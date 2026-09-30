# -*- coding: utf-8 -*-
"""
Bateria de Testes Automatizados de Segurança e Blindagem do Nexo Download.
Valida:
1. Whitelist e prevenção de RCE no Auto-Updater.
2. Prevenção de Path Traversal e bloqueio de executáveis em arquivos/pastas.
3. Hashing robusto PBKDF2 na Sessão Privê e migração retroativa.
4. Validação e formato de chaves de licença HWID.
"""

import os
import sys
import tempfile
from pathlib import Path
import pytest

# Adiciona diretório raiz ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from web_app.updater_engine import is_trusted_update_url
from web_app.app import is_safe_downloads_path, BLOCKED_EXEC_EXTENSIONS
from web_app.prive_engine import (
    _hash_password_pbkdf2,
    _legacy_hash_password,
    setup_prive_password,
    verify_prive_password,
    reset_prive_password,
    get_prive_config_path
)
from web_app.security_engine import (
    generate_license_key,
    verify_license_key,
    get_hardware_id
)


class TestUpdaterSecurity:
    """Testes de blindagem contra Remote Code Execution (RCE) no auto-updater."""

    def test_trusted_official_github_releases(self):
        valid_url = "https://github.com/junior-aguiar-eng/NexoDownload/releases/download/v2.1.0/NexoDownload-Setup.exe"
        assert is_trusted_update_url(valid_url) is True

    def test_trusted_github_objects_cdn(self):
        valid_cdn = "https://objects.githubusercontent.com/github-production-release-asset-2e6500/xyz"
        assert is_trusted_update_url(valid_cdn) is True

    def test_reject_insecure_http(self):
        http_url = "http://github.com/junior-aguiar-eng/NexoDownload/releases/download/v2.1.0/Setup.exe"
        assert is_trusted_update_url(http_url) is False

    def test_reject_external_attacker_domain(self):
        malicious_url = "https://attacker-server.com/malware.exe"
        assert is_trusted_update_url(malicious_url) is False

    def test_reject_different_github_repo(self):
        other_repo = "https://github.com/another-user/malicious-repo/releases/download/v1.0/trojan.exe"
        assert is_trusted_update_url(other_repo) is False

    def test_reject_empty_or_invalid_urls(self):
        assert is_trusted_update_url("") is False
        assert is_trusted_update_url(None) is False
        assert is_trusted_update_url("javascript:alert(1)") is False


class TestFilesystemSecurity:
    """Testes de contenção de arquivos e prevenção de execução arbitrária."""

    def test_safe_path_inside_downloads(self):
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td) / "downloads"
            base_dir.mkdir()
            sub_folder = base_dir / "YouTube"
            sub_folder.mkdir()
            file_path = sub_folder / "video.mp4"
            file_path.write_text("dummy")

            assert is_safe_downloads_path(file_path, base_dir) is True
            assert is_safe_downloads_path(sub_folder, base_dir) is True
            assert is_safe_downloads_path(base_dir, base_dir) is True

    def test_reject_path_traversal(self):
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td) / "downloads"
            base_dir.mkdir()
            system_file = Path(td) / "system_secret.txt"
            system_file.write_text("secret")

            traversal_path = base_dir / ".." / "system_secret.txt"
            assert is_safe_downloads_path(traversal_path, base_dir) is False

    def test_reject_windows_system_paths(self):
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td) / "downloads"
            base_dir.mkdir()
            windows_path = Path("C:/Windows/System32/cmd.exe")
            assert is_safe_downloads_path(windows_path, base_dir) is False

    def test_blocked_executable_extensions(self):
        assert ".exe" in BLOCKED_EXEC_EXTENSIONS
        assert ".bat" in BLOCKED_EXEC_EXTENSIONS
        assert ".cmd" in BLOCKED_EXEC_EXTENSIONS
        assert ".ps1" in BLOCKED_EXEC_EXTENSIONS
        assert ".msi" in BLOCKED_EXEC_EXTENSIONS
        assert ".vbs" in BLOCKED_EXEC_EXTENSIONS
        assert ".mp4" not in BLOCKED_EXEC_EXTENSIONS
        assert ".mp3" not in BLOCKED_EXEC_EXTENSIONS


class TestPriveEngineSecurity:
    """Testes do motor privê e hashing seguro de senhas."""

    def test_pbkdf2_hash_different_salts(self):
        h1 = _hash_password_pbkdf2("minha_senha_123", "salt_alpha", iterations=1000)
        h2 = _hash_password_pbkdf2("minha_senha_123", "salt_beta", iterations=1000)
        assert h1 != h2
        assert len(h1) == 64  # SHA-256 hex digest length

    def test_setup_and_verify_password(self, monkeypatch):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "prive_test_config.json"
            monkeypatch.setattr("web_app.prive_engine.get_prive_config_path", lambda: cfg)

            assert setup_prive_password("segredo2026") is True
            assert cfg.exists()

            assert verify_prive_password("segredo2026") is True
            assert verify_prive_password("senha_errada") is False

    def test_reject_short_password(self):
        assert setup_prive_password("123") is False


class TestLicenseSecurity:
    """Testes de integridade do licenciamento HWID."""

    def test_license_lifecycle_and_validation(self):
        hwid = get_hardware_id()
        assert hwid.startswith("NEXO-")

        key = generate_license_key(hwid, exp_type="LIFETIME")
        assert key.startswith("NEXO-9999-1231-")

        val = verify_license_key(key, hwid)
        assert val.get("valid") is True
        assert val.get("plan") == "Licença Vitalícia (Permanente)"

    def test_reject_tampered_key(self):
        hwid = get_hardware_id()
        key = generate_license_key(hwid, exp_type="LIFETIME")
        tampered_key = key[:-4] + "ABCD"
        val = verify_license_key(tampered_key, hwid)
        assert val.get("valid") is False
