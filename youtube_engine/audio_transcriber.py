"""
Motor Duplo de Transcrição por Áudio: Whisper Local + Google Gemini AI.
Padrão Google Engineering: Alta precisão, custo zero (R$ 0,00) e fallback 100% automático.
"""

import os
import re
import sys
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional

from .models import TranscriptSnippet
from .downloader import download_media
from .cleaner import clean_text_segment, filter_clean_snippets


class AudioTranscriptionEngine:
    """Motor de inteligência acústica híbrido: Whisper Local + Gemini 2.5 Flash."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        gemini_key: Optional[str] = None
    ):
        """
        model_size: 'tiny', 'base', 'small', 'medium'.
        'base' oferece o equilíbrio ideal entre velocidade absurda e precisão em português.
        compute_type: 'int8' roda com altíssima eficiência em qualquer processador sem placa de vídeo.
        gemini_key: Chave opcional do Google AI Studio (gratuita).
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.gemini_key = gemini_key or os.getenv("GEMINI_API_KEY")
        self._whisper_model = None

    def _get_whisper_model(self):
        if self._whisper_model is None:
            from faster_whisper import WhisperModel
            self._whisper_model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self._whisper_model

    def transcribe_video_audio(
        self,
        video_input: str,
        preferred_engine: str = "auto",
        temp_dir: Optional[str] = None
    ) -> Tuple[List[TranscriptSnippet], str]:
        """
        Extrai o áudio do vídeo e transcreve usando o motor selecionado com fallback automático.

        Args:
            video_input: URL ou ID do vídeo do YouTube.
            preferred_engine: 'auto', 'whisper' ou 'gemini'.
            temp_dir: Diretório de trabalho para o áudio extraído.

        Retorna:
            Tuple[List[TranscriptSnippet], str]: Lista de snippets e descrição do motor.
        """
        target_dir = temp_dir or tempfile.gettempdir()
        audio_path = download_media(video_input, target_dir, media_type="speech_audio")

        try:
            # 1. Modo Gemini se solicitado explicitamente e chave disponível
            if preferred_engine == "gemini" and self.gemini_key:
                try:
                    return self._transcribe_with_gemini(audio_path)
                except Exception as e:
                    print(f"Aviso: Gemini AI falhou ({e}). Recorrendo ao Whisper Local...")

            # 2. Modo Whisper Local (Padrão e Mais Seguro - 100% Offline e Gratuito)
            try:
                return self._transcribe_with_whisper(audio_path)
            except Exception as whisper_err:
                # Se Whisper falhar e houver chave Gemini, tenta Gemini como contingência
                if self.gemini_key and preferred_engine != "gemini":
                    print(f"Aviso: Whisper local encontrou erro ({whisper_err}). Tentando Gemini 2.5 Flash...")
                    return self._transcribe_with_gemini(audio_path)
                raise whisper_err

        finally:
            # Se foi salvo em pasta temporária descartável do sistema, limpa para evitar consumo de disco
            if temp_dir is None and audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except Exception:
                    pass

    def _transcribe_with_whisper(self, audio_file: str) -> Tuple[List[TranscriptSnippet], str]:
        """Executa transcrição de fala com Faster-Whisper local."""
        model = self._get_whisper_model()
        segments, info = model.transcribe(
            audio_file,
            beam_size=3,
            language="pt",
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500)
        )

        snippets: List[TranscriptSnippet] = []
        for seg in segments:
            text_clean = clean_text_segment(seg.text)
            if text_clean:
                snippets.append(TranscriptSnippet(
                    text=text_clean,
                    start=float(seg.start),
                    duration=float(seg.end - seg.start)
                ))

        filtered = filter_clean_snippets(snippets)
        detected_lang = f"pt (Whisper AI Local - {self.model_size})"
        return filtered, detected_lang

    def _transcribe_with_gemini(self, audio_file: str) -> Tuple[List[TranscriptSnippet], str]:
        """Executa transcrição e alinhamento temporal via Google Gemini 2.5 Flash."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.gemini_key)
        uploaded = None
        
        try:
            # Faz upload do arquivo para o File API do Google Gemini
            uploaded = client.files.upload(file=audio_file)

            prompt = (
                "Transcreva integralmente a fala contida neste áudio em português do Brasil. "
                "Formate a saída estritamente em linhas no formato: "
                "[MM:SS] Texto falado pelo orador. "
                "Não adicione introduções nem conclusões, apenas as linhas com o timestamp e o texto falado."
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[uploaded, prompt]
            )
        finally:
            if uploaded is not None:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass

        text_output = response.text or ""
        snippets: List[TranscriptSnippet] = []

        # Parser de timestamps [MM:SS] ou [HH:MM:SS]
        pattern = re.compile(r'\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]\s*(.+)')
        lines = text_output.splitlines()

        for idx, line in enumerate(lines):
            match = pattern.search(line)
            if match:
                part1 = int(match.group(1))
                part2 = int(match.group(2))
                part3 = match.group(3)
                spoken_text = match.group(4).strip()

                if part3 is not None:
                    # Formato HH:MM:SS
                    seconds = part1 * 3600 + part2 * 60 + int(part3)
                else:
                    # Formato MM:SS
                    seconds = part1 * 60 + part2

                clean_text = clean_text_segment(spoken_text)
                if clean_text:
                    snippets.append(TranscriptSnippet(
                        text=clean_text,
                        start=float(seconds),
                        duration=5.0
                    ))

        # Ajusta durações com base no próximo timestamp
        for i in range(len(snippets) - 1):
            diff = snippets[i + 1].start - snippets[i].start
            if diff > 0:
                snippets[i].duration = min(diff, 15.0)

        # Se o formato não seguiu timestamps estritos, cria snippets a partir do texto
        if not snippets and text_output.strip():
            blocks = text_output.strip().split("\n\n")
            cur_time = 0.0
            for b in blocks:
                cleaned = clean_text_segment(b)
                if cleaned:
                    snippets.append(TranscriptSnippet(text=cleaned, start=cur_time, duration=8.0))
                    cur_time += 8.0

        filtered = filter_clean_snippets(snippets)
        return filtered, "pt (Google Gemini 2.5 Flash)"
