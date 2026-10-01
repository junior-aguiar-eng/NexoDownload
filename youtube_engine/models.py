"""
Modelos de dados estruturados para o pipeline de transcrição do YouTube.
Padrão de Engenharia de Software Google: Tipagem estrita e imutabilidade quando aplicável.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class TranscriptSnippet:
    """Representa um fragmento temporal bruto retornado pela API de legendas."""
    text: str
    start: float
    duration: float

    @property
    def end(self) -> float:
        return self.start + self.duration

    def format_timestamp(self) -> str:
        """Formata o início no formato HH:MM:SS ou MM:SS."""
        total_seconds = int(self.start)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


@dataclass
class ParagraphBlock:
    """Bloco semântico de transcrição unificado (agregação de snippets contíguos)."""
    start_time: float
    end_time: float
    text: str
    snippets: List[TranscriptSnippet] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    def format_timestamp(self) -> str:
        total_seconds = int(self.start_time)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


@dataclass
class VideoMetadata:
    """Metadados completos e ricos do vídeo extraídos da infraestrutura do YouTube/Google."""
    video_id: str
    canonical_url: str
    title: str
    channel_name: str
    channel_url: str
    thumbnail_url: str
    duration_seconds: float = 0.0
    detected_language: str = "desconhecido"
    processed_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    @property
    def formatted_duration(self) -> str:
        total_seconds = int(self.duration_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        if hours > 0:
            return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
        return f"{minutes:02d}m {seconds:02d}s"


@dataclass
class SummaryReport:
    """Estrutura do relatório de síntese analítica do conteúdo."""
    executive_summary: str
    key_takeaways: List[str]
    chapters_breakdown: List[Dict[str, str]]
    full_markdown: str
    engine_used: str  # 'google-gemini' ou 'algorithmic-local'


@dataclass
class ProcessingResult:
    """Resultado final de ponta a ponta do pipeline de engenharia."""
    metadata: VideoMetadata
    raw_snippets: List[TranscriptSnippet]
    paragraphs: List[ParagraphBlock]
    full_text: str
    summary: SummaryReport
    output_dir: str
    generated_files: Dict[str, str] = field(default_factory=dict)
