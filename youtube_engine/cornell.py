"""
Gerador de Caderno de Estudos com o Método Cornell.
Estruturado para máxima retenção de conteúdo, memorização ativa e revisão espaçada.
Compatível nativamente com Obsidian, Notion e Logseq.
"""

from typing import List
from .models import VideoMetadata, ParagraphBlock, SummaryReport


def parse_cornell_cues_and_notes(paragraphs: List[ParagraphBlock]):
    """
    Agrupa parágrafos em blocos cronológicos de ~4 minutos e extrai tuplas:
    (pergunta_pista, notas_consolidadas, timestamp_formatado, segundos_inicio).
    """
    sections = []
    current_sec_paragraphs = []
    sec_start = 0.0

    for p in paragraphs:
        if not current_sec_paragraphs:
            sec_start = p.start_time
            current_sec_paragraphs.append(p)
        elif (p.end_time - sec_start) >= 240.0:
            sections.append(current_sec_paragraphs)
            current_sec_paragraphs = [p]
            sec_start = p.start_time
        else:
            current_sec_paragraphs.append(p)

    if current_sec_paragraphs:
        sections.append(current_sec_paragraphs)

    result = []
    for sec in sections:
        first_p = sec[0]
        start_sec = int(first_p.start_time)
        ts_str = first_p.format_timestamp()

        # Extrai frase-guia
        sample_snippet = first_p.text[:95].strip()
        if len(first_p.text) > 95:
            sample_snippet += "..."
        cue_question = f"Qual o conceito central discutido a partir de [{ts_str}] ({sample_snippet})?"

        notes_lines = []
        for p in sec:
            notes_lines.append(f"• [{p.format_timestamp()}] {p.text}")
        notes_combined = "<br><br>".join(notes_lines)

        result.append((cue_question, notes_combined, ts_str, start_sec))

    return result


def generate_cornell_notes(
    metadata: VideoMetadata,
    paragraphs: List[ParagraphBlock],
    summary: SummaryReport
) -> str:
    """
    Constrói um documento no padrão do Método Cornell de anotações acadêmicas.
    """
    clean_channel = metadata.channel_name.lower().replace(" ", "_")
    cues_data = parse_cornell_cues_and_notes(paragraphs)

    md = [
        "---",
        f'title: "Anotações Cornell: {metadata.title}"',
        f'channel: "{metadata.channel_name}"',
        f'video_id: "{metadata.video_id}"',
        f'url: "{metadata.canonical_url}"',
        f'duration: "{metadata.formatted_duration}"',
        f'processed_at: "{metadata.processed_at}"',
        "tags:",
        "  - estudos",
        "  - metodo_cornell",
        "  - videoaula",
        f"  - {clean_channel}",
        "  - revisao_ativa",
        "status: para_revisar",
        "---",
        "",
        f"# 🎓 Caderno de Estudos (Método Cornell): {metadata.title}",
        "",
        f"> **Canal:** [{metadata.channel_name}]({metadata.channel_url})  ",
        f"> **Aula Completa:** [Assistir no YouTube]({metadata.canonical_url}) (`{metadata.formatted_duration}`)  ",
        f"> **Data do Estudo:** `{metadata.processed_at}`",
        "",
        "---",
        "",
        "## 📌 Matriz de Estudo Cornell",
        "",
        "| ❓ Pistas & Perguntas-Chave (Cues) | 📝 Anotações da Aula (Notes com Timestamps) |",
        "| :--- | :--- |"
    ]

    for cue_question, notes_combined, ts_str, start_sec in cues_data:
        yt_link = f"https://www.youtube.com/watch?v={metadata.video_id}&t={start_sec}s"
        cue_cell = f"**O que é abordado em [`{ts_str}`]({yt_link})?**<br><br>_{cue_question}_"
        notes_cell = notes_combined.replace("|", "\\|")
        md.append(f"| {cue_cell} | {notes_cell} |")

    if not cues_data:
        md.append("| Transcrição em andamento | Nenhuma anotação detectada para o período. |")

    md.extend([
        "",
        "---",
        "",
        "## 🎯 Síntese de Fechamento (Summary Cornell)",
        "",
        "> _Utilize este resumo para revisão rápida 24h, 7 dias e 30 dias após assistir à aula:_",
        "",
        summary.full_markdown,
        "",
        "---",
        "",
        "### 💡 Dicas de Revisão Espaçada:",
        "1. **Cubra a coluna da direita (Anotações):** Olhe apenas para as perguntas da coluna esquerda (Pistas) e tente responder mentalmente ou em voz alta.",
        "2. **Verifique suas respostas:** Descubra a coluna da direita e confira a exatidão das notas e dos artigos citados.",
        "3. **Clique nos timestamps:** Se surgir dúvida em qualquer detalhe técnico, clique no link do tempo para ver o professor explicando exatamente aquele ponto no YouTube."
    ])

    return "\n".join(md)
