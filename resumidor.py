#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
    YOUTUBE INTELLIGENCE TRANSCRIBER & ORGANIZER - GOOGLE ENGINE GRADE
================================================================================
Suíte de alta performance para transcrição, estruturação semântica, sumarização
e catalogação automatizada de vídeos do YouTube.

Autor: Desenvolvido sob princípios de Engenharia de Software da Google
================================================================================
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Optional

# Garante suporte a UTF-8 no terminal Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Importação de Rich com fallback seguro
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import print as rprint
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

from youtube_engine import (
    extract_video_id,
    extract_urls_from_text_or_file,
    fetch_video_metadata,
    TranscriptionEngine,
    build_semantic_paragraphs,
    ContentSummarizer,
    LibraryOrganizer,
    ProcessingResult,
    start_study_server,
    download_media
)


def print_banner():
    """Exibe o cabeçalho oficial do sistema."""
    if HAS_RICH and console:
        title = "[bold cyan]YOUTUBE INTELLIGENCE TRANSCRIBER[/bold cyan] [dim]| Padrão Google Engineering[/dim]"
        subtitle = "[dim]Transcrição Semântica • Sumarização com IA • Legendas SRT/VTT • Catálogo Central[/dim]"
        console.print(Panel(f"{title}\n{subtitle}", border_style="cyan", padding=(1, 2)))
    else:
        print("=" * 75)
        print("   YOUTUBE INTELLIGENCE TRANSCRIBER | Google Software Engineering Standard")
        print("   Transcrição Semântica • Sumarização • Legendas SRT/VTT • Catálogo")
        print("=" * 75)


def process_single_video(
    video_input: str,
    output_dir: str = "transcricoes",
    preferred_languages: Optional[List[str]] = None,
    gemini_key: Optional[str] = None,
    download_video: bool = False,
    download_audio: bool = False,
    allow_audio_fallback: bool = True,
    audio_engine: str = "auto"
) -> Optional[ProcessingResult]:
    """
    Executa o pipeline completo de ponta a ponta para um único vídeo.
    """
    video_id = extract_video_id(video_input)
    if not video_id:
        if HAS_RICH:
            rprint(f"[bold red]❌ Erro:[/bold red] Formato de URL ou ID do YouTube inválido: '{video_input}'")
        else:
            print(f"Erro: Formato de URL ou ID do YouTube inválido: '{video_input}'")
        return None

    if HAS_RICH and console:
        with Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            # 1. Metadados
            task_meta = progress.add_task("[cyan]Coletando metadados ricos do vídeo...", total=None)
            metadata = fetch_video_metadata(video_id)
            progress.remove_task(task_meta)

            # 2. Transcrição (Legendas Oficiais + Fallback Whisper Local / Gemini IA)
            task_trans = progress.add_task(f"[yellow]Obtendo transcrição ({metadata.title[:40]}...)...", total=None)
            engine = TranscriptionEngine(
                preferred_languages=preferred_languages,
                allow_audio_fallback=allow_audio_fallback,
                audio_engine_type=audio_engine,
                gemini_key=gemini_key
            )
            try:
                snippets, lang = engine.fetch_transcript(video_id)
                metadata.detected_language = lang
                if snippets:
                    metadata.duration_seconds = snippets[-1].end
            except Exception as e:
                progress.remove_task(task_trans)
                rprint(f"[bold red]❌ Falha na transcrição:[/bold red] {e}")
                return None
            progress.remove_task(task_trans)

            # 3. Smart Paragraphing
            task_para = progress.add_task("[blue]Estruturando parágrafos semânticos e timestamps...", total=None)
            paragraphs = build_semantic_paragraphs(snippets)
            full_text = "\n\n".join(p.text for p in paragraphs)
            progress.remove_task(task_para)

            # 4. Síntese e Inteligência
            task_sum = progress.add_task("[magenta]Gerando síntese analítica e extração de tópicos...", total=None)
            summarizer = ContentSummarizer(api_key=gemini_key)
            summary = summarizer.generate_summary(metadata, paragraphs, full_text)
            progress.remove_task(task_sum)

            # 5. Organização e Salvamento
            task_org = progress.add_task("[green]Salvando arquivos e atualizando a BIBLIOTECA.md...", total=None)
            organizer = LibraryOrganizer(base_output_dir=output_dir)
            result = organizer.organize_and_save(metadata, paragraphs, snippets, summary)
            progress.remove_task(task_org)

            # 6. Download Opcional de Vídeo
            if download_video:
                task_vid = progress.add_task("[bold cyan]Baixando vídeo MP4 em alta resolução (yt-dlp)...", total=None)
                try:
                    vid_path = download_media(video_id, result.output_dir, media_type="video")
                    result.generated_files["video_mp4"] = vid_path
                except Exception as e:
                    rprint(f"[bold red]Falha ao baixar vídeo:[/bold red] {e}")
                progress.remove_task(task_vid)

            # 7. Download Opcional de Áudio
            if download_audio:
                task_aud = progress.add_task("[bold yellow]Extraindo podcast/áudio para estudos em mobilidade...", total=None)
                try:
                    aud_path = download_media(video_id, result.output_dir, media_type="audio")
                    result.generated_files["audio"] = aud_path
                except Exception as e:
                    rprint(f"[bold red]Falha ao extrair áudio:[/bold red] {e}")
                progress.remove_task(task_aud)
    else:
        print(f"\n-> Processando vídeo ID: {video_id}...")
        metadata = fetch_video_metadata(video_id)
        print(f"-> Título: {metadata.title} | Canal: {metadata.channel_name}")
        
        engine = TranscriptionEngine(
            preferred_languages=preferred_languages,
            allow_audio_fallback=allow_audio_fallback,
            audio_engine_type=audio_engine,
            gemini_key=gemini_key
        )
        try:
            snippets, lang = engine.fetch_transcript(video_id)
            metadata.detected_language = lang
            if snippets:
                metadata.duration_seconds = snippets[-1].end
        except Exception as e:
            print(f"Erro na transcrição: {e}")
            return None

        paragraphs = build_semantic_paragraphs(snippets)
        full_text = "\n\n".join(p.text for p in paragraphs)
        
        summarizer = ContentSummarizer(api_key=gemini_key)
        summary = summarizer.generate_summary(metadata, paragraphs, full_text)

        organizer = LibraryOrganizer(base_output_dir=output_dir)
        result = organizer.organize_and_save(metadata, paragraphs, snippets, summary)

        if download_video:
            print("-> Baixando vídeo MP4...")
            vid_path = download_media(video_id, result.output_dir, media_type="video")
            result.generated_files["video_mp4"] = vid_path

        if download_audio:
            print("-> Extraindo áudio...")
            aud_path = download_media(video_id, result.output_dir, media_type="audio")
            result.generated_files["audio"] = aud_path

    # Exibição de resultados
    _display_result_summary(result)
    return result


def _display_result_summary(result: ProcessingResult):
    """Exibe painel ou tabela detalhada com o resultado da execução."""
    if HAS_RICH and console:
        table = Table(title=f"✅ Vídeo Processado com Sucesso", border_style="green", show_lines=True)
        table.add_column("Propriedade", style="cyan", width=22)
        table.add_column("Detalhes", style="white")

        table.add_row("Título", f"[bold]{result.metadata.title}[/bold]")
        table.add_row("Canal", f"{result.metadata.channel_name}")
        table.add_row("Duração", f"{result.metadata.formatted_duration}")
        table.add_row("Idioma Detectado", f"{result.metadata.detected_language}")
        table.add_row("Estatísticas", f"{len(result.raw_snippets)} legendas brutas → {len(result.paragraphs)} parágrafos ({len(result.full_text.split()):,} palavras)")
        table.add_row("Motor de Resumo", f"{result.summary.engine_used}")
        table.add_row("Pasta de Destino", f"[link=file://{result.output_dir}]{result.output_dir}[/link]")

        console.print(table)

        files_table = Table(title="📁 Arquivos Gerados de Alta Fidelidade", border_style="dim")
        files_table.add_column("Formato", style="yellow")
        files_table.add_column("Caminho do Arquivo", style="dim")
        
        for fmt, path in result.generated_files.items():
            files_table.add_row(fmt.upper(), Path(path).name)

        console.print(files_table)
        rprint("[bold green]✨ Catálogo atualizado em:[/bold green] [underline]transcricoes/BIBLIOTECA.md[/underline]\n")
    else:
        print("\n" + "=" * 60)
        print(f"Vídeo Processado com Sucesso: {result.metadata.title}")
        print(f"Canal: {result.metadata.channel_name} | Duração: {result.metadata.formatted_duration}")
        print(f"Destino: {result.output_dir}")
        print("Arquivos gerados:")
        for fmt, p in result.generated_files.items():
            print(f"  - [{fmt.upper()}] {Path(p).name}")
        print("=" * 60 + "\n")


def main():
    """Ponto de entrada do sistema."""
    parser = argparse.ArgumentParser(
        description="YouTube Intelligence Transcriber & Organizer - Padrão Google Engineering",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("video_url", nargs="?", help="URL ou ID do vídeo do YouTube")
    parser.add_argument("-u", "--url", dest="opt_url", help="URL ou ID do vídeo do YouTube")
    parser.add_argument("-f", "--file", dest="file_path", help="Arquivo .txt com uma lista de links do YouTube (processamento em lote)")
    parser.add_argument("-o", "--output-dir", default="transcricoes", help="Diretório base para salvar as transcrições (padrão: 'transcricoes')")
    parser.add_argument("-l", "--languages", default="pt,pt-BR,en,es", help="Idiomas prioritários separados por vírgula (padrão: 'pt,pt-BR,en,es')")
    parser.add_argument("-k", "--gemini-key", default=None, help="Chave de API do Google Gemini para síntese avançada")
    parser.add_argument("-s", "--serve", action="store_true", help="Inicia o servidor de API local para a Extensão do Chrome e Study Player")
    parser.add_argument("-p", "--port", type=int, default=8765, help="Porta do servidor local (padrão: 8765)")
    parser.add_argument("--video", action="store_true", help="Realiza o download do vídeo completo em MP4 (720p/1080p)")
    parser.add_argument("--audio", action="store_true", help="Extrai apenas o áudio em formato podcast (M4A/MP3)")
    parser.add_argument("--engine", choices=["auto", "whisper", "gemini"], default="auto", help="Motor de IA acústica para fallback (padrão: auto - Whisper Local / Gemini)")
    parser.add_argument("--no-audio-fallback", action="store_true", help="Desativa a transcrição por áudio quando o vídeo não possuir legendas")

    args = parser.parse_args()
    print_banner()

    # Modo Servidor de Apoio para Extensão do Chrome
    if args.serve:
        if HAS_RICH and console:
            console.print(Panel(
                f"[bold green]🚀 SERVIDOR DE APOIO LOCAL ATIVO[/bold green]\n"
                f"[cyan]Porta:[/cyan] {args.port} | [cyan]Endereço:[/cyan] http://127.0.0.1:{args.port}\n\n"
                f"[bold yellow]💎 Extensão do Chrome:[/bold yellow] Sincronização em tempo real e downloads habilitados!\n"
                f"[bold magenta]🎙️ Motores de Áudio:[/bold magenta] Whisper Local + Google Gemini AI Prontos!\n"
                f"[dim]Pressione Ctrl + C para encerrar a qualquer momento.[/dim]",
                border_style="green"
            ))
        start_study_server(port=args.port)
        return

    target_url = args.video_url or args.opt_url
    langs = [lang.strip() for lang in args.languages.split(",") if lang.strip()]
    allow_audio = not args.no_audio_fallback

    # Modo 1: Processamento em lote a partir de arquivo
    if args.file_path:
        if not os.path.exists(args.file_path):
            if HAS_RICH:
                rprint(f"[bold red]❌ Arquivo não encontrado:[/bold red] {args.file_path}")
            else:
                print(f"Arquivo não encontrado: {args.file_path}")
            sys.exit(1)

        urls = extract_urls_from_text_or_file(args.file_path)
        if HAS_RICH:
            rprint(f"[bold green]Encontrados {len(urls)} vídeos para processamento em lote.[/bold green]\n")
        else:
            print(f"Encontrados {len(urls)} vídeos para processamento em lote.\n")

        success_count = 0
        for idx, vid in enumerate(urls, 1):
            if HAS_RICH:
                rprint(f"[bold cyan][Vídeo {idx}/{len(urls)}][/bold cyan] Iniciando processamento: {vid}")
            process_single_video(
                video_input=vid,
                output_dir=args.output_dir,
                preferred_languages=langs,
                gemini_key=args.gemini_key,
                download_video=args.video,
                download_audio=args.audio,
                allow_audio_fallback=allow_audio,
                audio_engine=args.engine
            )
            success_count += 1

        if HAS_RICH:
            rprint(f"[bold green]🎉 Concluído processamento de {success_count} vídeos![/bold green]")
        return

    # Modo 2: Processamento de URL informada via linha de comando
    if target_url:
        process_single_video(
            video_input=target_url,
            output_dir=args.output_dir,
            preferred_languages=langs,
            gemini_key=args.gemini_key,
            download_video=args.video,
            download_audio=args.audio,
            allow_audio_fallback=allow_audio,
            audio_engine=args.engine
        )
        return

    # Modo 3: Modo Interativo (quando executado sem argumentos via terminal)
    if HAS_RICH and console:
        rprint("[bold yellow]Modo Interativo:[/bold yellow] Nenhuma URL informada via parâmetro.")
        rprint("[dim]Dica: Você pode colar um link do YouTube, um ID de vídeo ou o caminho de um arquivo .txt com vários links.[/dim]\n")
        try:
            user_input = console.input("[bold cyan]➤ Digite ou cole o link do YouTube:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada pelo usuário.")
            return

        if not user_input:
            # Fallback para o vídeo demonstrativo padrão
            user_input = "https://www.youtube.com/watch?v=XHzzIHvi0BI&t=1041s"
            rprint(f"[dim]Nenhuma URL fornecida. Utilizando vídeo de demonstração: {user_input}[/dim]\n")
    else:
        try:
            user_input = input("➤ Digite ou cole o link do YouTube: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nOperação cancelada.")
            return
        if not user_input:
            user_input = "https://www.youtube.com/watch?v=XHzzIHvi0BI&t=1041s"

    # Verifica se a entrada do usuário é um arquivo
    if os.path.isfile(user_input):
        urls = extract_urls_from_text_or_file(user_input)
        for vid in urls:
            process_single_video(
                vid,
                output_dir=args.output_dir,
                preferred_languages=langs,
                gemini_key=args.gemini_key,
                allow_audio_fallback=allow_audio,
                audio_engine=args.engine
            )
    else:
        process_single_video(
            user_input,
            output_dir=args.output_dir,
            preferred_languages=langs,
            gemini_key=args.gemini_key,
            allow_audio_fallback=allow_audio,
            audio_engine=args.engine
        )


if __name__ == "__main__":
    main()