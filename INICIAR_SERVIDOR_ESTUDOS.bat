@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Servidor de Estudos - YouTube Study Intelligence

echo ======================================================================
echo    YOUTUBE STUDY INTELLIGENCE - SERVIDOR LOCAL DE ESTUDOS
echo    Porta: 8765 ^| Integracao com Extensao Google Chrome / Edge
echo ======================================================================
echo.
echo [*] Verificando ambiente e liberando portas...

:: 1. Libera a porta 8765 caso algum processo orfao antigo tenha ficado preso
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :8765 ^| findstr LISTENING 2^>nul') do (
    if "%%a" neq "0" (
        echo [*] Liberando porta 8765 (processo PID %%a)...
        taskkill /F /PID %%a >nul 2>nul
    )
)

set "PYTHON_CMD="

:: 2. Tenta python no PATH
where python >nul 2>nul
if %errorlevel% equ 0 (
    set "PYTHON_CMD=python"
)

:: 3. Tenta py launcher se python nao estiver no PATH
if not defined PYTHON_CMD (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set "PYTHON_CMD=py -3"
    )
)

:: 4. Tenta caminho exato da instalacao do Python no Windows
if not defined PYTHON_CMD (
    if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
        set "PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python314\python.exe""
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
        set "PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe""
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe""
    ) else if exist "%ProgramFiles%\Python314\python.exe" (
        set "PYTHON_CMD="%ProgramFiles%\Python314\python.exe""
    ) else if exist "%ProgramFiles%\Python313\python.exe" (
        set "PYTHON_CMD="%ProgramFiles%\Python313\python.exe""
    )
)

if not defined PYTHON_CMD (
    echo [ERRO] O interpretador Python nao foi encontrado no sistema!
    echo Certifique-se de ter o Python instalado e configurado no PATH do Windows.
    echo.
    pause
    exit /b 1
)

if not exist "resumidor.py" (
    echo [ERRO] Arquivo resumidor.py nao encontrado na pasta atual: %cd%
    echo.
    pause
    exit /b 1
)

echo [*] Interpretador Python: %PYTHON_CMD%
echo [!] Servidor iniciando na porta 8765. Mantenha esta janela aberta.
echo.

%PYTHON_CMD% resumidor.py --serve

if %errorlevel% neq 0 (
    echo.
    echo [!] O servidor foi encerrado com codigo de saida: %errorlevel%
)

echo.
pause
