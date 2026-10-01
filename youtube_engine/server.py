"""
Servidor HTTP de API Local para Extensão Chrome e Study Player.
Padrão de Engenharia Google: Ultra-leve, assíncrono com ThreadingHTTPServer e CORS nativo.
"""

import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from typing import Optional

# Garante suporte UTF-8 no console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from .url_parser import extract_video_id
from .metadata import fetch_video_metadata
from .transcriber import TranscriptionEngine
from .paragrapher import build_semantic_paragraphs
from .summarizer import ContentSummarizer
from .organizer import LibraryOrganizer
from .cornell import generate_cornell_notes
from .study_player import generate_study_player_html
from .downloader import download_media


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Servidor HTTP multi-thread para requisições concorrentes sem bloqueio."""
    daemon_threads = True


class StudyApiHandler(SimpleHTTPRequestHandler):
    """Manipulador de requisições REST da API de estudos com suporte a CORS."""

    base_dir = Path("transcricoes").resolve()

    def end_headers(self):
        # Habilita CORS completo para extensões do Chrome e páginas web locais
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # 1. Endpoint de Verificação de Saúde
        if path == "/api/status":
            self._send_json({"status": "online", "version": "1.0.0", "message": "Motor de Estudos Google Ativo"})
            return

        # 2. Endpoint de Transcrição e Estudos para a Extensão do Chrome
        if path == "/api/transcript":
            video_param = params.get("v", [None])[0] or params.get("url", [None])[0]
            engine_param = params.get("engine", ["auto"])[0]
            gemini_key = params.get("key", [None])[0] or os.getenv("GEMINI_API_KEY")

            if not video_param:
                self._send_error(400, "Parâmetro 'v' ou 'url' ausente.")
                return

            video_id = extract_video_id(video_param)
            if not video_id:
                self._send_error(400, f"Identificador de vídeo inválido: {video_param}")
                return

            try:
                data = self._process_or_get_video(video_id, engine_pref=engine_param, gemini_key=gemini_key)
                self._send_json(data)
            except Exception as e:
                err_msg = str(e)
                self._send_error(500, f"Erro ao processar vídeo: {err_msg}")
            return

        # 3. Endpoint de Download de Vídeo (MP4) ou Áudio (M4A/MP3)
        if path == "/api/download":
            video_param = params.get("v", [None])[0] or params.get("url", [None])[0]
            media_type = params.get("type", ["video"])[0]
            video_id = extract_video_id(video_param)
            if not video_id:
                self._send_error(400, "Parâmetro 'v' ou 'url' ausente.")
                return

            try:
                # Localiza ou processa os metadados do vídeo
                info = self._process_or_get_video(video_id)
                target_dir = self._find_video_dir(video_id)
                file_path = download_media(video_id, str(target_dir), media_type=media_type)
                self._send_json({
                    "success": True,
                    "filename": os.path.basename(file_path),
                    "file_path": file_path,
                    "type": media_type
                })
            except Exception as e:
                self._send_error(500, f"Falha no download da mídia: {str(e)}")
            return

        # 4. Endpoint de Visualização / Download de Caderno em PDF Estruturado
        if path == "/api/pdf":
            video_param = params.get("v", [None])[0] or params.get("url", [None])[0]
            video_id = extract_video_id(video_param)
            if not video_id:
                self._send_error(400, "Parâmetro 'v' ou 'url' ausente.")
                return

            try:
                self._process_or_get_video(video_id)
                target_dir = self._find_video_dir(video_id)
                pdf_path = target_dir / "07_caderno_de_estudos.pdf"

                if not pdf_path.exists():
                    meta_json = target_dir / "metadados.json"
                    if meta_json.exists():
                        with open(meta_json, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        from .models import VideoMetadata, ParagraphBlock, SummaryReport
                        from .pdf_generator import generate_study_pdf
                        m = data["metadata"]
                        meta = VideoMetadata(
                            video_id=m["video_id"],
                            title=m["title"],
                            channel_name=m["channel_name"],
                            channel_url=m["channel_url"],
                            canonical_url=m["canonical_url"],
                            thumbnail_url=m.get("thumbnail_url", ""),
                            duration_seconds=m.get("duration_seconds", 0),
                            detected_language=m.get("detected_language", "pt"),
                            processed_at=m.get("processed_at", "")
                        )
                        paragraphs = [
                            ParagraphBlock(text=p["text"], start_time=p["start_time"], end_time=p["end_time"])
                            for p in data["paragraphs"]
                        ]
                        summary_file = target_dir / "03_resumo_e_insights.md"
                        sum_text = summary_file.read_text(encoding="utf-8") if summary_file.exists() else ""
                        summary = SummaryReport(
                            executive_summary=sum_text[:600],
                            key_takeaways=[],
                            chapters_breakdown=[],
                            full_markdown=sum_text,
                            engine_used="google-engine"
                        )
                        generate_study_pdf(meta, paragraphs, summary, str(pdf_path))

                if pdf_path.exists():
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", f'inline; filename="{pdf_path.name}"')
                    self.send_header("Content-Length", str(len(pdf_bytes)))
                    self.end_headers()
                    self.wfile.write(pdf_bytes)
                    return
                else:
                    self._send_error(500, "Não foi possível gerar o PDF da aula.")
            except Exception as e:
                self._send_error(500, f"Erro ao gerar ou carregar PDF: {str(e)}")
            return

        # 5. Rota Padrão: Servir arquivos estáticos da pasta de transcrições
        super().do_GET()

    def _find_video_dir(self, video_id: str) -> Path:
        """Localiza a pasta da aula onde os arquivos foram salvos."""
        catalog_path = self.base_dir / ".catalogo_index.json"
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    catalog = json.load(f)
                    for item in catalog:
                        if item.get("video_id") == video_id:
                            return (self.base_dir / item["relative_dir"]).resolve()
            except Exception:
                pass
        # Fallback para pasta padrão
        fallback = self.base_dir / "downloads" / video_id
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _process_or_get_video(
        self,
        video_id: str,
        engine_pref: str = "auto",
        gemini_key: Optional[str] = None
    ) -> dict:
        """Verifica se o vídeo já foi processado ou executa o pipeline instantaneamente."""
        organizer = LibraryOrganizer(base_output_dir=str(self.base_dir))
        
        # Procura se já temos esse vídeo catalogado
        catalog_path = self.base_dir / ".catalogo_index.json"
        if catalog_path.exists():
            try:
                with open(catalog_path, "r", encoding="utf-8") as f:
                    catalog = json.load(f)
                    for item in catalog:
                        if item.get("video_id") == video_id:
                            target_dir = self.base_dir / item["relative_dir"]
                            meta_json_file = target_dir / "metadados.json"
                            cornell_file = target_dir / "06_caderno_cornell.md"
                            summary_file = target_dir / "03_resumo_e_insights.md"

                            if meta_json_file.exists() and cornell_file.exists():
                                with open(meta_json_file, "r", encoding="utf-8") as mf:
                                    cached_meta = json.load(mf)
                                with open(cornell_file, "r", encoding="utf-8") as cf:
                                    cached_cornell = cf.read()
                                cached_summary = ""
                                if summary_file.exists():
                                    with open(summary_file, "r", encoding="utf-8") as sf:
                                        cached_summary = sf.read()

                                return {
                                    "metadata": cached_meta.get("metadata", {}),
                                    "paragraphs": cached_meta.get("paragraphs", []),
                                    "summary": {"full_markdown": cached_summary},
                                    "cornell_markdown": cached_cornell,
                                    "cached": True
                                }
            except Exception:
                pass

        # Executa o pipeline de ponta a ponta com suporte duplo a Whisper / Gemini
        metadata = fetch_video_metadata(video_id)
        transcriber = TranscriptionEngine(
            allow_audio_fallback=True,
            audio_engine_type=engine_pref,
            gemini_key=gemini_key
        )
        snippets, lang = transcriber.fetch_transcript(video_id)
        metadata.detected_language = lang
        if snippets:
            metadata.duration_seconds = snippets[-1].end

        paragraphs = build_semantic_paragraphs(snippets)
        full_text = "\n\n".join(p.text for p in paragraphs)

        summarizer = ContentSummarizer(api_key=gemini_key)
        summary = summarizer.generate_summary(metadata, paragraphs, full_text)

        result = organizer.organize_and_save(metadata, paragraphs, snippets, summary)
        cornell_content = generate_cornell_notes(metadata, paragraphs, summary)

        return {
            "metadata": {
                "video_id": metadata.video_id,
                "canonical_url": metadata.canonical_url,
                "title": metadata.title,
                "channel_name": metadata.channel_name,
                "channel_url": metadata.channel_url,
                "duration_formatted": metadata.formatted_duration,
                "detected_language": metadata.detected_language
            },
            "paragraphs": [
                {
                    "start_time": p.start_time,
                    "end_time": p.end_time,
                    "timestamp_formatted": p.format_timestamp(),
                    "text": p.text
                }
                for p in paragraphs
            ],
            "summary": {
                "full_markdown": summary.full_markdown,
                "engine_used": summary.engine_used
            },
            "cornell_markdown": cornell_content,
            "cached": False
        }

    def _send_json(self, data: dict, status_code: int = 200):
        try:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError):
            pass

    def _send_error(self, status_code: int, message: str):
        self._send_json({"error": message}, status_code=status_code)


def _free_port_if_in_use(port: int):
    """Garante que a porta esteja livre, encerrando processos órfãos anteriores se necessário."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return
    except OSError:
        s.close()

    if sys.platform == "win32":
        import subprocess
        try:
            res = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                check=False
            )
            current_pid = os.getpid()
            for line in res.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = int(parts[-1])
                        if pid != current_pid and pid > 0:
                            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, check=False)
                            import time
                            time.sleep(0.5)
        except Exception:
            pass


def start_study_server(host: str = "127.0.0.1", port: int = 8765):
    """Inicia o servidor de suporte local para a Extensão do Chrome e web clients."""
    _free_port_if_in_use(port)
    server_address = (host, port)
    httpd = ThreadedHTTPServer(server_address, StudyApiHandler)
    try:
        print(f"\n[SERVIDOR] Motor de Estudos Ativo em: http://{host}:{port}")
        print(f"[EXTENSAO] Conexao Chrome Side Panel em: http://{host}:{port}/api/transcript")
        print(f"[STATUS] Pressione Ctrl + C para encerrar a qualquer momento.\n")
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        httpd.server_close()

