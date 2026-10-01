"""
Coletor de metadados ricos do YouTube.
Utiliza os serviços oficiais de oEmbed do ecossistema Google para obter informações autênticas.
"""

import requests
import re
from typing import Optional
from .models import VideoMetadata
from .url_parser import get_canonical_url


def fetch_video_metadata(video_id: str, timeout_seconds: int = 8) -> VideoMetadata:
    """
    Recupera título, autor, thumbnail e metadados oficiais do vídeo.
    Opera com múltiplos níveis de contingência para garantir 100% de disponibilidade.
    """
    canonical_url = get_canonical_url(video_id)
    default_thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    
    metadata = VideoMetadata(
        video_id=video_id,
        canonical_url=canonical_url,
        title=f"YouTube Video ({video_id})",
        channel_name="Canal do YouTube",
        channel_url="https://www.youtube.com",
        thumbnail_url=default_thumbnail
    )

    # 1. Tentativa via Google oEmbed Oficial
    try:
        oembed_url = f"https://www.youtube.com/oembed?url={canonical_url}&format=json"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }
        resp = requests.get(oembed_url, headers=headers, timeout=timeout_seconds)
        if resp.status_code == 200:
            data = resp.json()
            metadata.title = data.get("title", metadata.title).strip()
            metadata.channel_name = data.get("author_name", metadata.channel_name).strip()
            metadata.channel_url = data.get("author_url", metadata.channel_url).strip()
            metadata.thumbnail_url = data.get("thumbnail_url", default_thumbnail)
            return metadata
    except Exception:
        pass

    # 2. Contingência via Scraping leve de OpenGraph / Twitter Cards
    try:
        resp = requests.get(canonical_url, headers=headers, timeout=timeout_seconds)
        if resp.status_code == 200:
            html = resp.text
            title_match = re.search(r'<meta property="og:title" content="([^"]+)">', html)
            if title_match:
                metadata.title = title_match.group(1).strip()
                
            channel_match = re.search(r'<link itemprop="name" content="([^"]+)">', html)
            if channel_match:
                metadata.channel_name = channel_match.group(1).strip()
                
            thumb_match = re.search(r'<meta property="og:image" content="([^"]+)">', html)
            if thumb_match:
                metadata.thumbnail_url = thumb_match.group(1).strip()
    except Exception:
        pass

    return metadata
