"""
Formatadores e exportadores multi-formato de alta fidelidade.
Gera saídas em Markdown com timestamps clicáveis, Texto Puro, Legendas SRT/VTT e JSON estruturado.
"""

import json
from typing import List, Dict, Any
from .models import VideoMetadata, ParagraphBlock, TranscriptSnippet


def format_srt_time(seconds: float) -> str:
    """Converte segundos em formato SRT: HH:MM:SS,mmm"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def format_vtt_time(seconds: float) -> str:
    """Converte segundos em formato WebVTT: HH:MM:SS.mmm"""
    total_ms = int(round(seconds * 1000))
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    secs = (total_ms % 60000) // 1000
    ms = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def to_timestamped_markdown(metadata: VideoMetadata, paragraphs: List[ParagraphBlock]) -> str:
    """
    Gera documento Markdown com links hipertextuais para o momento exato do vídeo no YouTube.
    """
    lines = [
        f"# {metadata.title}",
        "",
        f"> **Canal:** [{metadata.channel_name}]({metadata.channel_url})  ",
        f"> **Link do Vídeo:** [Assistir no YouTube]({metadata.canonical_url})  ",
        f"> **Duração:** `{metadata.formatted_duration}` | **Idioma:** `{metadata.detected_language}` | **Data do Processamento:** `{metadata.processed_at}`",
        "",
        f"![Thumbnail do Vídeo]({metadata.thumbnail_url})",
        "",
        "---",
        "",
        "## Transcrição Completa com Minutagem Clicável",
        "",
        "_Clique no timestamp no início de cada parágrafo para saltar diretamente para esse momento no YouTube:_",
        ""
    ]

    for p in paragraphs:
        start_sec = int(p.start_time)
        yt_link = f"https://www.youtube.com/watch?v={metadata.video_id}&t={start_sec}s"
        timestamp_badge = f"[`[{p.format_timestamp()}]`]({yt_link})"
        lines.append(f"{timestamp_badge} {p.text}\n")

    return "\n".join(lines)


def to_plain_text(paragraphs: List[ParagraphBlock]) -> str:
    """Gera texto corrido limpo, sem metadados ou marcações, ideal para LLMs e leitura rápida."""
    return "\n\n".join(p.text for p in paragraphs)


def to_srt(snippets: List[TranscriptSnippet]) -> str:
    """Gera arquivo padrão de legendas SubRip (.srt)."""
    blocks = []
    for i, s in enumerate(snippets, 1):
        start_str = format_srt_time(s.start)
        end_str = format_srt_time(s.end)
        blocks.append(f"{i}\n{start_str} --> {end_str}\n{s.text}\n")
    return "\n".join(blocks)


def to_vtt(snippets: List[TranscriptSnippet]) -> str:
    """Gera arquivo padrão de legendas WebVTT (.vtt)."""
    blocks = ["WEBVTT", ""]
    for i, s in enumerate(snippets, 1):
        start_str = format_vtt_time(s.start)
        end_str = format_vtt_time(s.end)
        blocks.append(f"{start_str} --> {end_str}\n{s.text}\n")
    return "\n".join(blocks)


def to_json_dict(
    metadata: VideoMetadata,
    paragraphs: List[ParagraphBlock],
    snippets: List[TranscriptSnippet]
) -> Dict[str, Any]:
    """Exporta representação completa em formato de dicionário pronto para serialização JSON."""
    return {
        "metadata": {
            "video_id": metadata.video_id,
            "canonical_url": metadata.canonical_url,
            "title": metadata.title,
            "channel_name": metadata.channel_name,
            "channel_url": metadata.channel_url,
            "thumbnail_url": metadata.thumbnail_url,
            "duration_seconds": metadata.duration_seconds,
            "duration_formatted": metadata.formatted_duration,
            "detected_language": metadata.detected_language,
            "processed_at": metadata.processed_at
        },
        "stats": {
            "total_snippets": len(snippets),
            "total_paragraphs": len(paragraphs),
            "total_words": sum(len(p.text.split()) for p in paragraphs)
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
        "raw_snippets": [
            {
                "start": s.start,
                "duration": s.duration,
                "end": s.end,
                "text": s.text
            }
            for s in snippets
        ]
    }
