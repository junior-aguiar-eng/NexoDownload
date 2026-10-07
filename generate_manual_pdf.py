#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gerador do Manual Didático em PDF - Nexo Download Pro 2.2.0
Executa o motor Edge Chromium Headless para renderizar o manual em PDF.
"""

import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "manual_document.html"
PDF_PATH = BASE_DIR / "Manual_do_Usuario_NexoDownload_Pro.pdf"

def generate_pdf():
    print("=" * 65)
    print(" GERADOR DE MANUAL DIDÁTICO EM PDF - NEXO DOWNLOAD PRO")
    print("=" * 65)

    if not HTML_PATH.exists():
        print(f"[-] Arquivo HTML não encontrado: {HTML_PATH}")
        return False

    edge_candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    edge_exe = next((e for e in edge_candidates if e.exists()), None)
    if not edge_exe:
        print("[-] Navegador Edge não encontrado no sistema.")
        return False

    print(f"[+] Compilando PDF gráfico de alta fidelidade com {edge_exe.name}...")
    
    cmd = [
        str(edge_exe),
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={PDF_PATH}",
        HTML_PATH.as_uri()
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if not PDF_PATH.exists():
        print(f"[-] Erro na compilação do PDF: {res.stderr}")
        return False

    pdf_size_mb = PDF_PATH.stat().st_size / (1024 * 1024)
    print(f"[+] PDF gerado com sucesso!")
    print(f"    Arquivo: {PDF_PATH}")
    print(f"    Tamanho: {pdf_size_mb:.2f} MB")

    try:
        import pymupdf
        doc = pymupdf.open(str(PDF_PATH))
        print(f"    Total de Páginas Renderizadas: {len(doc)} páginas")
        for i, page in enumerate(doc):
            first_line = page.get_text().splitlines()[0] if page.get_text().splitlines() else ""
            print(f"    - Página {i+1}: {first_line[:50]}")
        doc.close()
    except Exception as e:
        print(f"[*] Verificação PyMuPDF: {e}")

    print("=" * 65)
    print(" [OK] MANUAL EM PDF PRONTO PARA ENVIO E IMPRESSÃO!")
    print("=" * 65)
    return True

if __name__ == "__main__":
    generate_pdf()
