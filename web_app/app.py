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
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, Optional, List

# Garante suporte UTF-8 e event loop do Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import yt_dlp
import urllib.parse

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
    from web_app.updater_engine import check_for_updates, apply_silent_update, get_current_version, is_trusted_update_url
    from web_app.prive_engine import (
        is_prive_configured, setup_prive_password, verify_prive_password,
        reset_prive_password, get_prive_download_folder, is_xvideos_url, sanitize_prive_title
    )
except ImportError:
    from spotify_engine import is_spotify_url, fetch_spotify_metadata
    from apple_music_engine import is_apple_music_url, fetch_apple_music_metadata
    from audio_processor import build_audio_ydl_options, clean_song_title
    from security_engine import get_hardware_id, verify_license_key, save_license, load_saved_license
    from updater_engine import check_for_updates, apply_silent_update, get_current_version, is_trusted_update_url
    from prive_engine import (
        is_prive_configured, setup_prive_password, verify_prive_password,
        reset_prive_password, get_prive_download_folder, is_xvideos_url, sanitize_prive_title
    )

try:
    from audio_engine import (
        process_audio_dsp,
        RVCVoiceConverter,
        VoiceTrainer,
        DSPConfig,
        RVCConfig,
        DSP_PRESETS,
        RVC_PRESETS,
        get_optimal_torch_device,
    )
    AUDIO_ENGINE_AVAILABLE = True
except Exception as _ae_err:
    AUDIO_ENGINE_AVAILABLE = False
    print(f"[AudioEngine Bridge]: Carregamento condicional: {_ae_err}")

MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None

class DownloadTask:
    """Representa uma tarefa de download com controle de ciclo de vida e cancelamento thread-safe."""
    def __init__(self, task_id: str, url: str, platform: str, media_type: str, is_prive: bool = False):
        self.task_id = task_id
        self.url = url
        self.platform = platform
        self.media_type = media_type
        self.is_prive = is_prive
        self.cancel_event = threading.Event()
        self.status = "starting"
        self.percent = 0.0
        self.message = "Iniciando..."
        self.start_time = time.time()
        self.error: Optional[str] = None
        self.result: Optional[dict] = None
        self.last_payload: Dict[str, Any] = {}

class DownloadTaskManager:
    """Gerenciador central e thread-safe de tarefas ativas de download."""
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[str, DownloadTask] = {}

    def register(self, task: DownloadTask):
        with self._lock:
            self._tasks[task.task_id] = task

    def get(self, task_id: str) -> Optional[DownloadTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status not in ["finished", "error", "cancelled"]:
                task.cancel_event.set()
                task.status = "cancelled"
                task.message = "Download cancelado pelo usuário."
                return True
            return False

    def cancel_all(self):
        with self._lock:
            for task in self._tasks.values():
                if task.status not in ["finished", "error", "cancelled"]:
                    task.cancel_event.set()
                    task.status = "cancelled"
                    task.message = "Encerrando aplicação..."

    def list_active(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "task_id": t.task_id,
                    "url": t.url,
                    "platform": t.platform,
                    "status": t.status,
                    "percent": t.percent,
                    "message": t.message,
                    "is_prive": t.is_prive,
                    "start_time": t.start_time
                }
                for t in self._tasks.values()
                if t.status in ["starting", "downloading", "converting"]
            ]

download_task_manager = DownloadTaskManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    yield
    # Encerramento gracioso: cancela downloads pendentes e finaliza threadpool
    try:
        download_task_manager.cancel_all()
        DOWNLOAD_EXECUTOR.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass

app = FastAPI(title="Nexo Download Pro - Mídia Digital Livre", version="2.2.0", lifespan=lifespan)

# Estado volátil da Sessão Privê (desbloqueada em memória durante a sessão)
prive_session_unlocked = False

DOWNLOAD_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="NexoDownloadWorker"
)

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
    try:
        download_task_manager.cancel_all()
        DOWNLOAD_EXECUTOR.shutdown(wait=False, cancel_futures=True)
    except Exception:
        pass
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
AUTHORIZED_DOWNLOAD_ROOTS = {DOWNLOADS_DIR.resolve()}

@app.get("/api/downloads-dir")
async def get_downloads_dir():
    return {"path": str(DOWNLOADS_DIR.resolve())}

def is_system_restricted_path(path: Path) -> bool:
    """Detecta se o caminho aponta para diretórios críticos do sistema operacional."""
    try:
        resolved = path.resolve()
        restricted_dirs = []
        if sys.platform == "win32":
            windir = os.environ.get("WINDIR", "C:\\Windows")
            prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
            system_drive = os.environ.get("SystemDrive", "C:")
            restricted_dirs.extend([
                Path(windir),
                Path(prog_files),
                Path(prog_files_x86),
                Path(system_drive) / "Windows",
                Path(system_drive) / "Program Files",
                Path(system_drive) / "Program Files (x86)",
                Path(system_drive) / "Windows" / "System32"
            ])
        else:
            restricted_dirs.extend([
                Path("/bin"), Path("/sbin"), Path("/usr/bin"), Path("/etc"), Path("/root")
            ])
            
        for r_dir in restricted_dirs:
            try:
                r_res = r_dir.resolve()
                if r_res in resolved.parents or resolved == r_res:
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return True

def is_safe_downloads_path(path: Path, base_dir: Optional[Path] = None) -> bool:
    """Verifica se o caminho resolvido reside estritamente dentro da pasta de downloads autorizada."""
    try:
        resolved_path = path.resolve()
        
        # Bloqueio obrigatório de pastas críticas do sistema
        if is_system_restricted_path(resolved_path):
            return False

        allowed_bases = set()
        if base_dir is not None:
            allowed_bases.add(base_dir.resolve())
        else:
            allowed_bases.update(b.resolve() for b in AUTHORIZED_DOWNLOAD_ROOTS)
            allowed_bases.add(DOWNLOADS_DIR.resolve())

        for b in allowed_bases:
            if b in resolved_path.parents or resolved_path == b:
                return True
        return False
    except Exception:
        return False

BLOCKED_EXEC_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".ps1", ".psm1", ".msi", ".msp", ".scr", ".com", ".pif", ".reg", ".dll",
    ".pyd", ".cpl", ".hta", ".inf", ".ins", ".isp", ".jar", ".lnk",
    ".sh", ".bash", ".bin", ".app", ".desktop"
}

# 1. Blindagem CORS: Restringe a origens estritamente locais (127.0.0.1 ou localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 2. Middleware de Proteção Local: Rejeita chamadas de páginas externas da web (anti-CSRF/DNS Rebinding)
class LocalHostSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and request.method in ["POST", "PUT", "DELETE"]:
            orig_lower = origin.lower()
            is_valid_local = (
                orig_lower.startswith("http://127.0.0.1") or
                orig_lower.startswith("http://localhost") or
                orig_lower.startswith("https://127.0.0.1") or
                orig_lower.startswith("https://localhost") or
                orig_lower == "null"
            )
            if not is_valid_local:
                return Response(
                    content='{"detail": "Acesso externo não autorizado por política de segurança local."}',
                    status_code=403,
                    media_type="application/json"
                )
        return await call_next(request)

app.add_middleware(LocalHostSecurityMiddleware)

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
    video_audio: str = "with_audio"  # "with_audio" ou "mute"
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


PRIVE_INACTIVITY_TIMEOUT_SECONDS = 900  # 15 minutos
last_prive_activity_time = 0.0

PRIVE_FAILED_ATTEMPTS: List[float] = []
PRIVE_LOCKOUT_UNTIL: float = 0.0
PRIVE_MAX_FAILED_ATTEMPTS = 5
PRIVE_WINDOW_SECONDS = 60
PRIVE_LOCKOUT_SECONDS = 30

def check_prive_auto_lock():
    global prive_session_unlocked, last_prive_activity_time
    if prive_session_unlocked:
        if (time.time() - last_prive_activity_time) > PRIVE_INACTIVITY_TIMEOUT_SECONDS:
            prive_session_unlocked = False

def record_prive_activity():
    global last_prive_activity_time
    last_prive_activity_time = time.time()

# ==============================================================================
# Endpoints da Sessão Privê (18+ / XVideos com Proteção de Senha)
# ==============================================================================

@app.get("/api/prive/status")
async def get_prive_status():
    """Retorna se a senha já foi configurada e se a sessão atual está desbloqueada (com auto-lock por inatividade)."""
    check_prive_auto_lock()
    configured = is_prive_configured()
    if prive_session_unlocked:
        record_prive_activity()
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
        record_prive_activity()
        return {"success": True, "unlocked": True, "message": "Senha Privê configurada com sucesso!"}
    return {"success": False, "message": "Erro ao gravar as credenciais privê."}

@app.post("/api/prive/unlock")
async def unlock_prive_endpoint(req: PrivePasswordRequest):
    """Desbloqueia a Sessão Privê com validação de senha e proteção contra força bruta."""
    global prive_session_unlocked, PRIVE_LOCKOUT_UNTIL, PRIVE_FAILED_ATTEMPTS
    now = time.time()

    if now < PRIVE_LOCKOUT_UNTIL:
        remaining = int(PRIVE_LOCKOUT_UNTIL - now) + 1
        return {
            "success": False,
            "locked_out": True,
            "message": f"Muitas tentativas incorretas. Aguarde {remaining}s antes de tentar novamente."
        }

    if not is_prive_configured():
        return {"success": False, "message": "Sessão Privê ainda não configurada."}

    if verify_prive_password(req.password):
        prive_session_unlocked = True
        record_prive_activity()
        PRIVE_FAILED_ATTEMPTS.clear()
        PRIVE_LOCKOUT_UNTIL = 0.0
        return {"success": True, "unlocked": True, "message": "Sessão Privê desbloqueada com sucesso!"}

    # Registra falha e aplica proteção temporária se exceder limite
    PRIVE_FAILED_ATTEMPTS = [t for t in PRIVE_FAILED_ATTEMPTS if (now - t) < PRIVE_WINDOW_SECONDS]
    PRIVE_FAILED_ATTEMPTS.append(now)

    if len(PRIVE_FAILED_ATTEMPTS) >= PRIVE_MAX_FAILED_ATTEMPTS:
        PRIVE_LOCKOUT_UNTIL = now + PRIVE_LOCKOUT_SECONDS
        return {
            "success": False,
            "locked_out": True,
            "message": f"Limite de tentativas excedido. Bloqueado por {PRIVE_LOCKOUT_SECONDS}s."
        }

    attempts_left = PRIVE_MAX_FAILED_ATTEMPTS - len(PRIVE_FAILED_ATTEMPTS)
    return {
        "success": False,
        "message": f"Senha incorreta. Tentativas restantes: {attempts_left}."
    }

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
    sha256: Optional[str] = None

@app.get("/api/check-update")
async def check_update_endpoint():
    """Consulta o GitHub Releases para verificar se há nova versão oficial."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, check_for_updates)

@app.post("/api/apply-update")
async def apply_update_endpoint(req: UpdateApplyRequest):
    """Baixa o novo instalador e executa a instalação silenciosa reiniciando o app com validação estrita."""
    url = req.download_url.strip()
    if not is_trusted_update_url(url):
        raise HTTPException(
            status_code=400,
            detail="URL de atualização não autorizada. Atualizações devem vir exclusivamente do repositório oficial."
        )
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, apply_silent_update, url, req.sha256)
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
        p = Path(selected_path).resolve()
        if p.exists() and p.is_dir() and not is_system_restricted_path(p):
            AUTHORIZED_DOWNLOAD_ROOTS.add(p)
            return {"success": True, "path": str(p)}
    return {"success": False, "path": "", "canceled": True}


@app.post("/api/set-downloads-dir")
async def set_downloads_dir(req: UpdateFolderRequest):
    """Define globalmente a pasta de downloads ativa."""
    global DOWNLOADS_DIR
    p = Path(req.path).resolve()
    if p.exists() and p.is_dir() and not is_system_restricted_path(p):
        DOWNLOADS_DIR = p
        AUTHORIZED_DOWNLOAD_ROOTS.add(p)
        return {"success": True, "path": str(DOWNLOADS_DIR)}
    return {"success": False, "message": "Diretório informado é inválido ou restrito."}


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
    if "soundcloud" in url_l or "snd.sc" in url_l:
        return "SoundCloud"
    if "vimeo" in url_l:
        return "Vimeo"
    return "Geral"


def normalize_target_url(url: str) -> str:
    """
    Normaliza URLs com peculiaridades conhecidas no yt-dlp.
    - Para Vimeo: Transforma https://vimeo.com/{id} em https://player.vimeo.com/video/{id}
      para permitir extração e download direto sem exigir login ou cookies.
    - Para URLs encurtadas (pin.it, spotify.link, vt.tiktok.com, vm.tiktok.com, on.soundcloud.com, snd.sc, fb.watch):
      Segue o redirecionamento HTTP para obter a URL canônica com os IDs reais.
    """
    url_clean = url.strip()

    # Redirecionamentos de links curtos conhecidos
    short_domains = ["pin.it", "spotify.link", "vt.tiktok.com", "vm.tiktok.com", "fb.watch", "on.soundcloud.com", "snd.sc"]
    if any(sd in url_clean.lower() for sd in short_domains):
        try:
            import urllib.request
            req = urllib.request.Request(
                url_clean,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                url_clean = resp.geturl()
        except Exception:
            pass

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


WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

def sanitize_filename(name: str, max_length: int = 120) -> str:
    """
    Remove caracteres ilegais para caminhos do Windows e outros sistemas,
    protege contra nomes reservados do Windows, caracteres de controle e
    limita o comprimento para evitar estouro de MAX_PATH (260 chars).
    """
    if not name:
        return "midia"
    # Remove caracteres inválidos no Windows: \ / : * ? " < > | e caracteres de controle (ASCII < 32)
    cleaned = "".join(c for c in name if c not in r'\/:*?"<>|' and ord(c) >= 32)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ._')
    if not cleaned:
        cleaned = "midia"
    base_check = cleaned.split(".")[0].upper()
    if base_check in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}_"
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip(' ._')
    return cleaned or "midia"


def concat_mp3_files(audio_files: List[Path], output_file: Path, ffmpeg_bin: str = "ffmpeg"):
    """Gera um arquivo de áudio contínuo mesclando uma lista de faixas MP3 com conformidade acústica e timeout seguro."""
    if not audio_files or len(audio_files) < 2:
        return
    valid_files = [af for af in audio_files if af.exists() and af.is_file() and af.stat().st_size > 0]
    if len(valid_files) < 2:
        return
    list_file = output_file.parent / f"_concat_{uuid.uuid4().hex[:8]}.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for af in valid_files:
                p_str = str(af.resolve()).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{p_str}'\n")
                
        # Tentativa 1: Re-encode LAME 320k 44.1kHz (elimina dessincronia e distorção por taxas de amostragem diferentes)
        cmd_reencode = [
            ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c:a", "libmp3lame",
            "-b:a", "320k",
            "-ar", "44100",
            str(output_file)
        ]
        res = subprocess.run(
            cmd_reencode,
            capture_output=True,
            check=False,
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        if res.returncode != 0:
            # Fallback para stream copy rápido caso libmp3lame encontre problemas
            cmd_copy = [
                ffmpeg_bin, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                str(output_file)
            ]
            subprocess.run(
                cmd_copy,
                capture_output=True,
                check=False,
                timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
    except subprocess.TimeoutExpired:
        print("[ConcatMP3] Timeout excedido durante a concatenação de áudio.")
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
    platform = detect_platform_name(url)
    task = DownloadTask(task_id, url, platform, req.media_type, is_prive=is_prive)
    download_task_manager.register(task)

    main_loop = asyncio.get_running_loop()

    main_loop.run_in_executor(
        DOWNLOAD_EXECUTOR,
        run_download_task,
        task_id,
        url,
        req.media_type,
        req.quality,
        req.audio_quality,
        req.video_audio,
        req.split_chapters,
        req.metadata,
        req.custom_folder,
        main_loop,
        is_prive
    )

    return {"task_id": task_id, "status": "started", "platform": platform, "is_prive": is_prive}


@app.post("/api/download/cancel/{task_id}")
async def cancel_download_endpoint(task_id: str):
    """Cancela com segurança uma tarefa de download ativa."""
    success = download_task_manager.cancel(task_id)
    if success:
        await progress_manager.broadcast_status(task_id, {
            "status": "cancelled",
            "percent": 0,
            "message": "Download cancelado pelo usuário."
        })
        return {"success": True, "task_id": task_id, "status": "cancelled"}
    task = download_task_manager.get(task_id)
    if task:
        return {"success": False, "task_id": task_id, "status": task.status, "message": "Download não está ativo."}
    return {"success": False, "task_id": task_id, "status": "not_found", "message": "Tarefa não encontrada."}


@app.get("/api/download/status/{task_id}")
async def get_download_status_endpoint(task_id: str):
    """Consulta o status atual de uma tarefa de download para resiliência na reconexão."""
    task = download_task_manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada.")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "percent": task.percent,
        "message": task.message,
        "platform": task.platform,
        "is_prive": task.is_prive,
        "last_payload": task.last_payload
    }


@app.get("/api/download/active")
async def get_active_downloads_endpoint():
    """Retorna todas as tarefas de download ativas em execução."""
    return {"tasks": download_task_manager.list_active()}


def run_download_task(
    task_id: str,
    url: str,
    media_type: str,
    quality: int,
    audio_quality: int = 320,
    video_audio: str = "with_audio",
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
    if platform == "SoundCloud":
        # SoundCloud é uma plataforma estritamente de áudio
        media_type = "audio"
    
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

    task = download_task_manager.get(task_id)

    def send_update(payload: dict):
        if task:
            task.status = payload.get("status", task.status)
            task.percent = float(payload.get("percent", task.percent))
            task.message = str(payload.get("message", task.message))
            task.last_payload = payload
        if loop and loop.is_running():
            try:
                payload["is_prive"] = bool(is_xvideos_url(url) or is_prive)
                payload["task_id"] = task_id
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
            if task and task.cancel_event.is_set():
                send_update({
                    "status": "cancelled",
                    "percent": 0,
                    "message": "Download do álbum cancelado pelo usuário."
                })
                return

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

            def album_track_hook(d):
                if task and task.cancel_event.is_set():
                    raise yt_dlp.utils.DownloadCancelled("Download cancelado pelo usuário.")

            track_ydl_opts: Dict[str, Any] = {
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "progress_hooks": [album_track_hook],
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
            except yt_dlp.utils.DownloadCancelled:
                send_update({
                    "status": "cancelled",
                    "percent": 0,
                    "message": "Download do álbum cancelado pelo usuário."
                })
                return
            except Exception as tr_err:
                print(f"[Aviso Faixa {idx}] {tr_err}")

        # Geração do Arquivo Contínuo Mesclado
        if len(downloaded_mp3s) > 1 and not (task and task.cancel_event.is_set()):
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
        if task and task.cancel_event.is_set():
            raise yt_dlp.utils.DownloadCancelled("Download cancelado pelo usuário.")

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
        "retries": 3,
        "fragment_retries": 5,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    }

    if ffmpeg_dir:
        ydl_opts["ffmpeg_location"] = ffmpeg_dir

    if media_type == "audio":
        audio_opts = build_audio_ydl_options(
            target_dir=target_dir,
            audio_quality=audio_quality,
            split_chapters=split_chapters,
            embed_thumbnail=True,
            ffmpeg_location=ffmpeg_dir
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
        # Vídeo: Com áudio vs Vídeo Mudo (Sem áudio)
        is_mute = (video_audio == "mute")
        if is_mute:
            video_format = (
                f"bestvideo[ext=mp4][height<={quality}]/"
                f"bestvideo[height<={quality}]/"
                f"bestvideo"
            )
        else:
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
            "merge_output_format": None if is_mute else "mp4"
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

        # Fallback inteligente: se o nome exato divergiu no pós-processamento, busca o arquivo mais recente gerado no target_dir
        if not saved_path.exists():
            recent_candidates = [
                f for f in target_dir.iterdir()
                if f.is_file() and not f.name.endswith(".part") and not f.name.endswith(".ytdl") and not f.name.startswith("_concat_")
            ]
            if recent_candidates:
                recent_candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                newest = recent_candidates[0]
                if (time.time() - newest.stat().st_mtime) < 90:
                    saved_path = newest

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
    except yt_dlp.utils.DownloadCancelled:
        try:
            for temp_f in target_dir.glob("*.part"):
                temp_f.unlink(missing_ok=True)
            for temp_f in target_dir.glob("*.ytdl"):
                temp_f.unlink(missing_ok=True)
        except Exception:
            pass
        send_update({
            "status": "cancelled",
            "percent": 0,
            "message": "Download cancelado pelo usuário."
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
        f = Path(req.file_path).resolve()
        target_folder = f.parent if f.is_file() else f
    elif req.platform:
        clean_platform = sanitize_filename(req.platform)
        target_folder = (DOWNLOADS_DIR / clean_platform).resolve()
    else:
        target_folder = DOWNLOADS_DIR.resolve()

    # Validação de segurança: o diretório deve estar estritamente dentro de DOWNLOADS_DIR
    if not is_safe_downloads_path(target_folder, DOWNLOADS_DIR):
        raise HTTPException(status_code=403, detail="Acesso negado: pasta fora do diretório de downloads.")

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
    if not req.file_path:
        raise HTTPException(status_code=400, detail="Caminho do arquivo não fornecido.")
        
    target_file = Path(req.file_path).resolve()
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    # 1. Impede Path Traversal (arquivo fora de DOWNLOADS_DIR)
    if not is_safe_downloads_path(target_file, DOWNLOADS_DIR):
        raise HTTPException(status_code=403, detail="Acesso negado: o arquivo não reside na pasta de downloads.")

    # 2. Bloqueia execução de arquivos perigosos/executáveis
    if target_file.suffix.lower() in BLOCKED_EXEC_EXTENSIONS:
        raise HTTPException(status_code=403, detail="Abertura de arquivos executáveis não é permitida por motivos de segurança.")

    try:
        if sys.platform == "win32":
            os.startfile(str(target_file))
        else:
            subprocess.run(["xdg-open" if sys.platform != "darwin" else "open", str(target_file)])
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Endpoints do Estúdio de Áudio & IA (DSP, RVC e Treinador de Voz Applio)
# ==============================================================================

AUDIO_STUDIO_DIR = DOWNLOADS_DIR / "Estudio_Audio"
AUDIO_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
AUTHORIZED_DOWNLOAD_ROOTS.add(AUDIO_STUDIO_DIR.resolve())

MODELS_DIR = BASE_DIR / "audio_engine" / "modelos"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_TRAIN_TASKS: Dict[str, Dict[str, Any]] = {}
ALLOWED_AUDIO_STREAM_EXTS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma", ".webm", ".opus"}


class DSPProcessRequest(BaseModel):
    input_path: str
    preset: Optional[str] = "custom"
    semitones: float = 0.0
    formant_shift_semitones: float = 0.0
    preserve_formants: bool = True
    reduce_noise: bool = True
    noise_prop_decrease: float = 0.85
    output_filename: Optional[str] = None


class RVCProcessRequest(BaseModel):
    input_path: str
    model_name: str
    pitch_semitones: int = 0
    index_rate: float = 0.75
    f0_method: str = "rmvpe"
    output_filename: Optional[str] = None


class VoiceTrainRequest(BaseModel):
    audio_source: str
    model_name: str
    epochs: int = 100
    batch_size: Optional[int] = None
    sample_rate: str = "40k"
    f0_method: str = "rmvpe"
    denoise: bool = True


@app.get("/api/audio/status")
async def get_audio_status():
    """Retorna status do motor de áudio, aceleração de hardware e presets disponíveis."""
    if not AUDIO_ENGINE_AVAILABLE:
        return {
            "available": False,
            "device": "cpu",
            "device_desc": "Motor de áudio não carregado",
            "dsp_presets": {},
            "demo_available": False,
            "models_count": 0,
        }

    device, device_desc = get_optimal_torch_device()
    demo_file = BASE_DIR / "audio_engine" / "demo.wav"
    models = list(MODELS_DIR.glob("*.pth"))

    presets_info = {
        k: {
            "semitones": v.semitones,
            "formant_shift_semitones": v.formant_shift_semitones,
            "reduce_noise": v.reduce_noise,
            "noise_prop_decrease": v.noise_prop_decrease,
        }
        for k, v in DSP_PRESETS.items()
    }

    return {
        "available": True,
        "device": device,
        "device_desc": device_desc,
        "dsp_presets": presets_info,
        "demo_available": demo_file.exists(),
        "demo_path": str(demo_file) if demo_file.exists() else "",
        "models_count": len(models),
        "models_dir": str(MODELS_DIR),
        "studio_dir": str(AUDIO_STUDIO_DIR),
    }


@app.get("/api/audio/models")
async def list_audio_models():
    """Lista todos os modelos RVC (.pth) disponíveis para conversão vocal."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    models = []
    for f in MODELS_DIR.glob("*.pth"):
        idx = f.with_suffix(".index")
        models.append({
            "name": f.stem,
            "filename": f.name,
            "path": str(f.resolve()),
            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            "has_index": idx.exists(),
            "index_path": str(idx.resolve()) if idx.exists() else None,
        })
    models.sort(key=lambda x: x["name"].lower())
    return {"models": models}


@app.post("/api/audio/select-file")
async def select_audio_file():
    """Abre o seletor nativo de arquivos do Windows para escolher áudio de entrada."""
    def _pick():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askopenfilename(
                title="Selecione um Arquivo de Áudio",
                filetypes=[
                    ("Arquivos de Áudio", "*.wav;*.mp3;*.m4a;*.flac;*.ogg;*.aac;*.wma;*.webm;*.opus"),
                    ("Todos os Arquivos", "*.*")
                ]
            )
            root.destroy()
            return selected
        except Exception as e:
            print(f"[AudioFileDialog] Erro: {e}")
            return ""

    loop = asyncio.get_running_loop()
    selected_path = await loop.run_in_executor(None, _pick)
    if selected_path:
        p = Path(selected_path).resolve()
        if p.exists() and p.is_file() and not is_system_restricted_path(p):
            return {"success": True, "path": str(p), "name": p.name}
    return {"success": False, "path": "", "canceled": True}


@app.post("/api/audio/select-folder")
async def select_audio_folder():
    """Abre o seletor nativo de pastas do Windows para selecionar dataset de treino."""
    def _pick_folder():
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(
                title="Selecione a Pasta com Gravações para Treinamento"
            )
            root.destroy()
            return selected
        except Exception as e:
            print(f"[AudioFolderDialog] Erro: {e}")
            return ""

    loop = asyncio.get_running_loop()
    selected_path = await loop.run_in_executor(None, _pick_folder)
    if selected_path:
        p = Path(selected_path).resolve()
        if p.exists() and p.is_dir() and not is_system_restricted_path(p):
            return {"success": True, "path": str(p)}
    return {"success": False, "path": "", "canceled": True}


@app.post("/api/audio/open-models-folder")
async def open_models_folder():
    """Abre a pasta local de modelos RVC no Windows Explorer."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(str(MODELS_DIR))
        else:
            subprocess.run(["xdg-open" if sys.platform != "darwin" else "open", str(MODELS_DIR)])
        return {"success": True, "path": str(MODELS_DIR)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/audio/process-dsp")
async def process_dsp_endpoint(req: DSPProcessRequest):
    """Executa a transformação vocal com o Motor 1 (DSP Tradicional)."""
    if not AUDIO_ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de áudio (AudioEngine) não disponível no ambiente.")

    input_file = Path(req.input_path).resolve()
    if is_system_restricted_path(input_file):
        raise HTTPException(status_code=403, detail="Acesso restrito ao arquivo informado.")
    if not input_file.exists() or not input_file.is_file():
        raise HTTPException(status_code=404, detail="Arquivo de áudio de entrada não encontrado.")

    AUDIO_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    out_filename = req.output_filename or f"dsp_{timestamp}_{input_file.stem}.wav"
    if not out_filename.endswith(".wav"):
        out_filename += ".wav"
    out_filename = sanitize_filename(out_filename)
    output_path = AUDIO_STUDIO_DIR / out_filename

    if req.preset and req.preset in DSP_PRESETS and req.preset != "custom":
        base_preset = DSP_PRESETS[req.preset]
        config = DSPConfig(
            semitones=req.semitones if req.semitones != 0.0 else base_preset.semitones,
            formant_shift_semitones=req.formant_shift_semitones if req.formant_shift_semitones != 0.0 else base_preset.formant_shift_semitones,
            preserve_formants=req.preserve_formants,
            reduce_noise=req.reduce_noise,
            noise_prop_decrease=req.noise_prop_decrease,
        )
    else:
        config = DSPConfig(
            semitones=req.semitones,
            formant_shift_semitones=req.formant_shift_semitones,
            preserve_formants=req.preserve_formants,
            reduce_noise=req.reduce_noise,
            noise_prop_decrease=req.noise_prop_decrease,
        )

    def _run_dsp():
        return process_audio_dsp(
            input_path=input_file,
            output_path=output_path,
            config=config,
        )

    loop = asyncio.get_running_loop()
    try:
        final_output = await loop.run_in_executor(None, _run_dsp)
        out_p = Path(final_output)
        return {
            "success": True,
            "output_path": str(out_p),
            "filename": out_p.name,
            "stream_url": f"/api/audio/stream?path={urllib.parse.quote(str(out_p))}",
            "size_mb": round(out_p.stat().st_size / (1024 * 1024), 2),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no processamento DSP: {e}")


@app.post("/api/audio/process-rvc")
async def process_rvc_endpoint(req: RVCProcessRequest):
    """Executa a conversão vocal com o Motor 2 (IA Neural RVC v2)."""
    if not AUDIO_ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de áudio (AudioEngine) não disponível no ambiente.")

    input_file = Path(req.input_path).resolve()
    if is_system_restricted_path(input_file):
        raise HTTPException(status_code=403, detail="Acesso restrito ao arquivo informado.")
    if not input_file.exists() or not input_file.is_file():
        raise HTTPException(status_code=404, detail="Arquivo de áudio de entrada não encontrado.")

    # Localização do modelo .pth
    model_path = Path(req.model_name).resolve()
    if not model_path.exists():
        candidate = MODELS_DIR / f"{req.model_name}.pth"
        if candidate.exists():
            model_path = candidate
        else:
            candidate2 = MODELS_DIR / req.model_name
            if candidate2.exists():
                model_path = candidate2
            else:
                raise HTTPException(status_code=404, detail=f"Modelo RVC '{req.model_name}' não encontrado.")

    index_path = model_path.with_suffix(".index")
    index_to_use = str(index_path) if index_path.exists() else None

    AUDIO_STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    out_filename = req.output_filename or f"rvc_{model_path.stem}_{timestamp}_{input_file.stem}.wav"
    if not out_filename.endswith(".wav"):
        out_filename += ".wav"
    out_filename = sanitize_filename(out_filename)
    output_path = AUDIO_STUDIO_DIR / out_filename

    rvc_config = RVCConfig(
        pitch_semitones=req.pitch_semitones,
        index_rate=req.index_rate,
        f0_method=req.f0_method,
    )

    def _run_rvc():
        converter = RVCVoiceConverter(
            model_path=str(model_path),
            index_path=index_to_use,
        )
        return converter.convert_voice(
            input_path=input_file,
            output_path=output_path,
            config=rvc_config,
        )

    loop = asyncio.get_running_loop()
    try:
        final_output = await loop.run_in_executor(None, _run_rvc)
        out_p = Path(final_output)
        return {
            "success": True,
            "output_path": str(out_p),
            "filename": out_p.name,
            "stream_url": f"/api/audio/stream?path={urllib.parse.quote(str(out_p))}",
            "size_mb": round(out_p.stat().st_size / (1024 * 1024), 2),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na conversão RVC: {e}")


@app.post("/api/audio/train-voice")
async def train_voice_endpoint(req: VoiceTrainRequest):
    """Inicia o treinamento e criação de modelo de voz (Applio / RVC v2)."""
    if not AUDIO_ENGINE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Módulo de áudio (AudioEngine) não disponível no ambiente.")

    src = Path(req.audio_source).resolve()
    if not src.exists():
        raise HTTPException(status_code=404, detail="Arquivo ou pasta de áudio de treino não encontrado.")
    if is_system_restricted_path(src):
        raise HTTPException(status_code=403, detail="Acesso restrito ao caminho informado.")

    clean_model_name = sanitize_filename(req.model_name).strip()
    if not clean_model_name:
        raise HTTPException(status_code=400, detail="Nome do modelo inválido.")

    task_id = str(uuid.uuid4())[:8]
    AUDIO_TRAIN_TASKS[task_id] = {
        "task_id": task_id,
        "status": "running",
        "model_name": clean_model_name,
        "percent": 10,
        "message": f"Iniciando fatiamento e preparação acústica para '{clean_model_name}'...",
        "start_time": time.time(),
        "error": None,
        "result": None,
    }

    def _worker():
        try:
            AUDIO_TRAIN_TASKS[task_id]["percent"] = 25
            AUDIO_TRAIN_TASKS[task_id]["message"] = "Processando dataset acústico e removendo ruídos de fundo..."
            trainer = VoiceTrainer()

            AUDIO_TRAIN_TASKS[task_id]["percent"] = 55
            AUDIO_TRAIN_TASKS[task_id]["message"] = f"Treinando rede neural RVC ({req.epochs} épocas, RMVPE)..."

            res = trainer.train(
                audio_source=src,
                model_name=clean_model_name,
                epochs=req.epochs,
                batch_size=req.batch_size,
                sample_rate=req.sample_rate,
                f0_method=req.f0_method,
                denoise=req.denoise,
            )

            AUDIO_TRAIN_TASKS[task_id]["percent"] = 100
            AUDIO_TRAIN_TASKS[task_id]["status"] = "finished"
            AUDIO_TRAIN_TASKS[task_id]["message"] = f"Modelo '{clean_model_name}' criado e compilado com sucesso!"
            AUDIO_TRAIN_TASKS[task_id]["result"] = {
                "model_name": res.model_name,
                "pth_path": str(res.pth_path),
                "index_path": str(res.index_path) if res.index_path else None,
                "total_epochs": res.total_epochs,
                "elapsed_seconds": round(res.elapsed_seconds, 1),
            }
        except Exception as exc:
            AUDIO_TRAIN_TASKS[task_id]["status"] = "error"
            AUDIO_TRAIN_TASKS[task_id]["error"] = str(exc)
            AUDIO_TRAIN_TASKS[task_id]["message"] = f"Falha no treino: {exc}"

    threading.Thread(target=_worker, daemon=True).start()
    return {"success": True, "task_id": task_id, "model_name": clean_model_name}


@app.get("/api/audio/train-status/{task_id}")
async def get_train_status(task_id: str):
    """Consulta o progresso e logs do treinamento de voz em segundo plano."""
    task = AUDIO_TRAIN_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa de treinamento não encontrada.")
    return task


@app.get("/api/audio/stream")
async def stream_audio(path: str = Query(...)):
    """Transmite o áudio gerado para o player HTML5 embutido."""
    p = Path(path).resolve()
    if is_system_restricted_path(p):
        raise HTTPException(status_code=403, detail="Acesso proibido: arquivo em diretório restrito do sistema.")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="Arquivo de áudio não encontrado.")
    if p.suffix.lower() not in ALLOWED_AUDIO_STREAM_EXTS:
        raise HTTPException(status_code=400, detail="Formato de áudio não suportado.")

    ext = p.suffix.lower()
    media_type = "audio/wav" if ext == ".wav" else ("audio/mpeg" if ext == ".mp3" else f"audio/{ext[1:]}")
    return FileResponse(str(p), media_type=media_type, filename=p.name)

