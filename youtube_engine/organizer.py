"""
Gerenciador de Organização de Arquivos e Catálogo Central (BIBLIOTECA.md).
Padrão de Armazenamento Semântico e Resiliente a Sistemas de Arquivos (Windows/POSIX).
"""

import os
import re
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from typing import Dict, Any, List
from .models import VideoMetadata, ProcessingResult, ParagraphBlock, TranscriptSnippet, SummaryReport
from .formatters import (
    to_timestamped_markdown,
    to_plain_text,
    to_srt,
    to_vtt,
    to_json_dict
)
from .cornell import generate_cornell_notes
from .study_player import generate_study_player_html
from .pdf_generator import generate_study_pdf


def sanitize_filename(name: str, max_length: int = 70) -> str:
    """
    Remove caracteres proibidos no Windows/Linux/macOS e trunca para tamanho seguro.
    Proibidos no Windows: < > : " / \\ | ? *
    Também limpa caracteres que podem conflitar com URLs e links markdown.
    """
    if not name:
        return "sem_titulo"
    # Remove caracteres inválidos no sistema de arquivos
    cleaned = re.sub(r'[<>:"/\\|?*()]', '_', name)
    # Remove underscores repetidos e espaços
    cleaned = re.sub(r'_+', '_', cleaned)
    cleaned = " ".join(cleaned.split()).strip('._ ')
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip('._ ')
    return cleaned or "video_youtube"


class LibraryOrganizer:
    """Orquestra o salvamento físico dos artefatos e a manutenção do catálogo central."""

    def __init__(self, base_output_dir: str = "transcricoes"):
        self.base_output_dir = Path(base_output_dir).resolve()
        self.base_output_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_json_path = self.base_output_dir / ".catalogo_index.json"
        self.library_md_path = self.base_output_dir / "BIBLIOTECA.md"

    def organize_and_save(
        self,
        metadata: VideoMetadata,
        paragraphs: List[ParagraphBlock],
        snippets: List[TranscriptSnippet],
        summary: SummaryReport
    ) -> ProcessingResult:
        """
        Salva todos os formatos derivados em uma pasta estruturada e atualiza o catálogo mestre.
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_channel = sanitize_filename(metadata.channel_name, max_length=50)
        safe_title = sanitize_filename(metadata.title, max_length=70)
        
        # Estrutura de pasta: transcricoes/{Canal}/{YYYY-MM-DD}_{Titulo}/
        folder_name = f"{date_str}_{safe_title}"
        target_dir = self.base_output_dir / safe_channel / folder_name
        target_dir.mkdir(parents=True, exist_ok=True)

        generated_files: Dict[str, str] = {}

        # 1. 01_transcricao_formatada.md
        md_content = to_timestamped_markdown(metadata, paragraphs)
        md_path = target_dir / "01_transcricao_formatada.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        generated_files["markdown"] = str(md_path)

        # 2. 02_transcricao_pura.txt
        txt_content = to_plain_text(paragraphs)
        txt_path = target_dir / "02_transcricao_pura.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(txt_content)
        generated_files["txt"] = str(txt_path)

        # 3. 03_resumo_e_insights.md
        summary_path = target_dir / "03_resumo_e_insights.md"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary.full_markdown)
        generated_files["summary"] = str(summary_path)

        # 4. 04_legendas.srt
        srt_content = to_srt(snippets)
        srt_path = target_dir / "04_legendas.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
        generated_files["srt"] = str(srt_path)

        # 5. 05_legendas.vtt
        vtt_content = to_vtt(snippets)
        vtt_path = target_dir / "05_legendas.vtt"
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(vtt_content)
        generated_files["vtt"] = str(vtt_path)

        # 6. metadados.json
        json_data = to_json_dict(metadata, paragraphs, snippets)
        json_data["summary_engine"] = summary.engine_used
        json_path = target_dir / "metadados.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        generated_files["json"] = str(json_path)

        # 7. 06_caderno_cornell.md (Método Cornell de Aprendizado Ativo)
        cornell_content = generate_cornell_notes(metadata, paragraphs, summary)
        cornell_path = target_dir / "06_caderno_cornell.md"
        with open(cornell_path, "w", encoding="utf-8") as f:
            f.write(cornell_content)
        generated_files["cornell"] = str(cornell_path)

        # 8. estudo_interativo.html (Study Player com Sincronização em Tempo Real)
        player_html = generate_study_player_html(metadata, paragraphs, cornell_content)
        player_path = target_dir / "estudo_interativo.html"
        with open(player_path, "w", encoding="utf-8") as f:
            f.write(player_html)
        generated_files["player_html"] = str(player_path)

        # 9. 07_caderno_de_estudos.pdf (Caderno Editorial Estruturado)
        try:
            pdf_path = target_dir / "07_caderno_de_estudos.pdf"
            generate_study_pdf(metadata, paragraphs, summary, str(pdf_path))
            generated_files["pdf"] = str(pdf_path)
        except Exception:
            pass

        # 10. Atualiza o Catálogo Geral BIBLIOTECA.md
        word_count = sum(len(p.text.split()) for p in paragraphs)
        self._update_library_catalog(
            metadata=metadata,
            target_dir=target_dir,
            word_count=word_count,
            engine_used=summary.engine_used
        )

        return ProcessingResult(
            metadata=metadata,
            raw_snippets=snippets,
            paragraphs=paragraphs,
            full_text=txt_content,
            summary=summary,
            output_dir=str(target_dir),
            generated_files=generated_files
        )

    def _update_library_catalog(
        self,
        metadata: VideoMetadata,
        target_dir: Path,
        word_count: int,
        engine_used: str
    ):
        """Atualiza persistentemente o índice de vídeos da biblioteca."""
        # Carrega índice JSON persistente
        catalog = []
        if self.catalog_json_path.exists():
            try:
                with open(self.catalog_json_path, "r", encoding="utf-8") as f:
                    catalog = json.load(f)
            except Exception:
                catalog = []

        # Remove entrada anterior do mesmo video_id se já existir para atualizar
        catalog = [item for item in catalog if item.get("video_id") != metadata.video_id]

        # Caminho relativo para a pasta do vídeo a partir de base_output_dir
        rel_dir = target_dir.relative_to(self.base_output_dir).as_posix()

        new_entry = {
            "video_id": metadata.video_id,
            "title": metadata.title,
            "channel": metadata.channel_name,
            "duration": metadata.formatted_duration,
            "duration_seconds": metadata.duration_seconds,
            "language": metadata.detected_language,
            "words": word_count,
            "processed_at": metadata.processed_at,
            "relative_dir": rel_dir,
            "canonical_url": metadata.canonical_url,
            "engine": engine_used
        }
        catalog.insert(0, new_entry)

        # Salva catálogo JSON
        with open(self.catalog_json_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, ensure_ascii=False, indent=2)

        # Renderiza BIBLIOTECA.md
        total_videos = len(catalog)
        total_words = sum(item.get("words", 0) for item in catalog)
        total_seconds = sum(item.get("duration_seconds", 0) for item in catalog)
        total_hours = total_seconds / 3600.0

        md = [
            "# 📚 Biblioteca Central de Transcrições do YouTube",
            "",
            "> Índice consolidado e gerado automaticamente pelo **YouTube Transcriber Engine**.",
            "",
            f"**Total de Vídeos:** `{total_videos}` | **Horas Processadas:** `{total_hours:.1f}h` | **Palavras Catalogadas:** `{total_words:,}` | **Última Atualização:** `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
            "",
            "---",
            "",
            "| Data | Vídeo / Título | Canal | Duração | Palavras | Acesso Rápido |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |"
        ]

        for item in catalog:
            dt = item["processed_at"].split()[0]
            title = item["title"].replace("|", "-")
            channel = item["channel"].replace("|", "-")
            duration = item["duration"]
            words = f"{item['words']:,}"
            rel = item["relative_dir"]
            # Codifica caracteres de espaço paraリンク Markdown seguro
            rel_encoded = quote(rel)
            
            links = f"[📁 Pasta](./{rel_encoded}) • [📄 PDF](./{rel_encoded}/07_caderno_de_estudos.pdf) • [🎓 Cornell](./{rel_encoded}/06_caderno_cornell.md) • [🌐 Player](./{rel_encoded}/estudo_interativo.html) • [📝 Resumo](./{rel_encoded}/03_resumo_e_insights.md) • [▶️ YouTube]({item['canonical_url']})"
            md.append(f"| `{dt}` | **{title}** | {channel} | `{duration}` | {words} | {links} |")

        md.append("\n---\n_Biblioteca organizada no padrão Google Cloud Data Engineering._")

        with open(self.library_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))
