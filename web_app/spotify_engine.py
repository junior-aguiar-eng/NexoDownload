#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor de Integração e Resolução do Spotify para Nexo Download.
Padrão Google Engineering: Extrai metadados oficiais do Spotify (oEmbed / Web API pública / Embed NextData)
e suporta faixas individuais, álbuns completos e playlists.
"""

import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Any, Optional, List


def is_spotify_url(url: str) -> bool:
    """Verifica se a URL pertence ao ecossistema do Spotify."""
    if not url:
        return False
    u = url.lower().strip()
    return "open.spotify.com" in u or "spotify.link" in u or u.startswith("spotify:")


def parse_spotify_url(url: str) -> Dict[str, str]:
    """Identifica o tipo de recurso do Spotify (track, album, playlist) e o ID."""
    match = re.search(r'spotify\.com/(track|album|playlist)/([a-zA-Z0-9]+)', url)
    if match:
        return {"type": match.group(1), "id": match.group(2)}
    
    uri_match = re.search(r'spotify:(track|album|playlist):([a-zA-Z0-9]+)', url)
    if uri_match:
        return {"type": uri_match.group(1), "id": uri_match.group(2)}

    return {"type": "unknown", "id": ""}


def fetch_spotify_collection_tracks(url: str) -> Optional[Dict[str, Any]]:
    """
    Extrai a lista de faixas de um Álbum ou Playlist do Spotify via endpoint oficial de Embed.
    Retorna nome da coleção, artista, capa e a lista de faixas individuais.
    """
    parsed = parse_spotify_url(url)
    if parsed["type"] not in ["album", "playlist"]:
        return None
    
    resource_type = parsed["type"]
    resource_id = parsed["id"]
    embed_url = f"https://open.spotify.com/embed/{resource_type}/{resource_id}"
    
    try:
        req = urllib.request.Request(
            embed_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
        if not match:
            return None
            
        data = json.loads(match.group(1))
        entity = data.get("props", {}).get("pageProps", {}).get("state", {}).get("data", {}).get("entity", {})
        if not entity:
            return None
            
        collection_title = entity.get("name", "Álbum Spotify")
        collection_artist = entity.get("subtitle", "")
        cover_art = entity.get("visualIdentity", {}).get("image", [{}])[0].get("url", "")
        
        raw_tracks = entity.get("trackList", [])
        tracks: List[Dict[str, Any]] = []
        
        for idx, t in enumerate(raw_tracks, start=1):
            t_title = t.get("title", f"Faixa {idx}")
            t_artist = t.get("subtitle", collection_artist)
            full_title = f"{t_artist} - {t_title}" if t_artist and t_artist not in t_title else t_title
            tracks.append({
                "track_number": idx,
                "title": t_title,
                "artist": t_artist,
                "full_title": full_title,
                "search_query": f"{t_artist} - {t_title} Audio" if t_artist else f"{t_title} Audio",
                "thumbnail": cover_art,
                "duration_ms": t.get("duration", 0)
            })
            
        return {
            "type": resource_type,
            "id": resource_id,
            "title": collection_title,
            "artist": collection_artist,
            "full_title": f"{collection_artist} - {collection_title}" if collection_artist else collection_title,
            "thumbnail": cover_art,
            "is_collection": True,
            "tracks": tracks
        }
    except Exception as e:
        print(f"[SpotifyEngine] Erro ao extrair coleção: {e}")
        return None


def fetch_spotify_metadata(url: str) -> Optional[Dict[str, Any]]:
    """
    Obtém metadados oficiais do Spotify.
    Se for álbum ou playlist, extrai a coleção e faixas.
    Se for faixa individual, extrai metadados da faixa.
    """
    parsed = parse_spotify_url(url)
    if parsed["type"] in ["album", "playlist"]:
        collection = fetch_spotify_collection_tracks(url)
        if collection:
            return collection
            
    try:
        clean_url = url.split("?")[0].strip()
        oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(clean_url)}"
        
        req = urllib.request.Request(
            oembed_url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                title_raw = data.get("title", "")
                thumbnail_url = data.get("thumbnail_url", "")
                
                artist = ""
                song_title = title_raw
                if " - " in title_raw:
                    parts = title_raw.rsplit(" - ", 1)
                    song_title = parts[0].strip()
                    artist = parts[1].strip()
                elif " by " in title_raw:
                    parts = title_raw.split(" by ", 1)
                    song_title = parts[0].strip()
                    artist = parts[1].strip()

                if not artist and parsed["type"] == "track":
                    try:
                        page_req = urllib.request.Request(
                            clean_url,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                        )
                        with urllib.request.urlopen(page_req, timeout=4.0) as page_resp:
                            page_html = page_resp.read().decode("utf-8", errors="ignore")
                            desc_match = re.search(r'<meta property="og:description" content="([^"·]+)', page_html)
                            if desc_match:
                                artist = desc_match.group(1).strip()
                    except Exception:
                        pass
                
                full_display = f"{artist} - {song_title}" if artist and artist not in song_title else song_title
                search_q = f"{artist} - {song_title} Audio" if artist else f"{song_title} Audio"

                return {
                    "type": parsed["type"],
                    "id": parsed["id"],
                    "title": song_title,
                    "artist": artist,
                    "full_title": full_display,
                    "thumbnail": thumbnail_url,
                    "search_query": search_q,
                    "is_collection": False
                }
    except Exception as e:
        print(f"[SpotifyEngine] Aviso ao consultar metadados: {e}")
        
    return None
