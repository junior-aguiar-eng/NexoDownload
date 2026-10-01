#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
     BAIXADOR UNIVERSAL DE MÍDIAS - GOOGLE SOFTWARE ENGINEERING GRADE
================================================================================
Utilitário isolado e de alta velocidade para download de vídeos e áudios de 
qualquer plataforma (YouTube, TikTok, Instagram Reels, Pinterest, Twitter/X, Vimeo, etc.).

Totalmente desacoplado: NÃO gera transcrições, notas de estudo ou cadernos Cornell.
Salva apenas os arquivos brutos de mídia na pasta: downloads/{Plataforma}/
================================================================================
"""

import os
import re
import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

# Garante suporte UTF-8 no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Interface Visual com Rich
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import (
        Progress,
        SpinnerColumn,
        TextColumn,
        BarColumn,
        DownloadColumn,
        TransferSpeedColumn,
        TimeRemainingColumn
    )
    from rich import print as rprint
    console = Console()
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

import yt_dlp


def sanitize_filename(name: str, max_length: int = 100) -> str:
    """Higieniza o nome do arquivo para compatibilidade total no Windows/Linux/macOS."""
    if not name:
        return "midia_download"
    cleaned = re.sub(r'[<>:"/\\|?*()]', '_', name)
    cleaned = re.sub(r'_+', '_', cleaned)
    cleaned = " ".join(cleaned.split()).strip('._ ')
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip('._ ')
    return cleaned or "midia_download"


def detect_platform_name(url: str, extractor_key: Optional[str] = None) -> str:
    """Identifica a plataforma para organizar na subpasta correspondente."""
    if extractor_key:
        key_lower = extractor_key.lower()
        if "youtube" in key_lower:
            return "YouTube"
        if "tiktok" in key_lower:
            return "TikTok"
        if "instagram" in key_lower:
            return "Instagram"
        if "pinterest" in key_lower:
            return "Pinterest"
        if "twitter" in key_lower or "x" == key_lower:
            return "Twitter"
        if "facebook" in key_lower:
            return "Facebook"
        if "twitch" in key_lower:
            return "Twitch"
        if "vimeo" in key_lower:
            return "Vimeo"
        if "reddit" in key_lower:
            return "Reddit"
        if "linkedin" in key_lower:
            return "LinkedIn"

    url_lower = url.lower()
    if "youtu" in url_lower:
        return "YouTube"
    if "tiktok" in url_lower:
        return "TikTok"
    if "instagram" in url_lower:
        return "Instagram"
    if "pinterest" in url_lower or "pin.it" in url_lower:
        return "Pinterest"
    if "twitter" in url_lower or "x.com" in url_lower:
        return "Twitter"
    if "facebook" in url_lower or "fb.watch" in url_lower:
        return "Facebook"
    if "twitch" in url_lower:
        return "Twitch"
    if "vimeo" in url_lower:
        return "Vimeo"
    if "reddit" in url_lower:
        return "Reddit"
    if "linkedin" in url_lower:
        return "LinkedIn"

    return "Outros"


def download_single_media(
    url: str,
    base_downloads_dir: str = "downloads",
    media_type: str = "video",
    max_height: int = 1080,
    open_folder_when_done: bool = False
) -> Optional[str]:
    """
    Baixa um único vídeo ou áudio e salva organizadamente em downloads/{Plataforma}/.
    """
    url = url.strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        if HAS_RICH:
            rprint(f"[bold red]❌ URL inválida:[/bold red] '{url}'")
        else:
            print(f"Erro: URL inválida: '{url}'")
        return None

    # Detecta plataforma preliminar
    platform = detect_platform_name(url)
    target_dir = Path(base_downloads_dir).resolve() / platform
    target_dir.mkdir(parents=True, exist_ok=True)

    has_ffmpeg = shutil.which("ffmpeg") is not None

    # Configuração de opções otimizadas do yt-dlp
    ydl_opts: Dict[str, Any] = {
        "noplaylist": True,  # Proteção ativa: nunca baixa a playlist toda sem autorização
        "quiet": True,
        "no_warnings": True,
        "concurrent_fragment_downloads": 8,
    }

    if media_type == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }] if has_ffmpeg else []
        })
    else:
        video_format = (
            f"bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"bestvideo+bestaudio/"
            f"best[height<={max_height}]/"
            f"best"
        )
        ydl_opts.update({
            "format": video_format,
            "outtmpl": str(target_dir / "%(title)s.%(ext)s"),
            "merge_output_format": "mp4"
        })

    if HAS_RICH and console:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Baixando ({platform})...", total=100)

            def ytdl_hook(d):
                if d["status"] == "downloading":
                    total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    downloaded = d.get("downloaded_bytes", 0)
                    if total_bytes > 0:
                        progress.update(task, total=total_bytes, completed=downloaded)
                elif d["status"] == "finished":
                    progress.update(task, completed=progress.tasks[0].total)

            ydl_opts["progress_hooks"] = [ytdl_hook]

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    # Atualiza plataforma refinada se o extrator deu mais detalhes
                    refined_platform = detect_platform_name(url, info.get("extractor_key"))
                    filename = ydl.prepare_filename(info)
                    if media_type == "audio" and has_ffmpeg:
                        filename = os.path.splitext(filename)[0] + ".mp3"
            except Exception as e:
                rprint(f"[bold red]❌ Falha no download:[/bold red] {e}")
                return None
    else:
        print(f"-> Conectando a {platform}...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if media_type == "audio" and has_ffmpeg:
                    filename = os.path.splitext(filename)[0] + ".mp3"
        except Exception as e:
            print(f"Erro no download: {e}")
            return None

    saved_path = Path(filename)
    if not saved_path.exists():
        for ext_candidate in [".mp4", ".mkv", ".webm", ".mp3", ".m4a"]:
            if saved_path.with_suffix(ext_candidate).exists():
                saved_path = saved_path.with_suffix(ext_candidate)
                break

    if saved_path.exists():
        file_size_mb = saved_path.stat().st_size / (1024 * 1024)
        if HAS_RICH and console:
            console.print(Panel(
                f"[bold green]✅ Download Concluído com Sucesso![/bold green]\n\n"
                f"[cyan]📁 Arquivo:[/cyan] {saved_path.name}\n"
                f"[cyan]🌐 Plataforma:[/cyan] {platform}\n"
                f"[cyan]⚖️ Tamanho:[/cyan] {file_size_mb:.2f} MB\n"
                f"[cyan]📍 Localização:[/cyan] [link=file://{saved_path.parent}]{saved_path.parent}[/link]",
                border_style="green",
                padding=(1, 2)
            ))
        else:
            print("=" * 60)
            print(f"Download Concluído: {saved_path.name}")
            print(f"Plataforma: {platform} | Tamanho: {file_size_mb:.2f} MB")
            print(f"Salvo em: {saved_path.parent}")
            print("=" * 60)

        if open_folder_when_done:
            _open_folder_in_explorer(str(saved_path.parent))

        return str(saved_path)

    return None


def _open_folder_in_explorer(folder_path: str):
    """Abre a pasta no Windows Explorer / Finder."""
    try:
        if sys.platform == "win32":
            os.startfile(folder_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", folder_path])
        else:
            subprocess.run(["xdg-open", folder_path])
    except Exception:
        pass


def print_banner():
    """Cabeçalho visual do baixador universal."""
    if HAS_RICH and console:
        console.print(Panel(
            "[bold yellow]BAIXADOR UNIVERSAL DE VÍDEOS[/bold yellow] [dim]| Google Engineering Grade[/dim]\n"
            "[dim]YouTube • TikTok • Instagram Reels • Pinterest • Twitter/X • Facebook • Vimeo[/dim]\n"
            "[dim]Isolado e cirúrgico: salva apenas os arquivos de mídia em downloads/{Rede}/[/dim]",
            border_style="yellow",
            padding=(1, 2)
        ))
    else:
        print("=" * 70)
        print("   BAIXADOR UNIVERSAL DE VÍDEOS | Padrão Google Engineering")
        print("   YouTube • TikTok • Instagram Reels • Pinterest • Twitter/X • Facebook • Vimeo")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Baixador Universal de Mídias - Padrão Google Engineering (YouTube, TikTok, Reels, Pinterest, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", nargs="?", help="URL direta do vídeo ou áudio para baixar")
    parser.add_argument("-u", "--url", dest="opt_url", help="URL direta do vídeo ou áudio para baixar")
    parser.add_argument("-a", "--audio", action="store_true", help="Baixa apenas a faixa de áudio em MP3 de alta qualidade")
    parser.add_argument("-q", "--quality", type=int, default=1080, help="Resolução máxima do vídeo em pixels (ex: 720, 1080, 2160). Padrão: 1080")
    parser.add_argument("-o", "--output-dir", default="downloads", help="Diretório base de downloads (padrão: 'downloads')")
    parser.add_argument("-f", "--file", dest="file_path", help="Arquivo de texto (.txt) contendo uma lista de links para baixar em lote")
    parser.add_argument("--open", action="store_true", help="Abre a pasta de destino no Windows Explorer após concluir o download")

    args = parser.parse_args()
    print_banner()

    media_type = "audio" if args.audio else "video"
    target_url = args.url or args.opt_url

    # Modo 1: Lote via arquivo de texto
    if args.file_path:
        if not os.path.exists(args.file_path):
            print(f"Arquivo não encontrado: {args.file_path}")
            sys.exit(1)

        with open(args.file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

        print(f"\nIniciando download de {len(urls)} links selecionados...\n")
        for idx, u in enumerate(urls, 1):
            print(f"[{idx}/{len(urls)}] Baixando: {u}")
            download_single_media(
                u,
                base_downloads_dir=args.output_dir,
                media_type=media_type,
                max_height=args.quality
            )
        print("\nTodos os downloads foram concluídos!")
        if args.open:
            _open_folder_in_explorer(args.output_dir)
        return

    # Modo 2: URL direta via linha de comando
    if target_url:
        download_single_media(
            target_url,
            base_downloads_dir=args.output_dir,
            media_type=media_type,
            max_height=args.quality,
            open_folder_when_done=args.open
        )
        return

    # Modo 3: Interativo (quando executado sem argumentos via terminal ou duplo clique)
    if HAS_RICH and console:
        rprint("[bold cyan]➤ Modo Interativo Ativado[/bold cyan]")
        rprint("[dim]Cole qualquer link de vídeo ou reel da internet (YouTube, TikTok, Instagram, Pinterest, Twitter, etc.).[/dim]\n")
        try:
            url_input = console.input("[bold yellow]➤ Cole a URL do vídeo:[/bold yellow] ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nCancelado pelo usuário.")
            return

        if not url_input:
            print("Nenhuma URL informada. Encerrando.")
            return

        rprint("\n[cyan]Escolha o formato desejado:[/cyan]")
        rprint("  [bold white][1][/bold white] 🎬 Vídeo Completo em Alta Qualidade (MP4)")
        rprint("  [bold white][2][/bold white] 🎧 Apenas Áudio / Música / Podcast (MP3)")
        try:
            choice = console.input("\n[bold yellow]➤ Opção (padrão 1):[/bold yellow] ").strip()
        except (KeyboardInterrupt, EOFError):
            return

        selected_type = "audio" if choice == "2" else "video"
        download_single_media(
            url_input,
            base_downloads_dir=args.output_dir,
            media_type=selected_type,
            max_height=args.quality,
            open_folder_when_done=True
        )
    else:
        try:
            url_input = input("➤ Cole a URL do vídeo: ").strip()
        except (KeyboardInterrupt, EOFError):
            return
        if not url_input:
            return
        choice = input("Opção: [1] Vídeo MP4 ou [2] Áudio MP3 (padrão 1): ").strip()
        selected_type = "audio" if choice == "2" else "video"
        download_single_media(
            url_input,
            base_downloads_dir=args.output_dir,
            media_type=selected_type,
            max_height=args.quality,
            open_folder_when_done=True
        )


if __name__ == "__main__":
    main()
