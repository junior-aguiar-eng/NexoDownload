#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Integração e Resolução do Apple Music para Nexo Download.
Padrão Google Engineering: Extrai metadados oficiais do Apple Music (OpenGraph / iTunes Lookup API)
e suporta faixas individuais, álbuns completos e playlists.
"""

import re
import html
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List


def is_apple_music_url(url: str) -> bool:
    """Verifica se a URL pertence ao ecossistema do Apple Music / iTunes."""
    if not url:
        return False
    u = url.lower().strip()
    return "music.apple.com" in u or "itunes.apple.com" in u or "apple.co/" in u


def parse_apple_music_url(url: str) -> Dict[str, str]:
    """Identifica tipo (album, playlist, song), ID do álbum e ID da faixa (se presente)."""
    clean = url.split("?")[0].strip()
    
    # Ex: music.apple.com/br/album/random-access-memories/1573274292
    album_m = re.search(r'/(album|playlist)/([^/]+)/([0-9]+|pl\.[a-zA-Z0-9]+)', clean)
    track_param_m = re.search(r'[?&]i=([0-9]+)', url)
    
    res_type = "song" if track_param_m else ("album" if "/album/" in clean else ("playlist" if "/playlist/" in clean else "unknown"))
    res_id = ""
    if album_m:
        res_id = album_m.group(3)
        
    track_id = track_param_m.group(1) if track_param_m else ""
    return {
        "type": res_type,
        "album_id": res_id,
        "track_id": track_id
    }


def fetch_apple_music_collection_tracks(album_id: str, country: str = "us") -> Optional[Dict[str, Any]]:
    """
    Consulta o iTunes Lookup API oficial para extrair todas as faixas do álbum.
    """
    if not album_id or not album_id.isdigit():
        return None
        
    country_list = [c for c in [country, "br", "us", "gb", "es"] if c]
    seen_countries = set()
    for c in country_list:
        if c in seen_countries:
            continue
        seen_countries.add(c)
        try:
            lookup_url = f"https://itunes.apple.com/lookup?id={album_id}&entity=song&country={c}"
            req = urllib.request.Request(
                lookup_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
            results = data.get("results", [])
            if not results:
                continue
                
            collection_info = results[0]
            collection_title = collection_info.get("collectionName", "Álbum Apple Music")
            collection_artist = collection_info.get("artistName", "")
            cover_art = collection_info.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
            
            tracks: List[Dict[str, Any]] = []
            for item in results[1:]:
                if item.get("wrapperType") == "track":
                    t_title = item.get("trackName", "")
                    t_artist = item.get("artistName", collection_artist)
                    t_num = item.get("trackNumber", len(tracks) + 1)
                    full_title = f"{t_artist} - {t_title}" if t_artist and t_artist not in t_title else t_title
                    tracks.append({
                        "track_number": t_num,
                        "title": t_title,
                        "artist": t_artist,
                        "full_title": full_title,
                        "search_query": f"{t_artist} - {t_title} Audio" if t_artist else f"{t_title} Audio",
                        "thumbnail": cover_art,
                        "duration_ms": item.get("trackTimeMillis", 0)
                    })
                    
            if tracks:
                return {
                    "type": "album",
                    "id": album_id,
                    "title": collection_title,
                    "artist": collection_artist,
                    "full_title": f"{collection_artist} - {collection_title}" if collection_artist else collection_title,
                    "thumbnail": cover_art,
                    "is_collection": True,
                    "tracks": tracks
                }
        except Exception:
            pass
            
    return None


def fetch_apple_music_metadata(url: str) -> Optional[Dict[str, Any]]:
    """
    Obtém metadados oficiais do Apple Music.
    Se for álbum sem faixa específica (?i=), resolve as faixas da coleção.
    """
    parsed = parse_apple_music_url(url)
    if parsed["type"] in ["album", "playlist"] and parsed["album_id"] and not parsed["track_id"]:
        country = "br" if "/br/" in url else "us"
        collection = fetch_apple_music_collection_tracks(parsed["album_id"], country=country)
        if collection:
            return collection

    try:
        clean_url = url.split("?")[0].strip()
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
            }
        )

        with urllib.request.urlopen(req, timeout=10.0) as resp:
            content = resp.read().decode("utf-8", errors="ignore")

        og_title_m = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']*)["\']', content)
        og_title = html.unescape(og_title_m.group(1)) if og_title_m else ""

        apple_title_m = re.search(r'<meta\s+name=["\']apple:title["\']\s+content=["\']([^"\']*)["\']', content)
        apple_title = html.unescape(apple_title_m.group(1)) if apple_title_m else ""

        og_image_m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']*)["\']', content)
        og_image = og_image_m.group(1) if og_image_m else ""

        desc_m = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', content)
        desc = html.unescape(desc_m.group(1)) if desc_m else ""

        clean_og = re.sub(r'\s+(?:no|on)\s+Apple\s*Music.*$', '', og_title, flags=re.IGNORECASE).strip()

        artist = ""
        title = apple_title or clean_og

        if " de " in clean_og:
            parts = clean_og.rsplit(" de ", 1)
            title = parts[0].strip()
            artist = parts[1].strip()
        elif " by " in clean_og:
            parts = clean_og.rsplit(" by ", 1)
            title = parts[0].strip()
            artist = parts[1].strip()
        elif " - " in clean_og:
            parts = clean_og.split(" - ", 1)
            title = parts[0].strip()
            artist = parts[1].strip()

        if not artist and desc:
            m_desc = re.search(r'(?:de|by)\s+([^.]+?)\s+n[oa]\s+Apple\s*Music', desc, re.IGNORECASE)
            if m_desc:
                artist = m_desc.group(1).strip()

        full_display = f"{artist} - {title}" if artist and artist not in title else title
        search_q = f"{artist} - {title} Audio" if artist else f"{title} Audio"

        return {
            "title": title or "Áudio Apple Music",
            "artist": artist,
            "full_title": full_display,
            "thumbnail": og_image,
            "search_query": search_q,
            "is_collection": False
        }
    except Exception as e:
        print(f"[AppleMusicEngine] Erro ao extrair metadados: {e}")
        return None
