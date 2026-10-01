"""
Módulo de Download de Vídeo e Áudio de Alta Performance (yt-dlp).
Padrão Google Engineering: Download otimizado, seletor de resolução inteligente
e extração de podcast/áudio para estudos em mobilidade.
"""

import os
from pathlib import Path
from typing import Optional, Callable, Dict, Any
import yt_dlp

from .url_parser import get_canonical_url, extract_video_id


def download_media(
    video_input: str,
    output_dir: str,
    media_type: str = "video",  # 'video' ou 'audio'
    max_height: int = 720,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> str:
    """
    Realiza o download de vídeo ou áudio do YouTube com configurações de alta fidelidade.
    
    Parâmetros:
        video_input: URL ou ID do vídeo.
        output_dir: Diretório onde o arquivo de mídia será armazenado.
        media_type: 'video' (MP4) ou 'audio' (M4A/MP3).
        max_height: Resolução vertical máxima para economizar espaço (ex: 720, 1080).
        progress_callback: Função chamada a cada atualização de porcentagem/velocidade.
        
    Retorna:
        str: Caminho absoluto do arquivo baixado.
    """
    video_id = extract_video_id(video_input)
    if not video_id:
        raise ValueError(f"URL ou ID do YouTube inválido: {video_input}")

    canonical_url = get_canonical_url(video_id)
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    def ytdl_hook(d):
        if progress_callback and callable(progress_callback):
            progress_callback(d)

    # Configuração de acordo com o tipo de mídia
    if media_type == "speech_audio":
        # Formato ultra-leve para transcrição instantânea por IA
        ydl_opts = {
            "format": "ba[abr<=96]/ba/worst/bestaudio",
            "outtmpl": str(out_path / "temp_speech_%(id)s.%(ext)s"),
            "concurrent_fragment_downloads": 8,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [ytdl_hook]
        }
    elif media_type == "audio":
        # Extração de áudio de alta qualidade (MP3 192kbps) para estudos e podcast
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(out_path / "00_aula_audio.%(ext)s"),
            "concurrent_fragment_downloads": 8,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }] if _has_ffmpeg() else [],
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [ytdl_hook]
        }
    else:
        # Download de vídeo em MP4 (com fallback gracioso de resolução)
        ydl_opts = {
            "format": f"bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/best[ext=mp4]/best[height<={max_height}]/best",
            "outtmpl": str(out_path / "00_aula_video.%(ext)s"),
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": 8,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [ytdl_hook]
        }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(canonical_url, download=True)
        filename = ydl.prepare_filename(info)
        
        # Se houve conversão pós-processamento, ajusta extensão esperada
        if media_type == "audio" and _has_ffmpeg():
            filename = os.path.splitext(filename)[0] + ".mp3"
            
        return filename


def _has_ffmpeg() -> bool:
    """Verifica se o FFmpeg está disponível no sistema."""
    import shutil
    return shutil.which("ffmpeg") is not None
