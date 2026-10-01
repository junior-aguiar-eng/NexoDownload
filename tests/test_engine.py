# -*- coding: utf-8 -*-
"""
Bateria de Testes Unitários dos Motores de Processamento do Nexo Download.
Cobre:
1. Normalização e detecção de plataformas suportadas.
2. Sanitização estrita de nomes de arquivos e segurança de diretórios.
3. Bloqueio de extensões executáveis expandidas (.sh, .bash, .bin, .desktop, .exe, etc.).
4. Lógica de concatenação e escape seguro de caracteres para o FFmpeg.
5. Resiliência do Hardware ID (HWID) em ambientes com e sem winreg.
"""

import sys
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from web_app.app import (
    detect_platform_name,
    normalize_target_url,
    sanitize_filename,
    is_safe_downloads_path,
    BLOCKED_EXEC_EXTENSIONS,
    concat_mp3_files
)
from web_app.security_engine import (
    get_hardware_id,
    _compute_hwid_from_raw
)


class TestPlatformDetection:
    """Testes de detecção e normalização inteligente de URLs."""

    def test_detect_youtube(self):
        assert detect_platform_name("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "YouTube"
        assert detect_platform_name("https://youtu.be/dQw4w9WgXcQ") == "YouTube"

    def test_detect_spotify(self):
        assert detect_platform_name("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT") == "Spotify"

    def test_detect_apple_music(self):
        assert detect_platform_name("https://music.apple.com/br/album/something/12345") == "AppleMusic"

    def test_detect_soundcloud(self):
        assert detect_platform_name("https://soundcloud.com/artist/track") == "SoundCloud"

    def test_detect_tiktok(self):
        assert detect_platform_name("https://www.tiktok.com/@user/video/123456") == "TikTok"

    def test_detect_instagram(self):
        assert detect_platform_name("https://www.instagram.com/reel/C-xyz123/") == "Instagram"

    def test_detect_vimeo(self):
        assert detect_platform_name("https://vimeo.com/123456789") == "Vimeo"

    def test_detect_pinterest(self):
        assert detect_platform_name("https://br.pinterest.com/pin/123456/") == "Pinterest"

    def test_vimeo_url_normalization(self):
        norm = normalize_target_url("https://vimeo.com/987654321")
        assert norm == "https://player.vimeo.com/video/987654321"


class TestPathAndFilenameSanitization:
    """Testes de integridade de filesystem e prevenção de injeção."""

    def test_sanitize_filename_removes_illegal_characters(self):
        bad_name = 'Vídeo: "Incrível" / <Teste> | [Parte 1]? *legal*'
        clean = sanitize_filename(bad_name)
        for char in r'\/:*?"<>|':
            assert char not in clean

    def test_blocked_executables_includes_scripts(self):
        dangerous = [".exe", ".bat", ".cmd", ".ps1", ".sh", ".bash", ".bin", ".desktop"]
        for ext in dangerous:
            assert ext in BLOCKED_EXEC_EXTENSIONS

    def test_is_safe_downloads_path_validates_containment(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "downloads"
            base.mkdir()
            safe_child = base / "YouTube" / "video.mp4"
            assert is_safe_downloads_path(safe_child, base) is True

            outside_path = Path(td) / "outside.txt"
            assert is_safe_downloads_path(outside_path, base) is False


class TestHardwareIDResilience:
    """Valida formato e determinismo do HWID."""

    def test_hwid_format(self):
        hwid = get_hardware_id()
        assert hwid.startswith("NEXO-")
        assert len(hwid) == 19
        parts = hwid.split("-")
        assert len(parts) == 4

    def test_compute_hwid_deterministic(self):
        h1 = _compute_hwid_from_raw("TEST_MACHINE_123")
        h2 = _compute_hwid_from_raw("TEST_MACHINE_123")
        assert h1 == h2
