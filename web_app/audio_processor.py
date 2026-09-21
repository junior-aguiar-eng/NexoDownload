#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Áudio Estruturado de Alta Fidelidade para Nexo Download.
Padrão Google Engineering: Limpeza semântica de títulos, injeção de capas em alta resolução
e opções para álbuns e fatiamento automático por capítulos.
"""

import re
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


def clean_song_title(raw_title: str) -> Dict[str, str]:
    """
    Remove ruídos e sufixos de videoclipes (ex: [Official Video], 4K, Clipe Oficial)
    para manter apenas o Artista e o Nome Real da Música.
    """
    if not raw_title:
        return {"artist": "", "title": "Áudio"}

    cleaned = raw_title
    
    # Padrões comuns de poluição de videoclipe
    junk_patterns = [
        r'\[official\s*(music)?\s*video\]',
        r'\(official\s*(music)?\s*video\)',
        r'\[clipe\s*oficial\]',
        r'\(clipe\s*oficial\)',
        r'\[video\s*oficial\]',
        r'\(video\s*oficial\)',
        r'\[vídeo\s*oficial\]',
        r'\(vídeo\s*oficial\)',
        r'\[audio\s*oficial\]',
        r'\(audio\s*oficial\)',
        r'\[áudio\s*oficial\]',
        r'\(áudio\s*oficial\)',
        r'\[official\s*audio\]',
        r'\(official\s*audio\)',
        r'\[official\s*visualizer\]',
        r'\(official\s*visualizer\)',
        r'\[lyric\s*video\]',
        r'\(lyric\s*video\)',
        r'\[letra\]',
        r'\(letra\)',
        r'\[lyrics\]',
        r'\(lyrics\)',
        r'\[4k\]',
        r'\(4k\)',
        r'\[hd\]',
        r'\(hd\)',
        r'\[1080p\]',
        r'\(1080p\)',
        r'\[remastered\]',
        r'\(remastered\)',
    ]
    
    for pat in junk_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE)

    # Limpa espaços e pontuações remanescentes
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' -_')

    artist = ""
    title = cleaned

    if " - " in cleaned:
        parts = cleaned.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()

    return {"artist": artist, "title": title}


def build_audio_ydl_options(
    target_dir: Path,
    audio_quality: int = 320,
    split_chapters: bool = False,
    embed_thumbnail: bool = True,
    ffmpeg_location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constrói as configurações otimizadas do yt-dlp para extração pura de áudio de estúdio.
    """
    has_ffmpeg = (ffmpeg_location and Path(ffmpeg_location).exists()) or (shutil.which("ffmpeg") is not None)
    
    # Formato e qualidade
    # 320kbps ou 192kbps -> MP3 (LAME)
    # 256kbps -> AAC / M4A (Original Apple)
    codec = "m4a" if audio_quality == 256 else "mp3"
    bitrate_str = str(audio_quality)

    postprocessors = []

    if has_ffmpeg:
        # 1. Extração / conversão de áudio
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": codec,
            "preferredquality": bitrate_str,
        })

        # 2. Injeção de metadados oficiais (ID3)
        postprocessors.append({
            "key": "FFmpegMetadata",
            "add_metadata": True,
        })

        # 3. Injeção de capa de álbum embutida
        if embed_thumbnail:
            postprocessors.append({
                "key": "EmbedThumbnail",
                "already_have_thumbnail": False,
            })

        # 4. Fatiamento por capítulos (se ativado)
        if split_chapters:
            postprocessors.append({
                "key": "FFmpegSplitChapters",
                "force_keyframes": False,
            })

    out_pattern = "%(section_number)02d - %(section_title)s.%(ext)s" if split_chapters else "%(title)s.%(ext)s"

    opts: Dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(target_dir / out_pattern),
        "postprocessors": postprocessors,
        "writethumbnail": embed_thumbnail and has_ffmpeg,
    }

    if ffmpeg_location:
        opts["ffmpeg_location"] = ffmpeg_location

    return opts
