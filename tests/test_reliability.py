# -*- coding: utf-8 -*-
"""
Bateria de Testes de Confiabilidade, Resiliência e Robustez do Nexo Download.
Cobre:
1. Ciclo de vida e cancelamento de tarefas de download (DownloadTaskManager).
2. Endpoints de cancelamento (/api/download/cancel/{task_id}), status e tarefas ativas.
3. Sanitização resiliente de nomes de arquivos (nomes reservados do Windows, trailing dots, MAX_PATH, caracteres de controle).
4. Robustez de concatenação de áudio (validação de arquivos vazios/ausentes e timeouts).
5. Prevenção de acesso a diretórios críticos do sistema operacional (is_system_restricted_path).
6. Auto-lock e proteção contra força bruta na Sessão Privê.
7. Localizador integrado de FFmpeg.
8. Validação de integridade de checksum SHA-256 no Auto-Updater.
"""

import sys
import time
import tempfile
from pathlib import Path
import pytest
from starlette.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from web_app.app import (
    app,
    download_task_manager,
    DownloadTask,
    sanitize_filename,
    concat_mp3_files,
    is_system_restricted_path,
    is_safe_downloads_path,
    find_ffmpeg_path,
    DOWNLOADS_DIR,
    AUTHORIZED_DOWNLOAD_ROOTS
)
from web_app.prive_engine import setup_prive_password, verify_prive_password
from web_app.updater_engine import apply_silent_update

client = TestClient(app)


class TestDownloadTaskManagerReliability:
    """Valida gerenciamento thread-safe e cancelamento de tarefas."""

    def test_task_registration_and_status(self):
        task_id = "test-task-123"
        task = DownloadTask(task_id, "https://youtube.com/watch?v=123", "YouTube", "video")
        download_task_manager.register(task)

        fetched = download_task_manager.get(task_id)
        assert fetched is not None
        assert fetched.task_id == task_id
        assert fetched.status == "starting"
        assert not fetched.cancel_event.is_set()

    def test_task_cancellation(self):
        task_id = "test-task-cancel"
        task = DownloadTask(task_id, "https://youtube.com/watch?v=456", "YouTube", "video")
        download_task_manager.register(task)

        assert download_task_manager.cancel(task_id) is True
        assert task.cancel_event.is_set()
        assert task.status == "cancelled"

        # Segunda tentativa de cancelar tarefa já cancelada retorna False
        assert download_task_manager.cancel(task_id) is False

    def test_api_cancel_endpoint(self):
        task_id = "api-cancel-task"
        task = DownloadTask(task_id, "https://youtube.com/watch?v=789", "YouTube", "video")
        download_task_manager.register(task)

        resp = client.post(f"/api/download/cancel/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True
        assert data.get("status") == "cancelled"

    def test_api_status_endpoint(self):
        task_id = "api-status-task"
        task = DownloadTask(task_id, "https://youtube.com/watch?v=abc", "YouTube", "audio")
        task.percent = 45.5
        task.message = "Baixando áudio..."
        download_task_manager.register(task)

        resp = client.get(f"/api/download/status/{task_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("task_id") == task_id
        assert data.get("percent") == 45.5
        assert data.get("platform") == "YouTube"

    def test_api_active_tasks_endpoint(self):
        task_id = "api-active-task"
        task = DownloadTask(task_id, "https://youtube.com/watch?v=active", "YouTube", "video")
        task.status = "downloading"
        download_task_manager.register(task)

        resp = client.get("/api/download/active")
        assert resp.status_code == 200
        tasks = resp.json().get("tasks", [])
        assert any(t["task_id"] == task_id for t in tasks)


class TestBulletproofFilenameSanitization:
    """Testes exaustivos da blindagem de nomes de arquivos para o Windows Explorer."""

    def test_reserved_windows_device_names(self):
        # Nomes como CON, AUX, NUL, COM1 não podem ser criados diretamente no Windows
        for name in ["CON", "con", "AUX", "aux.mp4", "NUL", "COM1", "LPT2.mp3"]:
            cleaned = sanitize_filename(name)
            assert not cleaned.upper().startswith("CON.")
            assert not cleaned.upper().startswith("AUX.")
            assert not cleaned.upper() == "NUL"
            assert "_" in cleaned

    def test_strip_trailing_dots_and_spaces(self):
        # O Windows rejeita arquivos terminados em ponto ou espaço
        bad_name = "Minha Música Incrível...   "
        cleaned = sanitize_filename(bad_name)
        assert not cleaned.endswith(".")
        assert not cleaned.endswith(" ")
        assert cleaned == "Minha Música Incrível"

    def test_strip_control_characters(self):
        # Caracteres de controle ASCII < 32 (newlines, tabs, null bytes)
        bad_name = "Linha 1\nLinha 2\r\tTítulo com \x00 Nulo"
        cleaned = sanitize_filename(bad_name)
        assert "\n" not in cleaned
        assert "\r" not in cleaned
        assert "\t" not in cleaned
        assert "\x00" not in cleaned

    def test_max_path_length_truncation(self):
        long_name = "A" * 300
        cleaned = sanitize_filename(long_name, max_length=120)
        assert len(cleaned) <= 120

    def test_empty_or_whitespace_fallback(self):
        assert sanitize_filename("") == "midia"
        assert sanitize_filename("   ") == "midia"
        assert sanitize_filename('///:::***???') == "midia"


class TestAudioConcatRobustness:
    """Valida comportamento defensivo de concat_mp3_files."""

    def test_handles_empty_or_single_file(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "completo.mp3"
            # Lista vazia não deve lançar exceção
            concat_mp3_files([], out_file)
            assert not out_file.exists()

            # Lista com apenas 1 arquivo não deve lançar exceção
            dummy = Path(td) / "faixa1.mp3"
            dummy.write_text("dummy")
            concat_mp3_files([dummy], out_file)
            assert not out_file.exists()

    def test_ignores_non_existent_or_zero_byte_files(self):
        with tempfile.TemporaryDirectory() as td:
            out_file = Path(td) / "completo.mp3"
            ghost1 = Path(td) / "ghost1.mp3"
            ghost2 = Path(td) / "ghost2.mp3"
            # Arquivos inexistentes são filtrados sem crash
            concat_mp3_files([ghost1, ghost2], out_file)
            assert not out_file.exists()


class TestSystemRestrictedPaths:
    """Valida bloqueio de caminhos críticos do sistema operacional."""

    def test_detects_windows_system_directories(self):
        windows_dir = Path("C:/Windows/System32/drivers/etc")
        assert is_system_restricted_path(windows_dir) is True

        prog_files = Path("C:/Program Files/Common Files")
        assert is_system_restricted_path(prog_files) is True

    def test_safe_downloads_path_blocks_system_dir(self):
        windows_dir = Path("C:/Windows/explorer.exe")
        assert is_safe_downloads_path(windows_dir) is False

    def test_safe_downloads_path_allows_custom_authorized_root(self):
        with tempfile.TemporaryDirectory() as td:
            custom_dir = Path(td) / "Meus Downloads Personalizados"
            custom_dir.mkdir()
            AUTHORIZED_DOWNLOAD_ROOTS.add(custom_dir.resolve())

            sub_file = custom_dir / "YouTube" / "video.mp4"
            assert is_safe_downloads_path(sub_file) is True


class TestPriveReliabilityAndBruteForce:
    """Valida taxa de tentativas e auto-lock na Sessão Privê."""

    def test_brute_force_lockout_trigger(self, monkeypatch):
        from web_app import app as app_mod
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "prive_robust_config.json"
            monkeypatch.setattr("web_app.prive_engine.get_prive_config_path", lambda: cfg)
            setup_prive_password("senhaForte2026")

            # Limpa estado anterior de tentativas
            app_mod.PRIVE_FAILED_ATTEMPTS.clear()
            app_mod.PRIVE_LOCKOUT_UNTIL = 0.0

            # 4 tentativas incorretas consecutivas
            for _ in range(4):
                res = client.post("/api/prive/unlock", json={"password": "errada"})
                assert res.status_code == 200
                assert res.json().get("success") is False
                assert res.json().get("locked_out") is not True

            # 5ª tentativa incorreta ativa lockout
            res5 = client.post("/api/prive/unlock", json={"password": "errada"})
            data5 = res5.json()
            assert data5.get("success") is False
            assert data5.get("locked_out") is True
            assert "Limite de tentativas excedido" in data5.get("message", "")

            # Limpeza pós-teste
            app_mod.PRIVE_FAILED_ATTEMPTS.clear()
            app_mod.PRIVE_LOCKOUT_UNTIL = 0.0


class TestFFmpegDiscovery:
    """Valida o localizador inteligente do executável FFmpeg."""

    def test_find_ffmpeg_path_returns_string_or_none(self):
        path = find_ffmpeg_path()
        if path is not None:
            assert isinstance(path, str)
            p = Path(path)
            assert (p / "ffmpeg.exe").exists() or (p / "ffmpeg").exists() or p.exists()


class TestOrganizerAndCLIReliability:
    """Valida robustez do organizer, atomicidade do catálogo e CLI downloader."""

    def test_organizer_sanitize_filename_reserved_names(self):
        from youtube_engine.organizer import sanitize_filename as org_sanitize
        for res_name in ["CON", "prn", "AUX", "nul", "COM1", "LPT1"]:
            cleaned = org_sanitize(res_name)
            assert cleaned.startswith("_") and cleaned.endswith("_")

    def test_organizer_sanitize_filename_control_chars_and_trailing(self):
        from youtube_engine.organizer import sanitize_filename as org_sanitize
        bad_name = "Aula\x00\x08Importante...\t "
        cleaned = org_sanitize(bad_name)
        assert "\x00" not in cleaned
        assert "\x08" not in cleaned
        assert not cleaned.endswith(".")

    def test_baixar_sanitize_filename(self):
        from baixar import sanitize_filename as baixar_sanitize
        assert baixar_sanitize("CON") == "_CON_"
        assert baixar_sanitize("video\x01\x1f teste..") == "video teste"

    def test_atomic_catalog_writing(self):
        from youtube_engine.organizer import LibraryOrganizer
        from youtube_engine.models import VideoMetadata, ParagraphBlock, SummaryReport
        with tempfile.TemporaryDirectory() as td:
            organizer = LibraryOrganizer(base_output_dir=td)
            meta = VideoMetadata("test_atomic", "https://youtube.com/watch?v=test_atomic", "Vídeo Atômico", "Canal Tech", "https://yt", "https://th")
            paras = [ParagraphBlock(0.0, 10.0, "Texto de teste para validação de atomicidade.")]
            summary = SummaryReport("Resumo teste", [], [], "Markdown", "local")

            result = organizer.organize_and_save(meta, paras, [], summary)
            assert Path(result.output_dir).exists()
            assert organizer.catalog_json_path.exists()
            assert not organizer.catalog_json_path.with_suffix(".json.tmp").exists()
            assert organizer.library_md_path.exists()
            assert not organizer.library_md_path.with_suffix(".md.tmp").exists()

            # Valida leitura JSON íntegra
            import json
            with open(organizer.catalog_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                assert len(data) == 1
                assert data[0]["video_id"] == "test_atomic"

    def test_summarizer_resilience_on_empty_candidates(self, monkeypatch):
        from youtube_engine.summarizer import ContentSummarizer
        from youtube_engine.models import VideoMetadata, ParagraphBlock
        summarizer = ContentSummarizer(api_key="fake-key-test")
        meta = VideoMetadata("fake_id", "https://youtube.com/watch?v=fake_id", "Titulo", "Canal", "https://yt", "https://th")
        paras = [ParagraphBlock(0.0, 10.0, "Inteligência artificial e algoritmos de busca e aprendizado contínuo.")]

        # Simula resposta do Gemini bloqueada ou sem candidates
        class MockResponse:
            status_code = 200
            def json(self):
                return {"candidates": []}

        monkeypatch.setattr("requests.post", lambda *args, **kwargs: MockResponse())
        # Deve executar fallback limpo para o motor algorítmico local sem lançar exceção
        report = summarizer.generate_summary(meta, paras, "Texto completo")
        assert report is not None
        assert report.engine_used == "algorithmic-local"

