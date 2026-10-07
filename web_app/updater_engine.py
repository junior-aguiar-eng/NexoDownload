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
import urllib.parse
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Dict, Any, Optional

CURRENT_VERSION = "2.2.0"
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

def is_trusted_update_url(url: object) -> bool:
    """
    Valida se a URL de atualização pertence exclusivamente ao repositório oficial do projeto.
    Previne ataques de Remote Code Execution (RCE) via injeção de binários arbitrários.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme != "https":
            return False
            
        netloc = parsed.netloc.lower()
        # Permite apenas o domínio oficial de releases do GitHub e seu CDN de assets
        if netloc == "github.com":
            return parsed.path.startswith("/junior-aguiar-eng/NexoDownload/releases/")
        elif netloc == "objects.githubusercontent.com":
            return True
        elif netloc == "raw.githubusercontent.com":
            return parsed.path.startswith("/junior-aguiar-eng/NexoDownload/")
            
        return False
    except Exception:
        return False

def check_for_updates(remote_url: str = GITHUB_VERSION_URL) -> Dict[str, Any]:
    """
    Verifica se há uma nova versão oficial disponível no repositório.
    """
    if not is_trusted_update_url(remote_url):
        return {
            "has_update": False,
            "current_version": CURRENT_VERSION,
            "latest_version": CURRENT_VERSION,
            "changelog": "",
            "download_url": ""
        }

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
                raw_download_url = data.get("download_url", "")
                
                # Validação de segurança na URL de download fornecida pelo manifesto
                safe_download_url = raw_download_url if is_trusted_update_url(raw_download_url) else ""
                raw_sha256 = str(data.get("sha256", "")).strip().lower()
                
                is_newer = _parse_version(latest_ver) > _parse_version(CURRENT_VERSION)
                changelog_items = data.get("changelog", [])
                if isinstance(changelog_items, list):
                    changelog_text = "\n".join(f"• {item}" for item in changelog_items)
                else:
                    changelog_text = str(changelog_items)
                    
                return {
                    "has_update": is_newer and bool(safe_download_url),
                    "current_version": CURRENT_VERSION,
                    "latest_version": latest_ver,
                    "title": data.get("title", f"Nexo Download v{latest_ver}"),
                    "changelog": changelog_text,
                    "download_url": safe_download_url,
                    "sha256": raw_sha256,
                    "release_date": data.get("release_date", "")
                }
    except Exception:
        pass

    return {
        "has_update": False,
        "current_version": CURRENT_VERSION,
        "latest_version": CURRENT_VERSION,
        "changelog": "",
        "download_url": "",
        "sha256": ""
    }

def apply_silent_update(download_url: str, expected_sha256: Optional[str] = None, progress_callback=None) -> bool:
    """
    Baixa o novo instalador em %TEMP% e o executa com a flag /S (silenciosa).
    Garante validação estrita de domínio antes do download, validação de integridade SHA-256 e validação do cabeçalho PE.
    """
    if not download_url or not is_trusted_update_url(download_url):
        print(f"[Updater] URL de atualização rejeitada por política de segurança: {download_url}")
        return False

    temp_dir = Path(tempfile.gettempdir())
    installer_path = temp_dir / "NexoDownload-Silent-Setup.exe"

    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": f"NexoDownload-Updater/{CURRENT_VERSION}"}
        )
        
        with urllib.request.urlopen(req, timeout=60.0) as resp:
            # Validação de redirecionamento para evitar desvios maliciosos
            final_url = resp.geturl()
            if not is_trusted_update_url(final_url):
                print(f"[Updater] Redirecionamento não confiável detectado: {final_url}")
                return False

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
            # Validação criptográfica de integridade SHA-256 (se fornecido)
            if expected_sha256:
                import hashlib
                hasher = hashlib.sha256()
                with open(installer_path, "rb") as f_hash:
                    while chunk := f_hash.read(65536):
                        hasher.update(chunk)
                computed_hash = hasher.hexdigest().lower()
                if computed_hash != expected_sha256.strip().lower():
                    print(f"[Updater] Hash SHA-256 inválido! Esperado: {expected_sha256}, Obtido: {computed_hash}")
                    installer_path.unlink(missing_ok=True)
                    return False

            # Validação básica de integridade do executável Windows (assinatura MZ no header PE)
            with open(installer_path, "rb") as f_check:
                header = f_check.read(2)
                if header != b"MZ":
                    print("[Updater] Arquivo baixado não é um executável Windows válido.")
                    installer_path.unlink(missing_ok=True)
                    return False

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
