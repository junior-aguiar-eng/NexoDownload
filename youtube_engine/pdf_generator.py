"""
Módulo de Geração de Caderno de Estudos em PDF Estruturado de Alta Fidelidade.
Padrão Google Engineering: Tipografia editorial, Método Cornell integrado,
timestamps clicáveis e renderização vetorial via Chromium Headless / PyMuPDF.
"""

import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from .models import VideoMetadata, ParagraphBlock, SummaryReport
from .cornell import parse_cornell_cues_and_notes


def generate_study_pdf(
    metadata: VideoMetadata,
    paragraphs: List[ParagraphBlock],
    summary: SummaryReport,
    output_pdf_path: str
) -> str:
    """
    Gera um PDF estruturado, editorial e elegante para impressão ou leitura digital.
    
    Retorna:
        str: Caminho absoluto do PDF gerado.
    """
    html_content = _build_study_pdf_html(metadata, paragraphs, summary)
    out_path = Path(output_pdf_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Tentativa 1: Renderização via Chromium Headless (Chrome ou Edge nativos)
    browser_exe = _find_browser_executable()
    if browser_exe:
        success = _render_pdf_with_browser(browser_exe, html_content, str(out_path))
        if success and out_path.exists() and out_path.stat().st_size > 1000:
            return str(out_path)

    # Tentativa 2: Fallback direto via PyMuPDF (biblioteca nativa instalada)
    return _render_pdf_with_pymupdf(metadata, paragraphs, summary, str(out_path))


def _find_browser_executable() -> Optional[str]:
    """Localiza o binário do Google Chrome ou Microsoft Edge no Windows/Linux/macOS."""
    # Procura no PATH
    for name in ["chrome", "google-chrome", "google-chrome-stable", "msedge", "chromium"]:
        p = shutil.which(name)
        if p and os.path.exists(p):
            return p

    # Caminhos comuns no Windows
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


def _render_pdf_with_browser(browser_path: str, html_content: str, output_pdf: str) -> bool:
    """Executa o browser em modo headless para produzir o PDF vetorial perfeito."""
    temp_html = os.path.join(tempfile.gettempdir(), f"study_doc_{os.getpid()}.html")
    try:
        with open(temp_html, "w", encoding="utf-8") as f:
            f.write(html_content)

        cmd = [
            browser_path,
            "--headless=new" if "edge" not in browser_path.lower() else "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-pdf-header-footer",
            f"--print-to-pdf={output_pdf}",
            temp_html
        ]

        res = subprocess.run(cmd, capture_output=True, timeout=30)
        return res.returncode == 0 and os.path.exists(output_pdf)
    except Exception:
        return False
    finally:
        try:
            if os.path.exists(temp_html):
                os.remove(temp_html)
        except Exception:
            pass


def _render_pdf_with_pymupdf(
    metadata: VideoMetadata,
    paragraphs: List[ParagraphBlock],
    summary: SummaryReport,
    output_pdf: str
) -> str:
    """Fallback usando PyMuPDF para gerar o documento PDF diretamente."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4

    margin_left = 50
    margin_top = 50
    y = margin_top

    # Cabeçalho
    page.insert_text((margin_left, y), "CADERNO DE ESTUDOS • MÉTODO CORNELL", fontsize=10, fontname="helv", color=(0.3, 0.4, 0.6))
    y += 25

    page.insert_text((margin_left, y), metadata.title[:75], fontsize=15, fontname="helv", color=(0.1, 0.15, 0.3))
    y += 20
    page.insert_text((margin_left, y), f"Canal: {metadata.channel_name} | Duração: {metadata.formatted_duration}", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))
    y += 30

    # Resumo
    page.insert_text((margin_left, y), "RESUMO EXECUTIVO", fontsize=11, fontname="helv", color=(0.1, 0.4, 0.7))
    y += 18

    exec_text = summary.executive_summary[:400].replace("\n", " ") + "..."
    rect = pymupdf.Rect(margin_left, y, 545, y + 80)
    page.insert_textbox(rect, exec_text, fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
    y += 95

    # Parágrafos da Transcrição
    page.insert_text((margin_left, y), "NOTAS DE AULA E TRANSCRIÇÃO", fontsize=11, fontname="helv", color=(0.1, 0.4, 0.7))
    y += 20

    for p in paragraphs[:25]:
        if y > 780:
            page = doc.new_page(width=595, height=842)
            y = margin_top

        ts_text = f"[{p.format_timestamp()}] "
        page.insert_text((margin_left, y), ts_text, fontsize=8, fontname="helv", color=(0.2, 0.4, 0.8))
        
        box_rect = pymupdf.Rect(margin_left + 45, y - 8, 545, y + 40)
        page.insert_textbox(box_rect, p.text, fontsize=8, fontname="helv", color=(0.15, 0.15, 0.15))
        y += 38

    doc.save(output_pdf)
    doc.close()
    return output_pdf


def _build_study_pdf_html(
    metadata: VideoMetadata,
    paragraphs: List[ParagraphBlock],
    summary: SummaryReport
) -> str:
    """Monta a estrutura HTML + CSS moderna de padrão editorial para impressão."""
    cues_and_notes = parse_cornell_cues_and_notes(paragraphs)
    
    # Monta linhas do Cornell
    cornell_rows_html = []
    for cue, note, ts, sec in cues_and_notes:
        yt_link = f"https://www.youtube.com/watch?v={metadata.video_id}&t={sec}s"
        cornell_rows_html.append(f"""
        <tr>
            <td class="col-cue">
                <div class="cue-badge">💡 Pergunta / Pista</div>
                <div class="cue-text">{cue}</div>
            </td>
            <td class="col-note">
                <div class="note-meta">
                    <a href="{yt_link}" class="timestamp-link" target="_blank">⏱️ [{ts}]</a>
                </div>
                <div class="note-text">{note}</div>
            </td>
        </tr>
        """)

    cornell_table = "\n".join(cornell_rows_html)

    # Monta parágrafos completos da transcrição
    transcription_blocks_html = []
    for p in paragraphs:
        sec = int(p.start_time)
        yt_link = f"https://www.youtube.com/watch?v={metadata.video_id}&t={sec}s"
        transcription_blocks_html.append(f"""
        <div class="transcript-entry">
            <a href="{yt_link}" class="timestamp-pill" target="_blank">{p.format_timestamp()}</a>
            <span class="transcript-body">{p.text}</span>
        </div>
        """)
    transcription_section = "\n".join(transcription_blocks_html)

    # Capítulos/Tópicos
    chapters_html = []
    if summary.chapters_breakdown:
        for c in summary.chapters_breakdown:
            yt_link = f"https://www.youtube.com/watch?v={metadata.video_id}&t={c.get('seconds', 0)}s"
            chapters_html.append(f"""
            <div class="topic-item">
                <a href="{yt_link}" class="topic-time">[{c.get('timestamp', '00:00')}]</a>
                <span class="topic-title">{c.get('title', '')}</span>
            </div>
            """)
    topics_section = "\n".join(chapters_html)

    keywords_badges = "".join(f'<span class="kw-badge">{kw}</span>' for kw in summary.key_takeaways[:12]) if summary.key_takeaways else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Caderno de Estudos - {metadata.title}</title>
<style>
    @page {{
        size: A4;
        margin: 16mm 18mm 18mm 18mm;
        @bottom-center {{
            content: "Caderno de Estudos • Método Cornell • Google Intelligence";
            font-size: 8pt;
            color: #94a3b8;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }}
        @bottom-right {{
            content: "Página " counter(page);
            font-size: 8pt;
            color: #64748b;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }}
    }}

    * {{
        box-sizing: border-box;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
    }}

    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: #1e293b;
        background: #ffffff;
        font-size: 10pt;
        line-height: 1.55;
        margin: 0;
        padding: 0;
    }}

    /* Capa e Cabeçalho */
    .header-card {{
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 18px;
        margin-bottom: 22px;
    }}

    .super-badge {{
        display: inline-block;
        background: #0ea5e9;
        color: #ffffff;
        font-size: 7.5pt;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        padding: 3px 9px;
        border-radius: 4px;
        margin-bottom: 10px;
    }}

    .video-title {{
        font-size: 18pt;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.25;
        margin: 0 0 10px 0;
    }}

    .meta-grid {{
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
        font-size: 8.5pt;
        color: #475569;
        align-items: center;
    }}

    .meta-item {{
        display: flex;
        align-items: center;
        gap: 4px;
    }}

    .meta-link {{
        color: #0284c7;
        text-decoration: none;
        font-weight: 600;
    }}

    /* Bloco Executivo */
    .section-title {{
        font-size: 12pt;
        font-weight: 700;
        color: #0f172a;
        margin: 20px 0 10px 0;
        display: flex;
        align-items: center;
        gap: 6px;
        border-bottom: 1px solid #f1f5f9;
        padding-bottom: 4px;
        page-break-after: avoid;
    }}

    .exec-card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #0284c7;
        border-radius: 6px;
        padding: 14px 16px;
        margin-bottom: 20px;
        page-break-inside: avoid;
    }}

    .exec-card p {{
        margin: 0 0 8px 0;
        font-size: 9.5pt;
        color: #334155;
    }}
    .exec-card p:last-child {{ margin-bottom: 0; }}

    .kw-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 10px;
    }}

    .kw-badge {{
        background: #e0f2fe;
        color: #0369a1;
        font-size: 7.5pt;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 9999px;
    }}

    /* Tópicos Cronológicos */
    .topics-box {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 22px;
        page-break-inside: avoid;
    }}

    .topic-item {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 5px;
        padding: 6px 10px;
        font-size: 8.5pt;
        display: flex;
        align-items: center;
        gap: 6px;
    }}

    .topic-time {{
        color: #0284c7;
        font-weight: 700;
        font-family: monospace;
        font-size: 8pt;
        text-decoration: none;
    }}

    .topic-title {{
        color: #334155;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    /* Tabela do Método Cornell */
    .cornell-table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        margin-bottom: 24px;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        overflow: hidden;
    }}

    .cornell-table thead th {{
        background: #1e293b;
        color: #ffffff;
        text-align: left;
        padding: 9px 14px;
        font-size: 8.5pt;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }}

    .cornell-table td {{
        padding: 12px 14px;
        vertical-align: top;
        border-bottom: 1px solid #e2e8f0;
        page-break-inside: avoid;
    }}

    .cornell-table tr:last-child td {{
        border-bottom: none;
    }}

    .col-cue {{
        width: 32%;
        background: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }}

    .cue-badge {{
        font-size: 7pt;
        font-weight: 700;
        color: #0284c7;
        text-transform: uppercase;
        margin-bottom: 4px;
    }}

    .cue-text {{
        font-weight: 600;
        color: #1e293b;
        font-size: 9pt;
        line-height: 1.35;
    }}

    .col-note {{
        width: 68%;
        background: #ffffff;
    }}

    .note-meta {{
        margin-bottom: 4px;
    }}

    .timestamp-link {{
        color: #0284c7;
        font-family: monospace;
        font-size: 8pt;
        font-weight: 700;
        text-decoration: none;
        background: #f0f9ff;
        padding: 1px 6px;
        border-radius: 3px;
        border: 1px solid #bae6fd;
    }}

    .note-text {{
        color: #334155;
        font-size: 9pt;
        line-height: 1.5;
    }}

    /* Transcrição Contínua */
    .page-break {{
        page-break-before: always;
    }}

    .transcript-entry {{
        display: flex;
        align-items: baseline;
        gap: 10px;
        padding: 6px 0;
        border-bottom: 1px dashed #f1f5f9;
        page-break-inside: avoid;
    }}

    .timestamp-pill {{
        flex-shrink: 0;
        font-family: monospace;
        font-size: 7.5pt;
        font-weight: 700;
        color: #0284c7;
        background: #f1f5f9;
        padding: 2px 6px;
        border-radius: 4px;
        text-decoration: none;
    }}

    .transcript-body {{
        font-size: 9pt;
        color: #334155;
        line-height: 1.6;
    }}
</style>
</head>
<body>

<!-- Cabeçalho Principal -->
<div class="header-card">
    <span class="super-badge">Caderno Oficial de Estudos • Método Cornell</span>
    <h1 class="video-title">{metadata.title}</h1>
    <div class="meta-grid">
        <div class="meta-item">📺 <b>Canal:</b> {metadata.channel_name}</div>
        <div class="meta-item">⏱️ <b>Duração:</b> {metadata.formatted_duration}</div>
        <div class="meta-item">📅 <b>Data:</b> {metadata.processed_at}</div>
        <div class="meta-item">🌐 <a href="{metadata.canonical_url}" class="meta-link" target="_blank">Assistir no YouTube</a></div>
    </div>
</div>

<!-- 1. Síntese Executiva -->
<div class="section-title">🎯 Resumo Executivo e Insights Centrais</div>
<div class="exec-card">
    <p>{summary.executive_summary}</p>
    {f'<div class="kw-container">{keywords_badges}</div>' if keywords_badges else ''}
</div>

<!-- 2. Estrutura de Tópicos (se houver) -->
{f'<div class="section-title">⏱️ Linha do Tempo e Capítulos da Apresentação</div><div class="topics-box">{topics_section}</div>' if summary.chapters_breakdown else ''}

<!-- 3. Caderno Cornell -->
<div class="section-title">📖 Anotações de Aprendizado Ativo (Método Cornell)</div>
<table class="cornell-table">
    <thead>
        <tr>
            <th>Coluna de Pistas & Questões</th>
            <th>Notas de Aula & Minutagens Clicáveis</th>
        </tr>
    </thead>
    <tbody>
        {cornell_table}
    </tbody>
</table>

<!-- 4. Transcrição Integral -->
<div class="page-break"></div>
<div class="section-title">📝 Transcrição Integral e Higienizada (Texto Completo)</div>
<div class="transcript-container">
    {transcription_section}
</div>

</body>
</html>
"""
