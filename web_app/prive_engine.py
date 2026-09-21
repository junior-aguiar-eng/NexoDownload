# -*- coding: utf-8 -*-
"""
Nexo Download - Motor da Sessão Privê (18+ / Conteúdo Adulto Protegido)
Gerenciamento seguro de senha (SHA-256 + Salt), persistência em AppData,
isolamento de pastas em disco e validação de URLs do XVideos.
"""

import os
import sys
import json
import hashlib
import secrets
import re
from pathlib import Path
from typing import Dict, Any, Optional

def get_app_data_dir() -> Path:
    """Retorna o diretório de dados em AppData/Roaming."""
    base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "NexoDownload"
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_prive_config_path() -> Path:
    """Caminho do arquivo de configuração da Sessão Privê."""
    return get_app_data_dir() / "prive_config.json"

def _hash_password(password: str, salt: str) -> str:
    """Gera hash SHA-256 da senha com salt."""
    salted = f"{salt}:{password}:{salt}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()

def is_prive_configured() -> bool:
    """Verifica se o usuário já cadastrou uma senha para a Sessão Privê."""
    cfg_file = get_prive_config_path()
    if not cfg_file.exists():
        return False
    try:
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        return bool(data.get("password_hash") and data.get("salt"))
    except Exception:
        return False

def setup_prive_password(password: str) -> bool:
    """Cadastra a senha da Sessão Privê (primeiro uso ou redefinição)."""
    password = password.strip()
    if len(password) < 4:
        return False
    
    salt = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt)
    
    config_data = {
        "password_hash": pwd_hash,
        "salt": salt,
        "created_at": str(os.times()[4])
    }
    
    try:
        cfg_file = get_prive_config_path()
        cfg_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[PriveEngine] Erro ao salvar senha: {e}")
        return False

def verify_prive_password(password: str) -> bool:
    """Valida a senha digitada pelo usuário."""
    cfg_file = get_prive_config_path()
    if not cfg_file.exists():
        return False
    try:
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        stored_hash = data.get("password_hash")
        salt = data.get("salt")
        if not stored_hash or not salt:
            return False
        
        computed_hash = _hash_password(password.strip(), salt)
        return secrets.compare_digest(stored_hash, computed_hash)
    except Exception as e:
        print(f"[PriveEngine] Erro na validação: {e}")
        return False

def reset_prive_password() -> bool:
    """
    Redefine a Sessão Privê (Zero-Knowledge).
    Remove o arquivo de credenciais sem deletar nenhum vídeo baixado no disco.
    """
    cfg_file = get_prive_config_path()
    if cfg_file.exists():
        try:
            cfg_file.unlink()
            return True
        except Exception as e:
            print(f"[PriveEngine] Erro ao redefinir: {e}")
            return False
    return True

def get_prive_download_folder(base_folder: Path) -> Path:
    """
    Retorna e garante a existência da subpasta dedicada 'Privê'
    dentro do diretório de downloads configurado pelo usuário.
    """
    prive_folder = base_folder / "Privê"
    prive_folder.mkdir(parents=True, exist_ok=True)
    return prive_folder

def is_xvideos_url(url: str) -> bool:
    """Detecta se a URL fornecida pertence ao domínio do XVideos."""
    url_l = url.lower()
    return "xvideos.com" in url_l or "xvideos.com.br" in url_l or "xvideos" in url_l

def sanitize_prive_title(title: str) -> str:
    """Limpa caracteres proibidos pelo Windows e limita tamanho para evitar erros de I/O."""
    if not title:
        return "Video_Prive"
    # Remove caracteres inválidos no Windows: \ / : * ? " < > |
    clean = re.sub(r'[\\/*?:"<>|]', "", title)
    clean = re.sub(r'\s+', " ", clean).strip()
    return clean[:120] if len(clean) > 120 else clean
