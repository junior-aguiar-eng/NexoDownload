"""
Módulo de Transcrição Resiliente do YouTube.
Implementa estratégia multi-nível de recuperação de legendas e tradução automática de contingência.
"""

from typing import List, Tuple, Optional
import html
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    YouTubeRequestFailed
)

from .models import TranscriptSnippet
from .cleaner import filter_clean_snippets, clean_text_segment


DEFAULT_LANGUAGES = ["pt", "pt-BR", "en", "es", "fr", "de", "it"]


class TranscriptionEngine:
    """Motor de orquestração de transcrições de alta resiliência."""

    def __init__(
        self,
        preferred_languages: Optional[List[str]] = None,
        allow_audio_fallback: bool = True,
        audio_engine_type: str = "auto",
        gemini_key: Optional[str] = None
    ):
        self.preferred_languages = preferred_languages or DEFAULT_LANGUAGES
        self.allow_audio_fallback = allow_audio_fallback
        self.audio_engine_type = audio_engine_type
        self.gemini_key = gemini_key
        self.api = YouTubeTranscriptApi()

    def fetch_transcript(self, video_id: str) -> Tuple[List[TranscriptSnippet], str]:
        """
        Recupera as legendas do vídeo com pipeline adaptativo.
        Se as legendas estiverem desativadas pelo canal, recorre à IA acústica (Whisper/Gemini).
        
        Retorna:
            Tuple[List[TranscriptSnippet], str]: Lista de fragmentos temporizados e o idioma detectado.
        """
        # Estratégia 1: Tentativa direta com a lista de idiomas preferenciais
        try:
            raw_data = self.api.fetch(video_id, languages=self.preferred_languages)
            snippets = self._parse_raw_snippets(raw_data)
            if snippets:
                # Tenta inferir idioma primário da lista preferencial
                return snippets, self.preferred_languages[0]
        except Exception:
            # Continua para a estratégia de inspeção detalhada
            pass

        # Estratégia 2: Inspeção da lista completa de legendas disponíveis
        try:
            transcript_list = self.api.list(video_id)
            
            # 2.1 Procura legendas manuais prioritárias
            selected_transcript = None
            detected_lang = "desconhecido"

            # Tenta encontrar qualquer correspondência entre os disponíveis e os preferenciais
            for lang_code in self.preferred_languages:
                try:
                    selected_transcript = transcript_list.find_transcript([lang_code])
                    detected_lang = lang_code
                    break
                except Exception:
                    continue

            # 2.2 Se não encontrou idioma preferencial exato, pega a primeira disponível
            if not selected_transcript:
                for t in transcript_list:
                    selected_transcript = t
                    detected_lang = t.language_code
                    break

            if selected_transcript:
                # 2.3 Se o idioma original não for português, mas puder ser traduzido, traduz para português
                if detected_lang not in ["pt", "pt-BR"] and getattr(selected_transcript, "is_translatable", False):
                    try:
                        selected_transcript = selected_transcript.translate("pt")
                        detected_lang = "pt (traduzido)"
                    except Exception:
                        pass

                raw_data = selected_transcript.fetch()
                snippets = self._parse_raw_snippets(raw_data)
                return snippets, detected_lang

        except (TranscriptsDisabled, NoTranscriptFound) as e:
            if self.allow_audio_fallback:
                print(f"\n[Info] Legendas desativadas pelo canal para o vídeo {video_id}.")
                print(f"[IA de Áudio] Ativando inteligência acústica (Whisper / Gemini)...")
                from .audio_transcriber import AudioTranscriptionEngine
                audio_engine = AudioTranscriptionEngine(gemini_key=self.gemini_key)
                return audio_engine.transcribe_video_audio(video_id, preferred_engine=self.audio_engine_type)
            raise RuntimeError(f"O vídeo {video_id} possui legendas e transcrições explicitamente desativadas pelo canal.")
        except VideoUnavailable:
            raise RuntimeError(f"O vídeo {video_id} está indisponível, privado ou foi removido.")
        except Exception as e:
            err_str = str(e).lower()
            if self.allow_audio_fallback and any(k in err_str for k in ["disabled", "subtitles", "transcript"]):
                print(f"\n[Info] Acionando inteligência de áudio para o vídeo {video_id}...")
                from .audio_transcriber import AudioTranscriptionEngine
                audio_engine = AudioTranscriptionEngine(gemini_key=self.gemini_key)
                return audio_engine.transcribe_video_audio(video_id, preferred_engine=self.audio_engine_type)
            raise RuntimeError(f"Falha ao obter transcrição para o vídeo {video_id}: {str(e)}")

        if self.allow_audio_fallback:
            print(f"\n[Info] Nenhuma legenda encontrada. Acionando inteligência de áudio...")
            from .audio_transcriber import AudioTranscriptionEngine
            audio_engine = AudioTranscriptionEngine(gemini_key=self.gemini_key)
            return audio_engine.transcribe_video_audio(video_id, preferred_engine=self.audio_engine_type)

        raise RuntimeError(f"Nenhuma transcrição ou legenda pôde ser localizada para o vídeo {video_id}.")

    def _parse_raw_snippets(self, raw_data) -> List[TranscriptSnippet]:
        """Converte a estrutura bruta da API em objetos tipados e higienizados."""
        snippets = []
        for item in raw_data:
            # Trata tanto objeto FetchedTranscriptSnippet quanto dict legado
            if hasattr(item, "text"):
                text = item.text
                start = float(item.start)
                duration = float(item.duration)
            elif isinstance(item, dict):
                text = item.get("text", "")
                start = float(item.get("start", 0.0))
                duration = float(item.get("duration", 0.0))
            else:
                continue

            # Decodifica entidades HTML (ex: &amp; -> &, &#39; -> ')
            clean_text = html.unescape(text).strip()
            # Remove tags acústicas ([música], [risos]) e ruídos
            clean_text = clean_text_segment(clean_text)
            
            # Filtra ruídos sonoros puros e snippets vazios
            if clean_text:
                snippets.append(TranscriptSnippet(
                    text=clean_text,
                    start=start,
                    duration=duration
                ))

        return filter_clean_snippets(snippets)
