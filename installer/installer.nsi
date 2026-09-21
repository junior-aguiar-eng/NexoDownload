; ============================================================================
; Nexo Download - Mídia Digital Livre
; Script Oficial de Instalação Windows (NSIS Modern UI 2)
; Padrão Google Engineering: Experiência fluida, silenciosa, sem console ou jargão técnico
; ============================================================================

!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; Habilita binário Unicode nativo (corrige caminhos com acentos como 'Transcrições')
Unicode true

; Definições Gerais do Aplicativo
!define PRODUCT_NAME "Nexo Download"
!define PRODUCT_SUBTITLE "Mídia Digital Livre"
!define PRODUCT_PUBLISHER "Nexo Digital"
!define PRODUCT_VERSION "2.0.0"
!define PRODUCT_EXE "NexoDownload.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\NexoDownload"

; Configurações do Instalador
Name "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"
OutFile "..\dist\NexoDownload-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\NexoDownload"
RequestExecutionLevel user
SetCompressor /SOLID lzma

; Ícones
!define MUI_ICON "..\web_app\static\icons\app_icon.ico"
!define MUI_UNICON "..\web_app\static\icons\app_icon.ico"

; Customização da Interface Modern UI 2
!define MUI_HEADERIMAGE
!define MUI_ABORTWARNING
!define MUI_BGCOLOR "F8FAFC"

; Oculta completamente logs técnicos, extração detalhada de arquivos e chamadas internas
ShowInstDetails nevershow
ShowUninstDetails nevershow

; ============================================================================
; Páginas da Instalação
; ============================================================================
!define MUI_PAGE_CUSTOMFUNCTION_SHOW SetupInstShow
!insertmacro MUI_PAGE_INSTFILES

; Páginas da Desinstalação
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Idioma
!insertmacro MUI_LANGUAGE "PortugueseBR"

; ============================================================================
; Personalização Visual da Janela
; ============================================================================
Function SetupInstShow
    ; Customiza títulos da janela para exibir somente a marca Nexo
    SendMessage $HWNDPARENT 0x000C 0 "STR:${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"
FunctionEnd

; ============================================================================
; Seção Principal de Instalação (Fluxo Amigável e Abstrato)
; ============================================================================
Section "InstalacaoNexo" SecInstall
    SetOutPath "$INSTDIR"

    ; 1. Estado: Preparando instalação
    DetailPrint "Preparando instalação..."
    Sleep 400

    ; 2. Verificação de Integridade do WebView2 Runtime
    DetailPrint "Verificando componentes do sistema..."
    ReadRegStr $0 HKLM "SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-F504-4115-8A06-39980F952A4F}" "pv"
    ${If} $0 == ""
        ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\{F3017226-F504-4115-8A06-39980F952A4F}" "pv"
    ${EndIf}
    ; Se o WebView2 já estiver presente, não reinstala
    Sleep 300

    ; 3. Estado: Instalando Nexo Download Pro
    DetailPrint "Instalando Nexo Download..."
    ; Suprime completamente a exibição de nomes de arquivos e pastas sendo extraídos
    SetDetailsPrint none
    File /r "..\dist\NexoDownload\*.*"
    File "..\web_app\static\icons\app_icon.ico"
    SetDetailsPrint both

    ; 4. Estado: Configurando Nexo Download
    DetailPrint "Configurando Nexo Download..."
    
    ; Define explicitamente o diretório de trabalho do atalho como $INSTDIR
    SetOutPath "$INSTDIR"
    
    ; Criação do Desinstalador
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Atalho na Área de Trabalho (aponta diretamente para o executável oficial instalado)
    CreateShortcut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0 SW_SHOWNORMAL "" "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"

    ; Atalhos no Menu Iniciar
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0 SW_SHOWNORMAL "" "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"
    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar ${PRODUCT_NAME}.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0

    ; Registro Oficial no Windows (Adicionar/Remover Programas)
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\app_icon.ico"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoRepair" 1

    ; 5. Estado: Finalizando
    DetailPrint "Finalizando..."
    Sleep 500

    DetailPrint "Instalação concluída."
    Sleep 400

    ; Abertura Imediata do Aplicativo (Experiência 1-Clique)
    Exec "$INSTDIR\${PRODUCT_EXE}"
SectionEnd

; ============================================================================
; Seção de Desinstalação (Preserva Mídias e Remove Somente o Aplicativo)
; ============================================================================
Section "Uninstall"
    ; Remove Atalhos
    Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
    Delete "$DESKTOP\${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}.lnk"
    Delete "$DESKTOP\Nexo.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar ${PRODUCT_NAME}.lnk"
    RMDir "$SMPROGRAMS\${PRODUCT_NAME}"

    ; Remove Entradas do Registro
    DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"

    ; Remove Binários e Arquivos Internos do Aplicativo
    Delete "$INSTDIR\${PRODUCT_EXE}"
    Delete "$INSTDIR\Uninstall.exe"
    Delete "$INSTDIR\app_icon.ico"
    RMDir /r "$INSTDIR\_internal"
    RMDir /r "$INSTDIR\bin"

    ; IMPORTANTE: A pasta downloads/ é mantida intacta para preservar as mídias do usuário!
    ; Tenta remover a pasta raiz caso vazia, sem forçar
    RMDir "$INSTDIR"
SectionEnd
