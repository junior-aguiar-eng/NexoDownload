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

from datetime import datetime, timezone

PBKDF2_ITERATIONS = 200_000

def _hash_password_pbkdf2(password: str, salt: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Gera hash criptográfico robusto utilizando PBKDF2-HMAC-SHA256."""
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations
    )
    return key.hex()

def _legacy_hash_password(password: str, salt: str) -> str:
    """Suporte retroativo ao hash legado de iteração única."""
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
    """Cadastra a senha da Sessão Privê com PBKDF2-HMAC-SHA256."""
    password = password.strip()
    if len(password) < 4:
        return False
    
    salt = secrets.token_hex(16)
    pwd_hash = _hash_password_pbkdf2(password, salt)
    
    config_data = {
        "algorithm": "pbkdf2_sha256",
        "iterations": PBKDF2_ITERATIONS,
        "password_hash": pwd_hash,
        "salt": salt,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        cfg_file = get_prive_config_path()
        cfg_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        print(f"[PriveEngine] Erro ao salvar senha: {e}")
        return False

def verify_prive_password(password: str) -> bool:
    """
    Valida a senha digitada pelo usuário.
    Se o hash for do padrão legado (SHA-256 simples), faz upgrade transparente para PBKDF2.
    """
    cfg_file = get_prive_config_path()
    if not cfg_file.exists():
        return False
    try:
        data = json.loads(cfg_file.read_text(encoding="utf-8"))
        stored_hash = data.get("password_hash")
        salt = data.get("salt")
        if not stored_hash or not salt:
            return False

        clean_pwd = password.strip()
        algo = data.get("algorithm")

        if algo == "pbkdf2_sha256":
            iterations = data.get("iterations", PBKDF2_ITERATIONS)
            computed_hash = _hash_password_pbkdf2(clean_pwd, salt, iterations)
            return secrets.compare_digest(stored_hash, computed_hash)
        else:
            # Hash legado: valida e migra automaticamente para PBKDF2
            computed_legacy = _legacy_hash_password(clean_pwd, salt)
            if secrets.compare_digest(stored_hash, computed_legacy):
                setup_prive_password(clean_pwd)
                return True
            return False
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
