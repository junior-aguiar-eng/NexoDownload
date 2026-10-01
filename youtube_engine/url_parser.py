"""
Parser universal e resiliente de URLs do YouTube.
Suporta todos os padrões conhecidos de links e identificadores do ecossistema Google/YouTube.
"""

import re
from typing import Optional, List
from urllib.parse import urlparse, parse_qs


# Expressão regular cobrindo todos os padrões canônicos e alternativos do YouTube
YOUTUBE_ID_PATTERNS = [
    # youtube.com/watch?v=ID ou m.youtube.com/watch?v=ID
    r'(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/watch\?(?:.*&)?v=([a-zA-Z0-9_-]{11})',
    # youtu.be/ID
    r'(?:https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]{11})',
    # youtube.com/shorts/ID
    r'(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})',
    # youtube.com/live/ID
    r'(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/live\/([a-zA-Z0-9_-]{11})',
    # youtube.com/embed/ID
    r'(?:https?:\/\/)?(?:www\.|m\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',
    # ID puro de 11 caracteres
    r'^([a-zA-Z0-9_-]{11})$'
]


def extract_video_id(input_str: str) -> Optional[str]:
    """
    Extrai com precisão cirúrgica o identificador de 11 caracteres de qualquer formato de link do YouTube.
    
    Exemplos:
    - https://www.youtube.com/watch?v=XHzzIHvi0BI&t=1041s -> XHzzIHvi0BI
    - https://youtu.be/XHzzIHvi0BI -> XHzzIHvi0BI
    - https://www.youtube.com/shorts/XHzzIHvi0BI -> XHzzIHvi0BI
    - XHzzIHvi0BI -> XHzzIHvi0BI
    """
    if not input_str or not isinstance(input_str, str):
        return None
        
    cleaned = input_str.strip()
    
    # Tentativa 1: Verificação via expressões regulares
    for pattern in YOUTUBE_ID_PATTERNS:
        match = re.search(pattern, cleaned)
        if match:
            return match.group(1)
            
    # Tentativa 2: Parse via urllib como contingência
    try:
        parsed = urlparse(cleaned)
        if 'youtube.com' in parsed.netloc:
            qs = parse_qs(parsed.query)
            if 'v' in qs and qs['v']:
                candidate = qs['v'][0]
                if re.match(r'^[a-zA-Z0-9_-]{11}$', candidate):
                    return candidate
        elif 'youtu.be' in parsed.netloc:
            candidate = parsed.path.lstrip('/')
            if re.match(r'^[a-zA-Z0-9_-]{11}$', candidate):
                return candidate
    except Exception:
        pass

    return None


def get_canonical_url(video_id: str) -> str:
    """Gera a URL canônica padrão para um dado ID."""
    return f"https://www.youtube.com/watch?v={video_id}"


def extract_urls_from_text_or_file(source: str) -> List[str]:
    """
    Identifica múltiplos IDs ou links a partir de um texto corrido ou de um caminho de arquivo (.txt).
    """
    lines = []
    try:
        with open(source, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
    except Exception:
        # Não é arquivo, trata como entrada de texto com separadores (vírgula, espaço ou quebra de linha)
        lines = re.split(r'[\s,]+', source.strip())

    results = []
    for item in lines:
        vid = extract_video_id(item)
        if vid and vid not in results:
            results.append(vid)

    return results
