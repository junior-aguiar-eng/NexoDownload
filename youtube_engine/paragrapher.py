"""
Algoritmo de Agrupamento Semântico e Estruturação de Parágrafos (Smart Paragraphing).
Transforma fluxos picados de legendas de 2 segundos em parágrafos coesos, legíveis e com cadência natural.
"""

from typing import List
from .models import TranscriptSnippet, ParagraphBlock
from .cleaner import polish_paragraph_text


def build_semantic_paragraphs(
    snippets: List[TranscriptSnippet],
    target_duration_seconds: float = 40.0,
    max_duration_seconds: float = 75.0,
    pause_threshold_seconds: float = 1.8
) -> List[ParagraphBlock]:
    """
    Agrupa fragmentos temporais em parágrafos estruturados com base em pausas e tempo.
    
    Parâmetros:
        snippets: Lista de snippets brutos ordenados por tempo.
        target_duration_seconds: Duração ideal de um parágrafo.
        max_duration_seconds: Duração máxima antes de forçar nova quebra.
        pause_threshold_seconds: Pausa entre falas que indica mudança de tópico ou respiração.
    """
    if not snippets:
        return []

    paragraphs: List[ParagraphBlock] = []
    
    current_snippets: List[TranscriptSnippet] = []
    block_start = snippets[0].start
    
    for i, snippet in enumerate(snippets):
        current_snippets.append(snippet)
        current_duration = snippet.end - block_start
        
        # Analisa se o próximo snippet tem um intervalo de silêncio (pausa)
        has_significant_pause = False
        if i + 1 < len(snippets):
            gap = snippets[i + 1].start - snippet.end
            if gap >= pause_threshold_seconds:
                has_significant_pause = True
                
        # Verifica se o texto atual encerra uma oração
        ends_with_sentence = snippet.text.rstrip().endswith((".", "!", "?", ":", "..."))
        
        # Critérios de fechamento de parágrafo:
        # 1. Houve pausa significativa E atingiu duração mínima (> 20s)
        # 2. Encerrou sentença E atingiu target_duration
        # 3. Ultrapassou a duração máxima limite (força quebra)
        # 4. É o último snippet
        should_break = False
        
        if i == len(snippets) - 1:
            should_break = True
        elif current_duration >= max_duration_seconds:
            should_break = True
        elif current_duration >= target_duration_seconds and ends_with_sentence:
            should_break = True
        elif current_duration >= 20.0 and has_significant_pause:
            should_break = True

        if should_break:
            # Unifica o texto dos snippets do bloco
            raw_text = " ".join(s.text for s in current_snippets)
            # Remove ruídos, ajusta maiúsculas e pontuação
            clean_text = polish_paragraph_text(raw_text)
            
            if clean_text:
                paragraphs.append(ParagraphBlock(
                    start_time=block_start,
                    end_time=snippet.end,
                    text=clean_text,
                    snippets=list(current_snippets)
                ))
            
            # Reinicia para o próximo bloco
            current_snippets = []
            if i + 1 < len(snippets):
                block_start = snippets[i + 1].start

    return paragraphs
