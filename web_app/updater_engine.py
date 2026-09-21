# -*- coding: utf-8 -*-
"""
Nexo Download - Motor de Auto-Atualização Silenciosa em 1-Clique.
Consulta releases oficiais no GitHub (junior-aguiar-eng/NexoDownload),
baixa o instalador em segundo plano e aplica atualização silenciosa via NSIS /S.
"""

import os
import sys
import json
import urllib.request
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional

CURRENT_VERSION = "2.1.0"
GITHUB_VERSION_URL = "https://raw.githubusercontent.com/junior-aguiar-eng/NexoDownload/main/version.json"

def get_current_version() -> str:
    return CURRENT_VERSION

def _parse_version(v_str: str) -> tuple:
    try:
        parts = [int(p) for p in v_str.strip().replace("v", "").split(".")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)

def check_for_updates(remote_url: str = GITHUB_VERSION_URL) -> Dict[str, Any]:
    """
    Verifica se há uma nova versão oficial disponível no repositório.
    """
    try:
        req = urllib.request.Request(
            remote_url,
            headers={
                "User-Agent": f"NexoDownload-Updater/{CURRENT_VERSION}",
                "Cache-Control": "no-cache"
            }
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                latest_ver = data.get("version", CURRENT_VERSION)
                
                is_newer = _parse_version(latest_ver) > _parse_version(CURRENT_VERSION)
                changelog_items = data.get("changelog", [])
                if isinstance(changelog_items, list):
                    changelog_text = "\n".join(f"• {item}" for item in changelog_items)
                else:
                    changelog_text = str(changelog_items)
                    
                return {
                    "has_update": is_newer,
                    "current_version": CURRENT_VERSION,
                    "latest_version": latest_ver,
                    "title": data.get("title", f"Nexo Download v{latest_ver}"),
                    "changelog": changelog_text,
                    "download_url": data.get("download_url", ""),
                    "release_date": data.get("release_date", "")
                }
    except Exception as e:
        # Falha silenciosa caso o usuário esteja offline ou o repositório ainda não tenha version.json
        pass

    return {
        "has_update": False,
        "current_version": CURRENT_VERSION,
        "latest_version": CURRENT_VERSION,
        "changelog": "",
        "download_url": ""
    }

def apply_silent_update(download_url: str, progress_callback=None) -> bool:
    """
    Baixa o novo instalador em %TEMP% e o executa com a flag /S (silenciosa).
    O instalador NSIS silencioso atualiza o diretório e reinicia o executável.
    """
    if not download_url:
        return False

    temp_dir = Path(tempfile.gettempdir())
    installer_path = temp_dir / "NexoDownload-Silent-Setup.exe"

    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": f"NexoDownload-Updater/{CURRENT_VERSION}"}
        )
        
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 65536
            
            with open(installer_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback and total_size > 0:
                        pct = round((downloaded / total_size) * 100, 1)
                        progress_callback(pct)

        if installer_path.exists() and installer_path.stat().st_size > 1024 * 1024:
            # Executa o instalador em modo silencioso (/S) desvinculado
            cmd = [str(installer_path), "/S"]
            subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
                close_fds=True
            )
            
            # Encerra o processo atual após 1 segundo para liberação dos arquivos
            def do_exit():
                import time
                time.sleep(1.0)
                os._exit(0)
                
            threading.Thread(target=do_exit, daemon=True).start()
            return True
    except Exception as e:
        print(f"[Updater] Erro ao aplicar atualização: {e}")
        return False

    return False
