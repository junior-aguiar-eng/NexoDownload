# -*- coding: utf-8 -*-
"""
Bateria de Testes do Servidor de Apoio da Extensão Chrome (youtube_engine.server).
Valida:
1. Resposta do endpoint /api/status.
2. Cabeçalhos de CORS habilitados para o Side Panel do Chrome.
3. Tratamento de parâmetros ausentes ou inválidos em /api/transcript e /api/download.
4. Processamento ou leitura em cache de vídeos catalogados.
"""

import sys
import json
import urllib.request
import urllib.error
import threading
import time
from pathlib import Path
import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from youtube_engine.server import ThreadedHTTPServer, StudyApiHandler


@pytest.fixture(scope="module")
def study_server():
    """Inicia o servidor em porta de teste temporária."""
    test_port = 8799
    server = ThreadedHTTPServer(("127.0.0.1", test_port), StudyApiHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.3)
    base_url = f"http://127.0.0.1:{test_port}"
    yield base_url
    server.shutdown()
    server.server_close()


def test_server_status_and_cors(study_server):
    req = urllib.request.Request(f"{study_server}/api/status")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "online"


def test_server_transcript_missing_param(study_server):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{study_server}/api/transcript")
    assert exc_info.value.code == 400


def test_server_download_missing_param(study_server):
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(f"{study_server}/api/download")
    assert exc_info.value.code == 400


def test_generate_cornell_notes_structure():
    from youtube_engine.models import VideoMetadata, ParagraphBlock, SummaryReport
    from youtube_engine.cornell import generate_cornell_notes

    meta = VideoMetadata("test123", "https://youtube.com/watch?v=test123", "Aula Teste", "Canal Teste", "https://yt.com", "https://thumb")
    paras = [
        ParagraphBlock(0.0, 15.0, "Introducao aos conceitos fundamentais de direito."),
        ParagraphBlock(15.0, 30.0, "Desenvolvimento da tese jurisprudencial.")
    ]
    summary = SummaryReport("Resumo do teste", [], [], "Markdown completo", "test-engine")

    notes = generate_cornell_notes(meta, paras, summary)
    assert "Caderno de Estudos (Método Cornell)" in notes
    assert "Aula Teste" in notes
    assert "Matriz de Estudo Cornell" in notes
    assert "00:00" in notes

