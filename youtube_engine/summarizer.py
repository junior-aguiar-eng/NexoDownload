"""
Motor de Inteligência e Síntese Analítica de Conteúdo.
Arquitetura Híbrida:
- Modo A: Google Gemini Generative AI (quando GEMINI_API_KEY configurada)
- Modo B: Motor Algorítmico Local (resiliente, offline, sem dependências externas de API)
"""

import os
import re
import requests
from collections import Counter
from typing import List, Dict, Any, Optional
from .models import VideoMetadata, ParagraphBlock, SummaryReport


# Stopwords essenciais para filtragem semântica local
STOPWORDS = {
    'de', 'a', 'o', 'que', 'e', 'do', 'da', 'em', 'um', 'para', 'com', 'não', 'uma',
    'os', 'no', 'se', 'na', 'por', 'mais', 'as', 'dos', 'como', 'mas', 'foi', 'ao',
    'ele', 'das', 'tem', 'à', 'seu', 'sua', 'ou', 'ser', 'quando', 'muito', 'há',
    'nos', 'já', 'está', 'eu', 'também', 'só', 'pelo', 'pela', 'até', 'isso', 'ela',
    'entre', 'era', 'depois', 'sem', 'mesmo', 'aos', 'ter', 'seus', 'quem', 'nas',
    'me', 'esse', 'eles', 'estão', 'você', 'tinha', 'foram', 'essa', 'num', 'nem',
    'suas', 'meu', 'às', 'minha', 'têm', 'numa', 'pelos', 'elas', 'havia', 'seja',
    'qual', 'será', 'nós', 'tenho', 'lhe', 'deles', 'essas', 'esses', 'pelas', 'este',
    'fosse', 'dele', 'tu', 'te', 'vocês', 'vos', 'lhes', 'meus', 'minhas', 'teu',
    'tua', 'teus', 'tuas', 'nosso', 'nossa', 'nossos', 'nossas', 'dela', 'delas',
    'esta', 'estes', 'estas', 'aquele', 'aquela', 'aqueles', 'aquelas', 'isto', 'aquilo',
    'aqui', 'ali', 'lá', 'onde', 'então', 'assim', 'aí', 'gente', 'vai', 'vou', 'bom',
    'bem', 'né', 'tá', 'fazer', 'saber', 'ver', 'dar', 'tudo', 'nada', 'coisa',
    'música', 'musica', 'aplausos', 'risos', 'áudio', 'audio', 'vídeo', 'video'
}


class ContentSummarizer:
    """Orquestrador de síntese e extração de insights de vídeo."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def generate_summary(
        self,
        metadata: VideoMetadata,
        paragraphs: List[ParagraphBlock],
        full_text: str
    ) -> SummaryReport:
        """Gera síntese estruturada usando Gemini AI ou motor algorítmico local."""
        if self.api_key:
            try:
                return self._generate_with_gemini(metadata, full_text)
            except Exception as e:
                # Log e fallback para local
                pass

        return self._generate_with_local_engine(metadata, paragraphs)

    def _generate_with_gemini(self, metadata: VideoMetadata, full_text: str) -> SummaryReport:
        """Invoca a API do Google Gemini com prompt de engenharia analítica."""
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
        
        # Limita o texto de entrada para caber folgadamente no contexto
        truncated_text = full_text[:120000]

        prompt = f"""
Atue como um Engenheiro e Pesquisador de Inteligência da Google especialista em síntese de conteúdo.
Analise a transcrição abaixo do vídeo do YouTube e elabore um documento executivo completo, analítico e de alto valor.

METADADOS DO VÍDEO:
- Título: {metadata.title}
- Canal: {metadata.channel_name}
- Duração: {metadata.formatted_duration}
- URL: {metadata.canonical_url}

ESTRUTURE SEU RELATÓRIO OBRIGATORIAMENTE NAS SEGUINTES SEÇÕES:
1. 🎯 RESUMO EXECUTIVO (Visão abrangente e objetiva do que o conteúdo aborda em 2 ou 3 parágrafos densos)
2. 📌 PONTOS CHAVE & APRENDIZADOS PRINCIPAIS (Bullet points aprofundados com os tópicos centrais discutidos)
3. ⏱️ ESTRUTURA CRONOLÓGICA E CAPÍTULOS TEMÁTICOS (Resumo das fases e momentos da apresentação)
4. 💡 INSIGHTS E APLICAÇÕES PRÁTICAS (Como o leitor pode aplicar o conhecimento transmitido)
5. ❓ PERGUNTAS & RESPOSTAS FUNDAMENTAIS (3 a 5 perguntas frequentes que o vídeo responde)

TRANSCRIÇÃO:
{truncated_text}
"""

        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096
            }
        }

        resp = requests.post(url, json=payload, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            candidates = data.get("candidates") or []
            if candidates:
                content = candidates[0].get("content") or {}
                parts = content.get("parts") or []
                if parts and "text" in parts[0]:
                    generated_text = parts[0]["text"]
                    return SummaryReport(
                        executive_summary=generated_text,
                        key_takeaways=[],
                        chapters_breakdown=[],
                        full_markdown=generated_text,
                        engine_used=f"google-gemini ({model})"
                    )
            raise RuntimeError("Gemini não retornou texto gerado (possível filtro de segurança ou resposta vazia).")
        else:
            raise RuntimeError(f"Erro na API do Gemini: {resp.status_code} - {resp.text}")

    def _generate_with_local_engine(
        self,
        metadata: VideoMetadata,
        paragraphs: List[ParagraphBlock]
    ) -> SummaryReport:
        """Motor algorítmico local de análise de frequência ponderada e capítulos temporais."""
        if not paragraphs:
            return SummaryReport(
                executive_summary="Conteúdo sem parágrafos suficientes para sumarização.",
                key_takeaways=[],
                chapters_breakdown=[],
                full_markdown="Não foi possível gerar o resumo.",
                engine_used="algorithmic-local"
            )

        # 1. Análise de Frequência de Palavras Relevantes
        all_words = []
        for p in paragraphs:
            words = re.findall(r'\b[a-zA-ZáéíóúâêîôûãõçÁÉÍÓÚÂÊÎÔÛÃÕÇ]{4,}\b', p.text.lower())
            all_words.extend([w for w in words if w not in STOPWORDS])

        word_counts = Counter(all_words)
        top_keywords = [w for w, _ in word_counts.most_common(12)]

        # 2. Pontuação de Sentenças Relevantes
        scored_paragraphs = []
        for p in paragraphs:
            score = 0
            text_lower = p.text.lower()
            for kw in top_keywords:
                score += text_lower.count(kw)
            # Penaliza parágrafos muito curtos
            length_penalty = 1.0 if len(p.text.split()) > 20 else 0.5
            scored_paragraphs.append((score * length_penalty, p))

        scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
        top_paragraphs = [p for _, p in scored_paragraphs[:5]]
        # Reordena cronologicamente
        top_paragraphs.sort(key=lambda p: p.start_time)

        # 3. Criação de Capítulos Cronológicos
        total_p = len(paragraphs)
        chapter_count = min(6, max(3, total_p // 4))
        step = max(1, total_p // chapter_count)
        
        chapters = []
        for c in range(chapter_count):
            idx = c * step
            if idx < len(paragraphs):
                p = paragraphs[idx]
                title_snip = p.text[:90].strip()
                if len(p.text) > 90:
                    title_snip += "..."
                chapters.append({
                    "timestamp": p.format_timestamp(),
                    "seconds": int(p.start_time),
                    "title": title_snip
                })

        # 4. Montagem do Markdown Estruturado
        md_lines = [
            f"# Relatório Analítico: {metadata.title}",
            "",
            f"> **Canal:** [{metadata.channel_name}]({metadata.channel_url})  ",
            f"> **Vídeo:** [Assistir no YouTube]({metadata.canonical_url})  ",
            f"> **Duração:** `{metadata.formatted_duration}` | **Motor de Análise:** `Algorítmico Local (TF-IDF Heurístico)`",
            "",
            "---",
            "",
            "## 🎯 Resumo Executivo e Destaques Principais",
            ""
        ]

        for p in top_paragraphs:
            start_sec = int(p.start_time)
            link = f"https://www.youtube.com/watch?v={metadata.video_id}&t={start_sec}s"
            md_lines.append(f"- [`[{p.format_timestamp()}]`]({link}) {p.text}\n")

        md_lines.extend([
            "",
            "## ⏱️ Linha do Tempo e Estrutura dos Tópicos",
            ""
        ])

        for chap in chapters:
            link = f"https://www.youtube.com/watch?v={metadata.video_id}&t={chap['seconds']}s"
            md_lines.append(f"- [`[{chap['timestamp']}]`]({link}) **Tópico:** {chap['title']}")

        md_lines.extend([
            "",
            "## 🔑 Palavras-Chave e Conceitos Mais Frequentes",
            "",
            ", ".join(f"`{kw}`" for kw in top_keywords),
            "",
            "---",
            f"_Processado e catalogado automaticamente em {metadata.processed_at}_"
        ])

        full_md = "\n".join(md_lines)

        return SummaryReport(
            executive_summary="\n".join(p.text for p in top_paragraphs),
            key_takeaways=top_keywords,
            chapters_breakdown=chapters,
            full_markdown=full_md,
            engine_used="algorithmic-local"
        )
