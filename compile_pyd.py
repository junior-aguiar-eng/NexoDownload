#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Compilação C Nativa (Cython + MSVC) para Blindagem Antirreversa.
Compila os módulos vitais de negócio e segurança em binários de máquina C (.pyd).
"""

import sys
import os
import shutil
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Suporte UTF-8 no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

MODULES_TO_COMPILE = [
    BASE_DIR / "web_app" / "security_engine.py",
    BASE_DIR / "web_app" / "prive_engine.py",
    BASE_DIR / "web_app" / "spotify_engine.py",
    BASE_DIR / "web_app" / "apple_music_engine.py",
    BASE_DIR / "web_app" / "audio_processor.py",
    BASE_DIR / "web_app" / "updater_engine.py"
]

def compile_modules():
    print("=" * 70)
    print(" [CYTHON] INICIANDO COMPILAÇÃO C NATIVA DOS MÓDULOS DE SEGURANÇA E NEGÓCIO")
    print("=" * 70)
    
    # Prepara setup_build.py temporário
    setup_script = BASE_DIR / "_cython_build.py"
    
    sources = [str(p.resolve()) for p in MODULES_TO_COMPILE if p.exists()]
    print(f"[+] Módulos identificados para compilação C:")
    for s in sources:
        print(f"    - {Path(s).name}")
        
    script_content = f"""# -*- coding: utf-8 -*-
import sys
from setuptools import setup, Extension
from Cython.Build import cythonize

modules = {repr(sources)}
ext_modules = cythonize(
    modules,
    compiler_directives={{
        'language_level': '3',
        'always_allow_keywords': True
    }},
    quiet=True
)

setup(
    name='nexo_native_modules',
    ext_modules=ext_modules
)
"""
    setup_script.write_text(script_content, encoding="utf-8")
    
    cmd = [
        sys.executable,
        str(setup_script),
        "build_ext",
        "--inplace"
    ]
    
    print(f"\n[+] Executando compilação MSVC...")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    
    # Limpeza do script temporário
    if setup_script.exists():
        setup_script.unlink(missing_ok=True)
        
    if res.returncode != 0:
        print("[-] Falha na compilação Cython.")
        return False

    # Move os binários gerados (.pyd no Windows, .so no Linux) para web_app/
    ext_pattern = "*.pyd" if sys.platform == "win32" else "*.so"
    for ext_file in BASE_DIR.glob(ext_pattern):
        dest = BASE_DIR / "web_app" / ext_file.name
        shutil.move(str(ext_file), str(dest))
        print(f"[+] Binário movido para: {dest}")

    # Valida presença dos binários em web_app/
    success_count = 0
    target_ext = ".pyd" if sys.platform == "win32" else ".so"
    for mod in MODULES_TO_COMPILE:
        stem = mod.stem
        matches = list((BASE_DIR / "web_app").glob(f"{stem}.*{target_ext}"))
        if matches:
            print(f"[OK] Módulo compilado em C puro: {matches[0].name}")
            success_count += 1
        else:
            print(f"[!] Aviso: Binário nativo para {stem} não foi encontrado.")

    # Remove arquivos intermediários .c
    for mod in MODULES_TO_COMPILE:
        c_file = mod.with_suffix(".c")
        if c_file.exists():
            c_file.unlink(missing_ok=True)

    build_dir = BASE_DIR / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir, ignore_errors=True)

    print("\n" + "=" * 70)
    print(f" [OK] {success_count}/{len(MODULES_TO_COMPILE)} MÓDULOS C NATIVOS BLINDADOS COM SUCESSO!")
    print("=" * 70)
    return success_count == len(MODULES_TO_COMPILE)

if __name__ == "__main__":
    success = compile_modules()
    sys.exit(0 if success else 1)
