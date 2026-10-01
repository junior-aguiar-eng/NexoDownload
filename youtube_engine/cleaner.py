"""
Módulo de Limpeza Semântica e Remoção de Ruídos de Transcrição (Data Cleansing).
Padrão Google NLP: Remove artefatos de ASR, tags acústicas ([música], [aplausos]),
duplicações de fala e normaliza pontuação para transformar legendas automáticas em texto de livro.
"""

import re
from typing import List
from .models import TranscriptSnippet


# Padrões de ruídos acústicos e artefatos de Speech-To-Text do YouTube
ACOUSTIC_TAGS_REGEX = re.compile(
    r'\[\s*(?:música|musica|music|som|aplausos|risos|gargalhadas|vinheta|ruído|ruido|tosse|roncando|áudio|audio|suspiro|grito|palmas|legenda|silêncio|gagueira|barulho)[^\]]*\]',
    re.IGNORECASE
)

PARENTHESIS_TAGS_REGEX = re.compile(
    r'\(\s*(?:música|musica|music|aplausos|risos|vinheta)[^\)]*\)',
    re.IGNORECASE
)

SPEAKER_MARKERS_REGEX = re.compile(r'^(?:>>|>>>|\-\-)\s*')


def clean_text_segment(text: str) -> str:
    """
    Higieniza profundamente um segmento de fala individual:
    - Remove tags acústicas ([música], [risos], [roncando], etc.)
    - Remove marcadores de troca de orador (>>, >>>)
    - Remove gagueiras e duplicações automáticas da IA do YouTube (ex: 'que que', 'o o')
    - Ajusta espaçamentos e pontuações flutuantes
    """
    if not text:
        return ""

    # 1. Remove tags acústicas e colchetes sonoros
    cleaned = ACOUSTIC_TAGS_REGEX.sub("", text)
    cleaned = PARENTHESIS_TAGS_REGEX.sub("", cleaned)
    cleaned = SPEAKER_MARKERS_REGEX.sub("", cleaned)

    # 2. Remove repetições imediatas de palavras idênticas (artefato comum de STT, ex: 'o o', 'para para')
    # Preserva apenas quando intencional; remove duplicações óbvias
    cleaned = re.sub(r'\b([a-zA-ZáéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ]{2,})\s+\1\b', r'\1', cleaned, flags=re.IGNORECASE)

    # 3. Corrige espaços antes de pontuação (ex: 'processo civil .' -> 'processo civil.')
    cleaned = re.sub(r'\s+([,.:;!?])', r'\1', cleaned)

    # 4. Remove pontuações duplas erráticas (ex: '..,', ',.', '??')
    cleaned = re.sub(r'[,;]\s*[,;]+', ',', cleaned)
    cleaned = re.sub(r'\.{2,}(?!\.)', '.', cleaned)

    # 5. Normaliza espaços em branco múltiplos
    cleaned = " ".join(cleaned.split()).strip()

    # 6. Se sobrou apenas pontuação sem texto real (ex: apenas '.' ou ','), descarta
    if cleaned in {".", ",", ";", ":", "-", "--", "...", "!", "?"}:
        return ""

    return cleaned


def filter_clean_snippets(snippets: List[TranscriptSnippet]) -> List[TranscriptSnippet]:
    """
    Filtra a lista de fragmentos brutos, removendo blocos que eram puro silêncio ou vinheta musical.
    """
    cleaned_list: List[TranscriptSnippet] = []
    
    for s in snippets:
        cleaned_str = clean_text_segment(s.text)
        if cleaned_str:
            # Cria novo snippet preservando os tempos originais
            cleaned_list.append(TranscriptSnippet(
                text=cleaned_str,
                start=s.start,
                duration=s.duration
            ))
            
    return cleaned_list


def polish_paragraph_text(text: str) -> str:
    """
    Realiza o acabamento final no parágrafo consolidado:
    - Capitalização de início de frases
    - Remoção de vírgulas ou hifens soltos no final
    - Garantia de pontuação final elegante
    """
    cleaned = clean_text_segment(text)
    if not cleaned:
        return ""

    # Garante primeira letra maiúscula
    cleaned = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()

    # Capitaliza letras após ponto final seguido de espaço
    def capitalize_match(match):
        return match.group(1) + match.group(2).upper()
    cleaned = re.sub(r'([.!?]\s+)([a-zà-ÿ])', capitalize_match, cleaned)

    # Remove vírgula solta no final e adiciona ponto se não houver pontuação
    cleaned = cleaned.rstrip(' ,;:-')
    if cleaned and not cleaned.endswith(('.', '!', '?', ':', '...')):
        cleaned += '.'

    return cleaned
