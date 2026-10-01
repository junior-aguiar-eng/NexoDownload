"""
YouTube Transcriber & Organizer Engine - Google Software Engineering Standard.
"""

from .models import (
    TranscriptSnippet,
    ParagraphBlock,
    VideoMetadata,
    SummaryReport,
    ProcessingResult
)
from .url_parser import extract_video_id, get_canonical_url, extract_urls_from_text_or_file
from .metadata import fetch_video_metadata
from .transcriber import TranscriptionEngine
from .paragrapher import build_semantic_paragraphs
from .summarizer import ContentSummarizer
from .organizer import LibraryOrganizer
from .cornell import generate_cornell_notes
from .study_player import generate_study_player_html
from .server import start_study_server
from .downloader import download_media
from .audio_transcriber import AudioTranscriptionEngine
from .pdf_generator import generate_study_pdf

__all__ = [
    "TranscriptSnippet",
    "ParagraphBlock",
    "VideoMetadata",
    "SummaryReport",
    "ProcessingResult",
    "extract_video_id",
    "get_canonical_url",
    "extract_urls_from_text_or_file",
    "fetch_video_metadata",
    "TranscriptionEngine",
    "AudioTranscriptionEngine",
    "generate_study_pdf",
    "build_semantic_paragraphs",
    "ContentSummarizer",
    "LibraryOrganizer",
    "generate_cornell_notes",
    "generate_study_player_html",
    "start_study_server",
    "download_media"
]
