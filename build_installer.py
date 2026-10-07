#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Mestre de Build do Nexo Download - Mídia Digital Livre.
Pipeline Oficial: Python -> PyInstaller onedir -> Copia FFmpeg -> NSIS -> NexoDownload-Setup.exe
"""

import os
import sys
import shutil
import subprocess
import hashlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Suporte UTF-8 no Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def kill_running_processes():
    """Garante que instâncias anteriores de NexoDownload não bloqueiem arquivos."""
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", 
                 "Get-Process -Name NexoDownload -ErrorAction SilentlyContinue | Stop-Process -Force; "
                 "Get-CimInstance Win32_Process -Filter \"name = 'msedge.exe'\" | Where-Object { $_.CommandLine -like '*app_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
                capture_output=True,
                check=False
            )
        except Exception:
            pass
        
    app_profile = BASE_DIR / "web_app" / ".app_profile"
    if app_profile.exists():
        shutil.rmtree(app_profile, ignore_errors=True)


def step1_pyinstaller_onedir() -> bool:
    print("\n" + "=" * 70)
    print(" [1/3] COMPILANDO VIA SPEC OFICIAL (PyInstaller NexoDownload.spec)")
    print("=" * 70)

    spec_file = BASE_DIR / "NexoDownload.spec"
    if not spec_file.exists():
        print(f"[-] Erro: Arquivo {spec_file} não encontrado.")
        return False

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        str(spec_file)
    ]

    print(f"[+] Executando: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(BASE_DIR))
    if res.returncode != 0:
        print("[-] Erro durante a compilação do PyInstaller a partir do spec.")
        return False

    exe_file = BASE_DIR / "dist" / "NexoDownload" / "NexoDownload.exe"
    if not exe_file.exists():
        print(f"[-] Erro crítico: O executável {exe_file} NÃO foi gerado.")
        return False

    print(f"[+] Compilação concluída com sucesso. Binário verificado: {exe_file}")
    return True


def step2_bundle_dependencies() -> bool:
    print("\n" + "=" * 70)
    print(" [2/3] ACOPLANDO FFMPEG, FFPROBE E ATIVOS DIGITAIS")
    print("=" * 70)

    dist_dir = BASE_DIR / "dist" / "NexoDownload"
    exe_file = dist_dir / "NexoDownload.exe"
    if not exe_file.exists():
        print(f"[-] Erro Crítico: {exe_file} não existe no diretório de distribuição.")
        return False

    bin_dir = dist_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    # Localiza FFmpeg e FFprobe no sistema
    winget_links = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"
    ffmpeg_candidates = [
        BASE_DIR / "bin" / "ffmpeg.exe",
        BASE_DIR / "tools" / "ffmpeg.exe",
        winget_links / "ffmpeg.exe",
        Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        Path("C:/ffmpeg/bin/ffmpeg.exe")
    ]
    ffprobe_candidates = [
        BASE_DIR / "bin" / "ffprobe.exe",
        BASE_DIR / "tools" / "ffprobe.exe",
        winget_links / "ffprobe.exe",
        Path("C:/Program Files/ffmpeg/bin/ffprobe.exe"),
        Path("C:/ffmpeg/bin/ffprobe.exe")
    ]

    # Também checa PATH
    for p in os.environ.get("PATH", "").split(os.pathsep):
        if (Path(p) / "ffmpeg.exe").exists():
            ffmpeg_candidates.insert(0, Path(p) / "ffmpeg.exe")
        if (Path(p) / "ffprobe.exe").exists():
            ffprobe_candidates.insert(0, Path(p) / "ffprobe.exe")

    found_ffmpeg = next((f for f in ffmpeg_candidates if f.exists()), None)
    found_ffprobe = next((f for f in ffprobe_candidates if f.exists()), None)

    if found_ffmpeg:
        shutil.copy2(found_ffmpeg, bin_dir / "ffmpeg.exe")
        print(f"[+] FFmpeg acoplado: {bin_dir / 'ffmpeg.exe'}")
    else:
        print("[!] Aviso: ffmpeg.exe não localizado para inclusão automática.")

    if found_ffprobe:
        shutil.copy2(found_ffprobe, bin_dir / "ffprobe.exe")
        print(f"[+] FFprobe acoplado: {bin_dir / 'ffprobe.exe'}")

    # Garante cópia no BASE_DIR/bin para runtime de desenvolvimento
    dev_bin = BASE_DIR / "bin"
    dev_bin.mkdir(parents=True, exist_ok=True)
    if found_ffmpeg and not (dev_bin / "ffmpeg.exe").exists():
        shutil.copy2(found_ffmpeg, dev_bin / "ffmpeg.exe")
    if found_ffprobe and not (dev_bin / "ffprobe.exe").exists():
        shutil.copy2(found_ffprobe, dev_bin / "ffprobe.exe")

    # Garante que os .pyd de web_app estejam acoplados em dist/NexoDownload
    for pyd_file in (BASE_DIR / "web_app").glob("*.pyd"):
        dest_internal = dist_dir / "_internal" / "web_app" / pyd_file.name
        dest_internal.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pyd_file, dest_internal)
        
        dest_app = dist_dir / "web_app" / pyd_file.name
        dest_app.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pyd_file, dest_app)
        print(f"[+] Binário C (.pyd) acoplado: {pyd_file.name}")
        
    # Remove código fonte sensível (.py) das pastas de distribuição para blindagem total
    protected_stems = ["security_engine", "prive_engine", "spotify_engine", "apple_music_engine", "audio_processor", "updater_engine"]
    for stem in protected_stems:
        for py_path in dist_dir.rglob(f"{stem}.py"):
            py_path.unlink(missing_ok=True)
            print(f"[+] Código-fonte original {py_path.name} removido (blindado via binário C nativo)")

    # Copia ícone para a raiz do pacote
    ico_src = BASE_DIR / "web_app" / "static" / "icons" / "app_icon.ico"
    if ico_src.exists():
        shutil.copy2(ico_src, dist_dir / "app_icon.ico")

    # Garante acoplamento do módulo audio_engine e pastas de modelos
    audio_engine_src = BASE_DIR / "audio_engine"
    if audio_engine_src.exists():
        for target_ae in [dist_dir / "audio_engine", dist_dir / "_internal" / "audio_engine"]:
            target_ae.mkdir(parents=True, exist_ok=True)
            for item in audio_engine_src.iterdir():
                if item.is_file() and not item.name.endswith(".pyc"):
                    shutil.copy2(item, target_ae / item.name)
            (target_ae / "modelos").mkdir(parents=True, exist_ok=True)
        print("[+] Módulo de áudio & IA acoplado no pacote de distribuição.")

    return True


def step0_cython_compilation() -> bool:
    print("\n" + "=" * 70)
    print(" [0/3] BLINDAGEM ANTIRREVERSA (Cython C Native -> .pyd)")
    print("=" * 70)
    try:
        from compile_pyd import compile_modules
        return compile_modules()
    except Exception as e:
        print(f"[-] Erro na compilação Cython: {e}")
        return False


def step3_compile_nsis_installer() -> bool:
    print("\n" + "=" * 70)
    print(" [3/3] GERANDO INSTALADOR FINAL (NSIS -> NexoDownload-Setup.exe)")
    print("=" * 70)

    makensis_candidates = [
        BASE_DIR / "tools" / "nsis" / "makensis.exe",
        Path("C:/Program Files (x86)/NSIS/makensis.exe"),
        Path("C:/Program Files/NSIS/makensis.exe")
    ]
    makensis_exe = next((m for m in makensis_candidates if m.exists()), None)

    if not makensis_exe:
        for p in os.environ.get("PATH", "").split(os.pathsep):
            if (Path(p) / "makensis.exe").exists():
                makensis_exe = Path(p) / "makensis.exe"
                break

    if not makensis_exe:
        print("[-] makensis.exe não foi encontrado em tools/nsis nem no sistema.")
        return False

    nsi_script = BASE_DIR / "installer" / "installer.nsi"
    print(f"[+] Compilando {nsi_script} com {makensis_exe}...")
    
    res = subprocess.run(
        [str(makensis_exe), "/INPUTCHARSET", "UTF8", str(nsi_script)],
        cwd=str(BASE_DIR / "installer")
    )
    if res.returncode != 0:
        print("[-] Erro durante a compilação do instalador NSIS.")
        return False

    setup_exe = BASE_DIR / "dist" / "NexoDownload-Setup.exe"
    if setup_exe.exists():
        size_mb = setup_exe.stat().st_size / (1024 * 1024)
        
        sha256 = hashlib.sha256(setup_exe.read_bytes()).hexdigest().upper()
        sha_file = BASE_DIR / "dist" / "SHA256SUMS.txt"
        sha_file.write_text(f"{sha256}  NexoDownload-Setup.exe\n", encoding="utf-8")

        print("\n" + "=" * 70)
        print(" [OK] INSTALADOR OFICIAL CRIADO COM SUCESSO!")
        print(f"      Arquivo: {setup_exe}")
        print(f"      Tamanho: {size_mb:.2f} MB")
        print(f"      SHA256:  {sha256}")
        print("=" * 70)
        return True
    
    return False


def main():
    print("=" * 70)
    print("  NEXO DOWNLOAD - MÍDIA DIGITAL LIVRE")
    print("  Pipeline de Distribuição Profissional para Windows")
    print("=" * 70)

    kill_running_processes()
    
    # 0. Blindagem antirreversa (Cython C native)
    if not step0_cython_compilation():
        sys.exit(1)

    # 1. Compila backend com PyInstaller
    if not step1_pyinstaller_onedir():
        sys.exit(1)

    # 2. Adiciona binários (FFmpeg), .pyd e remove códigos sensíveis
    if not step2_bundle_dependencies():
        sys.exit(1)

    # 3. Compila o instalador NSIS
    if not step3_compile_nsis_installer():
        sys.exit(1)


if __name__ == "__main__":
    main()
