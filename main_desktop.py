#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ponto de Entrada Desktop do Nexo Download - Mídia Digital Livre.
Versão Blindada: Suporte completo a execução sem console (Windows GUI),
desativação de formatadores conflitantes do Uvicorn e ciclo de vida sincronizado.
"""

import os
import sys
import asyncio
import time
import socket
import threading
import urllib.request
from pathlib import Path
from typing import Optional

# 1. Blindagem contra ausência de console no Windows (evita NoneType.isatty())
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# 2. Prevenção de crash no Windows por desconexão de sockets (WinError 10054 / Proactor)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Determina o diretório base (lidando com modo congelado PyInstaller)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    internal_dir = BASE_DIR / "_internal"
    if internal_dir.exists():
        sys.path.insert(0, str(internal_dir))
else:
    BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

# Importações principais de dependências
import uvicorn
from web_app.app import app

# Adiciona diretórios de binários internos (FFmpeg) ao PATH
bin_candidates = [
    BASE_DIR,
    BASE_DIR / "_internal",
    BASE_DIR / "_internal" / "bin",
    BASE_DIR / "bin"
]
for b in bin_candidates:
    if b.exists() and str(b) not in os.environ.get("PATH", ""):
        os.environ["PATH"] = str(b) + os.path.pathsep + os.environ.get("PATH", "")

# Suporte a UTF-8 no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def find_free_port(start_port: int = 8769) -> int:
    """Localiza uma porta TCP disponível."""
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    return start_port


def start_server(host: str, port: int):
    """Inicia o servidor FastAPI local com Uvicorn sem logging com cores."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        config = uvicorn.Config(
            app=app,
            host=host,
            port=port,
            log_config=None,  # Evita crash do formatador default em modo sem console
            log_level="critical",
            access_log=False,
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        server.run()
    except Exception as e:
        err_log = BASE_DIR / "nexo_error.log"
        with open(err_log, "a", encoding="utf-8") as f:
            import traceback
            f.write(f"Erro em start_server: {e}\n")
            traceback.print_exc(file=f)


def wait_for_server_ready(url: str, timeout: float = 15.0) -> bool:
    """Aguarda confirmação síncrona de status 200 do servidor antes de abrir a janela."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(f"{url}/api/lifecycle", headers={"User-Agent": "NexoHealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def launch_native_webview(app_url: str, icon_path: Path):
    """
    Cria a janela Windows nativa com o motor Microsoft Edge WebView2.
    """
    import webview
    
    window = webview.create_window(
        title="Nexo Download - Mídia Digital Livre",
        url=app_url,
        width=1220,
        height=840,
        min_size=(980, 660),
        resizable=True,
        text_select=True,
        confirm_close=False
    )
    
    icon_arg = str(icon_path) if icon_path.exists() else None
    webview.start(icon=icon_arg, debug=False)


def fallback_browser_mode(app_url: str):
    """Fallback seguro caso o WebView2 nativo não esteja acessível."""
    import webbrowser
    webbrowser.open(app_url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def main():
    host = "127.0.0.1"
    port = find_free_port(8769)
    app_url = f"http://{host}:{port}"
    
    # Localiza ícone oficial
    icon_candidates = [
        BASE_DIR / "web_app" / "static" / "icons" / "app_icon.ico",
        BASE_DIR / "_internal" / "web_app" / "static" / "icons" / "app_icon.ico",
        BASE_DIR / "app_icon.ico"
    ]
    icon_path = next((ic for ic in icon_candidates if ic.exists()), icon_candidates[0])

    # 1. Inicia backend FastAPI em thread separada
    server_thread = threading.Thread(target=start_server, args=(host, port), daemon=True)
    server_thread.start()

    # 2. Confirma prontidão do servidor antes de exibir a interface
    ready = wait_for_server_ready(app_url, timeout=15.0)
    if not ready:
        sys.exit(1)

    # 3. Lança Janela Nativa com WebView2
    try:
        launch_native_webview(app_url, icon_path)
    except Exception:
        fallback_browser_mode(app_url)

    # 4. Encerramento limpo
    os._exit(0)


if __name__ == "__main__":
    main()