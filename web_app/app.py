#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor FastAPI para o Nexo Download - Mídia Digital Livre.
Versão Pro: Thread-safe WebSocket, suporte dinâmico a FFmpeg local, yt-dlp resiliente,
metadados HD em vídeos MP4, download de álbuns/playlists (faixas separadas + álbum contínuo),
seletor nativo de pastas do Windows e sistema de licenciamento HWID criptográfico.
"""

import os
import sys
import re
import glob
import uuid
import shutil
import asyncio
import threading
import subprocess
import concurrent.futures
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Garante suporte UTF-8 e event loop do Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

# Determinação segura de diretórios
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent
for d in [str(BASE_DIR), str(APP_DIR)]:
    if d not in sys.path:
        sys.path.insert(0, d)

try:
    from web_app.spotify_engine import is_spotify_url, fetch_spotify_metadata
    from web_app.apple_music_engine import is_apple_music_url, fetch_apple_music_metadata
    from web_app.audio_processor import build_audio_ydl_options, clean_song_title
    from web_app.security_engine import get_hardware_id, verify_license_key, save_license, load_saved_license
    from web_app.updater_engine import check_for_updates, apply_silent_update, get_current_version
    from web_app.prive_engine import (
        is_prive_configured, setup_prive_password, verify_prive_password,
        reset_prive_password, get_prive_download_folder, is_xvideos_url, sanitize_prive_title
    )
except ImportError:
    from spotify_engine import is_spotify_url, fetch_spotify_metadata
    from apple_music_engine import is_apple_music_url, fetch_apple_music_metadata
    from audio_processor import build_audio_ydl_options, clean_song_title
    from security_engine import get_hardware_id, verify_license_key, save_license, load_saved_license
    from updater_engine import check_for_updates, apply_silent_update, get_current_version
    from prive_engine import (
        is_prive_configured, setup_prive_password, verify_prive_password,
        reset_prive_password, get_prive_download_folder, is_xvideos_url, sanitize_prive_title
    )

app = FastAPI(title="Nexo Download Pro - Mídia Digital Livre", version="2.1.0")

# Estado volátil da Sessão Privê (desbloqueada em memória durante a sessão)
prive_session_unlocked = False

DOWNLOAD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="NexoDownloadWorker"
)

MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None

@app.on_event("startup")
async def on_startup():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()

# Controle de ciclo de vida (Heartbeat da Janela WebView2)
last_heartbeat = time.time()
client_connected_ever = False

@app.post("/api/heartbeat")
async def receive_heartbeat():
    global last_heartbeat, client_connected_ever
    last_heartbeat = time.time()
    client_connected_ever = True
    return {"status": "ok", "time": last_heartbeat}

@app.post("/api/shutdown")
async def shutdown_system():
    global last_heartbeat
    last_heartbeat = 0
    def do_exit():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=do_exit, daemon=True).start()
    return {"status": "shutting_down"}

@app.get("/api/lifecycle")
async def get_lifecycle():
    global last_heartbeat, client_connected_ever
    return {
        "connected_ever": client_connected_ever,
        "seconds_since_heartbeat": round(time.time() - last_heartbeat, 2)
    }

# Resolução de diretórios (Desenvolvimento vs PyInstaller Frozen)
if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).resolve().parent
    internal_web = exe_dir / "_internal" / "web_app"
    app_dir = internal_web if internal_web.exists() else exe_dir / "web_app"
    DOWNLOADS_DIR = exe_dir / "downloads"
else:
    app_dir = Path(__file__).resolve().parent
    DOWNLOADS_DIR = BASE_DIR / "downloads"

STATIC_DIR = app_dir / "static"
TEMPLATES_DIR = app_dir / "templates"
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/api/downloads-dir")
async def get_downloads_dir():
    return {"path": str(DOWNLOADS_DIR.resolve())}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class ProgressManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[task_id] = websocket

    def disconnect(self, task_id: str):
        self.active_connections.pop(task_id, None)

    async def broadcast_status(self, task_id: str, data: Dict[str, Any]):
        ws = self.active_connections.get(task_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(task_id)

progress_manager = ProgressManager()


class DownloadRequest(BaseModel):
    url: str
    media_type: str = "video"  # "video" ou "audio"
    quality: int = 1080
    audio_quality: int = 320
    split_chapters: bool = False
    metadata: bool = True
    custom_folder: Optional[str] = None
    is_prive: bool = False


class OpenFolderRequest(BaseModel):
    platform: Optional[str] = None
    file_path: Optional[str] = None


class LicenseActivateRequest(BaseModel):
    key: str


class UpdateFolderRequest(BaseModel):
    path: str


class PrivePasswordRequest(BaseModel):
    password: str


# ==============================================================================
# Endpoints da Sessão Privê (18+ / XVideos com Proteção de Senha)
# ==============================================================================

@app.get("/api/prive/status")
async def get_prive_status():
    """Retorna se a senha já foi configurada e se a sessão atual está desbloqueada."""
    configured = is_prive_configured()
    return {
        "configured": configured,
        "unlocked": prive_session_unlocked if configured else False
    }

@app.post("/api/prive/setup")
async def setup_prive_endpoint(req: PrivePasswordRequest):
    """Configura a senha mestra da Sessão Privê no primeiro uso ou redefinição."""
    global prive_session_unlocked
    pwd = req.password.strip()
    if len(pwd) < 4:
        return {"success": False, "message": "A senha deve conter no mínimo 4 caracteres."}
    if setup_prive_password(pwd):
        prive_session_unlocked = True
        return {"success": True, "unlocked": True, "message": "Senha Privê configurada com sucesso!"}
    return {"success": False, "message": "Erro ao gravar as credenciais privê."}

@app.post("/api/prive/unlock")
async def unlock_prive_endpoint(req: PrivePasswordRequest):
    """Desbloqueia a Sessão Privê com validação de senha."""
    global prive_session_unlocked
    if not is_prive_configured():
        return {"success": False, "message": "Sessão Privê ainda não configurada."}
    if verify_prive_password(req.password):
        prive_session_unlocked = True
        return {"success": True, "unlocked": True, "message": "Sessão Privê desbloqueada com sucesso!"}
    return {"success": False, "message": "Senha incorreta. Verifique e tente novamente."}

@app.post("/api/prive/lock")
async def lock_prive_endpoint():
    """Tranca imediatamente a Sessão Privê."""
    global prive_session_unlocked
    prive_session_unlocked = False
    return {"success": True, "unlocked": False, "message": "Sessão Privê trancada."}

@app.post("/api/prive/reset")
async def reset_prive_endpoint():
    """Redefine as credenciais da Sessão Privê (Zero-Knowledge, sem tocar nos arquivos já salvos)."""
    global prive_session_unlocked
    prive_session_unlocked = False
    if reset_prive_password():
        return {"success": True, "message": "Credenciais da Sessão Privê redefinidas."}
    return {"success": False, "message": "Erro ao redefinir credenciais."}


# ==============================================================================
# Endpoints de Licença e Segurança HWID
# ==============================================================================

@app.get("/api/license/status")
async def get_license_status():
    """Retorna o status atual de ativação e o ID de máquina."""
    status = load_saved_license()
    return status

@app.post("/api/license/activate")
async def activate_license(req: LicenseActivateRequest):
    """Valida e grava a chave de licença no computador."""
    clean_key = req.key.strip()
    hwid = get_hardware_id()
    val = verify_license_key(clean_key, hwid)
    if val.get("valid"):
        saved = save_license(clean_key, val)
        if saved:
            return {
                "success": True,
                "message": "Nexo Download ativado com sucesso!",
                "plan": val.get("plan"),
                "expires": val.get("expires")
            }
        else:
            return {"success": False, "message": "Erro ao salvar arquivo de ativação no disco."}
    return {"success": False, "message": val.get("reason", "Chave de ativação inválida.")}


# ==============================================================================
# Endpoints de Auto-Atualização Silenciosa
# ==============================================================================

class UpdateApplyRequest(BaseModel):
    download_url: str

@app.get("/api/check-update")
async def check_update_endpoint():
    """Consulta o GitHub Releases para verificar se há nova versão oficial."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, check_for_updates)

@app.post("/api/apply-update")
async def apply_update_endpoint(req: UpdateApplyRequest):
    """Baixa o novo instalador e executa a instalação silenciosa reiniciando o app."""
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, apply_silent_update, req.download_url)
    return {"status": "updating_in_background"}


# ==============================================================================
# Endpoints de Sistema e Pastas
# ==============================================================================

@app.post("/api/select-folder")
async def select_folder_native():
    """Abre a janela nativa do Windows Explorer para escolher pasta de downloads."""
    def _open_dialog():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(
                initialdir=str(DOWNLOADS_DIR),
                title="Selecione a Pasta de Downloads do Nexo"
            )
            root.destroy()
            return selected
        except Exception as e:
            print(f"[FolderDialog] Erro: {e}")
            return ""

    loop = asyncio.get_running_loop()
    selected_path = await loop.run_in_executor(None, _open_dialog)
    if selected_path:
        p = Path(selected_path)
        if p.exists() and p.is_dir():
            return {"success": True, "path": str(p.resolve())}
    return {"success": False, "path": "", "canceled": True}


@app.post("/api/set-downloads-dir")
async def set_downloads_dir(req: UpdateFolderRequest):
    """Define globalmente a pasta de downloads ativa."""
    global DOWNLOADS_DIR
    p = Path(req.path)
    if p.exists() and p.is_dir():
        DOWNLOADS_DIR = p
        return {"success": True, "path": str(DOWNLOADS_DIR.resolve())}
    return {"success": False, "message": "Diretório informado não existe."}


def detect_platform_name(url: str) -> str:
    url_l = url.lower()
    if is_xvideos_url(url_l):
        return "XVideos"
    if "spotify" in url_l:
        return "Spotify"
    if "music.apple.com" in url_l or "apple.co" in url_l or "itunes.apple.com" in url_l:
        return "AppleMusic"
    if "youtu" in url_l:
        return "YouTube"
    if "pinterest" in url_l or "pin.it" in url_l:
        return "Pinterest"
    if "tiktok" in url_l:
        return "TikTok"
    if "instagram" in url_l:
        return "Instagram"
    if "twitter" in url_l or "x.com" in url_l:
        return "Twitter"
    if "facebook" in url_l or "fb.watch" in url_l:
        return "Facebook"
    if "twitch" in url_l:
        return "Twitch"
    if "vimeo" in url_l:
        return "Vimeo"
    return "Geral"


def normalize_target_url(url: str) -> str:
    """
    Normaliza URLs com peculiaridades conhecidas no yt-dlp.
    Para Vimeo: Transforma https://vimeo.com/{id} em https://player.vimeo.com/video/{id}
    para permitir extração e download direto sem exigir login ou cookies.
    """
    url_clean = url.strip()
    m_vimeo = re.search(r'vimeo\.com/(?:.*?/)?(\d+)', url_clean)
    if m_vimeo and "player.vimeo.com" not in url_clean:
        return f"https://player.vimeo.com/video/{m_vimeo.group(1)}"
    return url_clean


def find_ffmpeg_path() -> Optional[str]:
    """Descobre o executável ou pasta do FFmpeg no sistema ou no pacote."""
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend([
            exe_dir / "bin",
            exe_dir / "_internal" / "bin",
            exe_dir / "tools",
            exe_dir
        ])
    else:
        candidates.extend([
            BASE_DIR / "bin",
            BASE_DIR / "tools",
            BASE_DIR / "tools" / "ffmpeg" / "bin",
            BASE_DIR / "dist" / "NexoDownload" / "bin"
        ])

    localappdata = os.environ.get("LOCALAPPDATA", "")
    if localappdata:
        candidates.append(Path(localappdata) / "Microsoft" / "WinGet" / "Links")
    candidates.extend([
        Path("C:/Program Files/ffmpeg/bin"),
        Path("C:/ffmpeg/bin")
    ])

    for c in candidates:
        if (c / "ffmpeg.exe").exists():
            return str(c.resolve())

    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return str(Path(sys_ffmpeg).parent.resolve())

    return None


def sanitize_filename(name: str) -> str:
    """Remove caracteres ilegais para caminhos do Windows."""
    return "".join(c for c in name if c not in r'\/:*?"<>|').strip()


def concat_mp3_files(audio_files: List[Path], output_file: Path, ffmpeg_bin: str = "ffmpeg"):
    """Gera um arquivo de áudio contínuo mesclando uma lista de faixas MP3."""
    if not audio_files or len(audio_files) < 2:
        return
    list_file = output_file.parent / f"_concat_{uuid.uuid4().hex[:8]}.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for af in audio_files:
                p_str = str(af.resolve()).replace("\\", "/")
                f.write(f"file '{p_str}'\n")
                
        cmd = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_file)
        ]
        subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
    except Exception as e:
        print(f"[ConcatMP3] Aviso: {e}")
    finally:
        if list_file.exists():
            try:
                list_file.unlink()
            except Exception:
                pass


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Interface index.html não encontrada.")
    return index_file.read_text(encoding="utf-8")


@app.get("/api/info")
async def get_url_info(url: str = Query(...)):
    clean_url = normalize_target_url(url.strip())
    if not clean_url or not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        return {"valid": False, "platform": "Desconhecido"}

    platform = detect_platform_name(clean_url)
    info_resp = {"valid": True, "platform": platform, "url": clean_url}

    if platform == "Spotify":
        sp_meta = fetch_spotify_metadata(clean_url)
        if sp_meta:
            info_resp.update({
                "title": sp_meta.get("title", ""),
                "artist": sp_meta.get("artist", ""),
                "thumbnail": sp_meta.get("thumbnail", ""),
                "is_spotify": True,
                "is_collection": sp_meta.get("is_collection", False),
                "tracks_count": len(sp_meta.get("tracks", [])) if sp_meta.get("is_collection") else 1
            })
    elif platform == "AppleMusic":
        apple_meta = fetch_apple_music_metadata(clean_url)
        if apple_meta:
            info_resp.update({
                "title": apple_meta.get("title", ""),
                "artist": apple_meta.get("artist", ""),
                "thumbnail": apple_meta.get("thumbnail", ""),
                "is_apple_music": True,
                "is_collection": apple_meta.get("is_collection", False),
                "tracks_count": len(apple_meta.get("tracks", [])) if apple_meta.get("is_collection") else 1
            })
    elif platform == "XVideos":
        info_resp["is_prive"] = True
        if not prive_session_unlocked:
            info_resp.update({
                "title": "Conteúdo Privê (XVideos)",
                "artist": "Sessão Privê",
                "thumbnail": "",
                "requires_prive_unlock": True,
                "is_locked": True
            })
        else:
            try:
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                    x_info = ydl.extract_info(clean_url, download=False)
                    info_resp.update({
                        "title": sanitize_prive_title(x_info.get("title", "Vídeo XVideos")),
                        "artist": x_info.get("uploader", "XVideos"),
                        "thumbnail": x_info.get("thumbnail", ""),
                        "duration": x_info.get("duration", 0),
                        "is_locked": False
                    })
            except Exception:
                info_resp.update({
                    "title": "Vídeo XVideos",
                    "artist": "XVideos",
                    "thumbnail": "",
                    "is_locked": False
                })
    else:
        # Plataformas de vídeo em geral (YouTube, Vimeo, TikTok, Instagram, Twitter, etc.)
        try:
            with yt_dlp.YoutubeDL({
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "socket_timeout": 6
            }) as ydl:
                v_meta = ydl.extract_info(clean_url, download=False)
                if v_meta:
                    info_resp.update({
                        "title": v_meta.get("title", ""),
                        "artist": v_meta.get("uploader", "") or v_meta.get("channel", ""),
                        "thumbnail": v_meta.get("thumbnail", ""),
                        "duration": v_meta.get("duration", 0)
                    })
        except Exception:
            pass

    return info_resp


@app.post("/api/download")
async def start_download(req: DownloadRequest):
    url = normalize_target_url(req.url.strip())
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="URL inválida.")

    is_prive = is_xvideos_url(url) or req.is_prive
    if is_prive and not prive_session_unlocked:
        raise HTTPException(status_code=403, detail="Sessão Privê bloqueada. Desbloqueie com sua senha para iniciar o download.")

    task_id = str(uuid.uuid4())
    main_loop = asyncio.get_running_loop()

    main_loop.run_in_executor(
        DOWNLOAD_EXECUTOR,
        run_download_task,
        task_id,
        url,
        req.media_type,
        req.quality,
        req.audio_quality,
        req.split_chapters,
        req.metadata,
        req.custom_folder,
        main_loop,
        is_prive
    )

    return {"task_id": task_id, "status": "started", "platform": detect_platform_name(url), "is_prive": is_prive}


def run_download_task(
    task_id: str,
    url: str,
    media_type: str,
    quality: int,
    audio_quality: int = 320,
    split_chapters: bool = False,
    metadata: bool = True,
    custom_folder: Optional[str] = None,
    main_loop: Optional[asyncio.AbstractEventLoop] = None,
    is_prive: bool = False
):
    global MAIN_LOOP, DOWNLOADS_DIR
    url = normalize_target_url(url)
    loop = main_loop or MAIN_LOOP
    platform = detect_platform_name(url)
    
    base_target = Path(custom_folder) if custom_folder and Path(custom_folder).exists() else DOWNLOADS_DIR
    if is_xvideos_url(url) or is_prive:
        target_dir = get_prive_download_folder(base_target)
        platform = "XVideos" if is_xvideos_url(url) else platform
    else:
        target_dir = base_target / platform
    target_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_dir = find_ffmpeg_path()
    ffmpeg_exe = str(Path(ffmpeg_dir) / "ffmpeg.exe") if ffmpeg_dir else "ffmpeg"
    if ffmpeg_dir and ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

    def send_update(payload: dict):
        if loop and loop.is_running():
            try:
                payload["is_prive"] = bool(is_xvideos_url(url) or is_prive)
                asyncio.run_coroutine_threadsafe(
                    progress_manager.broadcast_status(task_id, payload),
                    loop
                )
            except Exception:
                pass

    send_update({
        "status": "starting",
        "message": f"Conectando aos servidores de {platform}...",
        "platform": platform,
        "percent": 5
    })

    # Resolução de Plataformas de Áudio (Spotify / Apple Music)
    music_meta = None
    if platform == "Spotify":
        send_update({"status": "starting", "message": "Obtendo dados no Spotify...", "platform": "Spotify", "percent": 10})
        music_meta = fetch_spotify_metadata(url)
        media_type = "audio"
    elif platform == "AppleMusic":
        send_update({"status": "starting", "message": "Obtendo dados no Apple Music...", "platform": "AppleMusic", "percent": 10})
        music_meta = fetch_apple_music_metadata(url)
        media_type = "audio"

    # ==========================================================================
    # CASO 1: Álbum ou Playlist (Múltiplas Faixas + Álbum Contínuo)
    # ==========================================================================
    if music_meta and music_meta.get("is_collection") and music_meta.get("tracks"):
        tracks = music_meta["tracks"]
        total_tracks = len(tracks)
        col_title = sanitize_filename(music_meta.get("title", "Álbum"))
        col_artist = sanitize_filename(music_meta.get("artist", platform))
        folder_name = f"{col_artist} - {col_title}" if col_artist and col_artist not in col_title else col_title
        album_dir = target_dir / folder_name
        album_dir.mkdir(parents=True, exist_ok=True)

        send_update({
            "status": "downloading",
            "message": f"Iniciando álbum: {col_title} ({total_tracks} faixas)...",
            "percent": 10,
            "total_tracks": total_tracks,
            "current_track": 1
        })

        downloaded_mp3s: List[Path] = []

        for idx, tr in enumerate(tracks, start=1):
            track_name = sanitize_filename(tr.get("title", f"Faixa {idx}"))
            t_artist = sanitize_filename(tr.get("artist", col_artist))
            full_track_name = f"{idx:02d} - {t_artist} - {track_name}" if t_artist else f"{idx:02d} - {track_name}"
            
            percent_base = 10 + int((idx - 1) / total_tracks * 80)
            send_update({
                "status": "downloading",
                "message": f"[{idx}/{total_tracks}] Baixando: {track_name}",
                "percent": percent_base,
                "current_track": idx,
                "total_tracks": total_tracks
            })

            track_ydl_opts: Dict[str, Any] = {
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "format": "bestaudio/best",
                "outtmpl": str(album_dir / f"{full_track_name}.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(audio_quality),
                }]
            }
            if ffmpeg_dir:
                track_ydl_opts["ffmpeg_location"] = ffmpeg_dir

            search_query = f"ytsearch1:{tr.get('search_query', track_name)}"
            try:
                with yt_dlp.YoutubeDL(track_ydl_opts) as ydl:
                    ydl.download([search_query])

                # Localiza o arquivo gerado
                expected_mp3 = album_dir / f"{full_track_name}.mp3"
                if expected_mp3.exists():
                    downloaded_mp3s.append(expected_mp3)
                else:
                    candidates = list(album_dir.glob(f"{idx:02d} - *.mp3"))
                    if candidates:
                        downloaded_mp3s.append(candidates[-1])
            except Exception as tr_err:
                print(f"[Aviso Faixa {idx}] {tr_err}")

        # Geração do Arquivo Contínuo Mesclado
        if len(downloaded_mp3s) > 1:
            send_update({
                "status": "converting",
                "message": "Gerando álbum contínuo mesclado (Álbum Completo)...",
                "percent": 95
            })
            continuous_filename = f"{col_title} (Álbum Completo).mp3"
            continuous_path = album_dir / continuous_filename
            concat_mp3_files(downloaded_mp3s, continuous_path, ffmpeg_bin=ffmpeg_exe)

        send_update({
            "status": "finished",
            "completed": True,
            "percent": 100,
            "filename": f"{col_title} ({total_tracks} faixas + Álbum Completo)",
            "platform": platform,
            "size_mb": round(sum(f.stat().st_size for f in album_dir.glob("*.mp3")) / (1024 * 1024), 2),
            "folder_path": str(album_dir),
            "file_path": str(album_dir),
            "message": f"Álbum completo baixado em {album_dir.name}!"
        })
        return

    # ==========================================================================
    # CASO 2: Mídia Individual (Vídeo ou Faixa de Áudio Única)
    # ==========================================================================
    actual_url = url
    if music_meta and "search_query" in music_meta:
        actual_url = f"ytsearch1:{music_meta['search_query']}"
        send_update({
            "status": "starting",
            "message": f"Localizando áudio master: {music_meta.get('full_title', '')}",
            "platform": platform,
            "percent": 15
        })

    def ytdl_hook(d):
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            percent = (downloaded / total * 100) if total > 0 else 0
            speed = d.get("speed") or 0
            speed_str = f"{speed / (1024 * 1024):.1f} MB/s" if speed > (1024 * 1024) else f"{speed / 1024:.0f} KB/s"
            eta = d.get("eta")
            eta_str = f"{eta}s" if eta else "--"

            downloaded_mb = round(downloaded / (1024 * 1024), 2)
            total_mb = round(total / (1024 * 1024), 2) if total else 0

            send_update({
                "status": "downloading",
                "percent": round(percent, 1),
                "downloaded_mb": downloaded_mb,
                "total_mb": total_mb,
                "downloaded_str": f"{downloaded_mb} MB",
                "total_str": f"{total_mb} MB" if total else "--",
                "speed": speed_str,
                "speed_str": speed_str,
                "eta": eta_str,
                "eta_str": eta_str,
                "message": f"Baixando mídia ({percent:.1f}%)..."
            })
        elif status == "finished":
            send_update({
                "status": "converting",
                "percent": 98.0,
                "message": "Finalizando e integrando metadados atômicos..."
            })

    ydl_opts: Dict[str, Any] = {
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
        "progress_hooks": [ytdl_hook],
    }

    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    if media_type == "audio":
        audio_opts = build_audio_ydl_options(
            target_dir=target_dir,
            audio_quality=audio_quality,
            split_chapters=split_chapters,
            embed_thumbnail=True
        )
        if audio_opts:
            ydl_opts.update(audio_opts)
        else:
            ydl_opts.update({
                "format": "bestaudio/best",
                "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": str(audio_quality),
                }]
            })
    else:
        # Vídeo MP4 com metadados e thumbnail embutidos nativamente
        video_format = (
            f"bestvideo[ext=mp4][height<={quality}]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={quality}]+bestaudio/"
            f"bestvideo+bestaudio/"
            f"best[height<={quality}]/"
            f"best"
        )
        ydl_opts.update({
            "format": video_format,
            "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
            "merge_output_format": "mp4"
        })
        
        if metadata:
            ydl_opts["writethumbnail"] = True
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegMetadata",
                    "add_chapters": True,
                    "add_metadata": True,
                },
                {
                    "key": "EmbedThumbnail",
                    "already_have_thumbnail": False,
                }
            ]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(actual_url, download=True)
            if "entries" in info and info["entries"]:
                info = info["entries"][0]
            filename = ydl.prepare_filename(info)

        saved_path = Path(filename)
        if not saved_path.exists():
            for ext in [".mp4", ".mkv", ".webm", ".mp3", ".m4a"]:
                if saved_path.with_suffix(ext).exists():
                    saved_path = saved_path.with_suffix(ext)
                    break

        if saved_path.exists():
            if music_meta and music_meta.get("full_title"):
                clean_name = sanitize_filename(music_meta["full_title"]) + saved_path.suffix
                new_path = saved_path.parent / clean_name
                try:
                    saved_path.rename(new_path)
                    saved_path = new_path
                except Exception:
                    pass

            size_mb = saved_path.stat().st_size / (1024 * 1024)
            send_update({
                "status": "finished",
                "completed": True,
                "percent": 100,
                "filename": saved_path.name,
                "platform": platform,
                "size_mb": round(size_mb, 2),
                "folder_path": str(saved_path.parent),
                "file_path": str(saved_path),
                "message": "Download concluído com sucesso!"
            })
        else:
            send_update({
                "status": "error",
                "error": "Arquivo concluído, mas não localizado no disco.",
                "message": "Arquivo concluído, mas não localizado no disco."
            })
    except Exception as e:
        print(f"[ERRO YT-DLP]: {e}")
        send_update({
            "status": "error",
            "error": str(e),
            "message": str(e)
        })


@app.websocket("/ws/progress/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    await progress_manager.connect(task_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, ConnectionResetError, Exception):
        pass
    finally:
        progress_manager.disconnect(task_id)


@app.get("/api/history")
async def get_history(show_prive: bool = False):
    files_list = []
    if DOWNLOADS_DIR.exists():
        for file_path in DOWNLOADS_DIR.rglob("*.*"):
            if file_path.is_file() and not file_path.name.endswith(".part"):
                is_file_prive = "Privê" in file_path.parts or "Prive" in file_path.parts
                # Se for arquivo privê e a sessão estiver trancada, esconde do histórico
                if is_file_prive and not (show_prive and prive_session_unlocked):
                    continue
                stat = file_path.stat()
                platform = "XVideos" if is_file_prive else (file_path.parent.name if file_path.parent != DOWNLOADS_DIR else "Geral")
                files_list.append({
                    "name": file_path.name,
                    "platform": platform,
                    "is_prive": is_file_prive,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": stat.st_mtime,
                    "ext": file_path.suffix.lower().replace(".", ""),
                    "file_path": str(file_path),
                    "folder_path": str(file_path.parent)
                })

    files_list.sort(key=lambda x: x["modified"], reverse=True)
    return {"files": files_list[:25]}


@app.post("/api/open-folder")
async def open_folder(req: OpenFolderRequest):
    target_folder = None
    if req.file_path:
        f = Path(req.file_path)
        target_folder = f.parent if f.is_file() else f
    elif req.platform:
        target_folder = DOWNLOADS_DIR / req.platform
    else:
        target_folder = DOWNLOADS_DIR

    if target_folder and target_folder.exists():
        try:
            if sys.platform == "win32":
                os.startfile(str(target_folder))
            else:
                subprocess.run(["xdg-open" if sys.platform != "darwin" else "open", str(target_folder)])
            return {"success": True, "opened": str(target_folder)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=404, detail="Pasta não encontrada.")


@app.post("/api/open-file")
async def open_file(req: OpenFolderRequest):
    if not req.file_path or not Path(req.file_path).exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    try:
        if sys.platform == "win32":
            os.startfile(str(req.file_path))
        else:
            subprocess.run(["xdg-open" if sys.platform != "darwin" else "open", str(req.file_path)])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))