# -*- coding: utf-8 -*-
"""
Bateria de Testes de Integração e Rotas da API FastAPI do Nexo Download.
Valida:
1. Bloqueio de origens externas no CORS e Middleware de Segurança Local.
2. Rejeição de URLs não confiáveis no /api/apply-update.
3. Bloqueio de Path Traversal e Executáveis no /api/open-file.
4. Resposta das rotas de ciclo de vida e diretório de downloads.
"""

import sys
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
try:
    from starlette.exceptions import StarletteDeprecationWarning
    warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)
except (ImportError, AttributeError):
    pass
from starlette.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from web_app.app import app, DOWNLOADS_DIR

client = TestClient(app)


class TestAPISecurity:
    """Testes de segurança das rotas HTTP."""

    def test_lifecycle_endpoint(self):
        response = client.get("/api/lifecycle")
        assert response.status_code == 200
        data = response.json()
        assert "connected_ever" in data

    def test_downloads_dir_endpoint(self):
        response = client.get("/api/downloads-dir")
        assert response.status_code == 200
        assert "path" in response.json()

    def test_apply_update_rejects_untrusted_url(self):
        payload = {"download_url": "https://malicious-site.com/trojan.exe"}
        response = client.post("/api/apply-update", json=payload)
        assert response.status_code == 400
        assert "não autorizada" in response.json().get("detail", "")

    def test_open_file_rejects_empty_path(self):
        response = client.post("/api/open-file", json={"file_path": ""})
        assert response.status_code == 400

    def test_open_file_rejects_path_traversal(self):
        # Tenta escapar da pasta de downloads
        traversal_file = str(DOWNLOADS_DIR / ".." / "outside.txt")
        response = client.post("/api/open-file", json={"file_path": traversal_file})
        assert response.status_code in [403, 404]

    def test_open_file_blocks_executable_file(self, monkeypatch):
        # Simula um executável colocado dentro da pasta de downloads
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            monkeypatch.setattr("web_app.app.DOWNLOADS_DIR", temp_dir)
            fake_exe = temp_dir / "payload.exe"
            fake_exe.write_text("fake binary")

            response = client.post("/api/open-file", json={"file_path": str(fake_exe)})
            assert response.status_code == 403
            assert "não é permitida por motivos de segurança" in response.json().get("detail", "")

    def test_local_security_middleware_rejects_external_origin(self):
        # Simula requisição POST vinda de uma aba com site externo
        headers = {"Origin": "https://malicious-website.com"}
        response = client.post("/api/heartbeat", headers=headers)
        assert response.status_code == 403
        assert "Acesso externo não autorizado" in response.text

    def test_local_security_middleware_allows_localhost_origin(self):
        headers = {"Origin": "http://127.0.0.1:8769"}
        response = client.post("/api/heartbeat", headers=headers)
        assert response.status_code == 200
