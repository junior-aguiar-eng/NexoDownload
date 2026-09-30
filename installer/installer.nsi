; ============================================================================
; Nexo Download - Mídia Digital Livre
; Script Oficial de Instalação Windows (Minimalista Moderno - Estilo Spotify/Discord)
; ============================================================================

Unicode true
!include "FileFunc.nsh"
!include "LogicLib.nsh"

; Definições Gerais do Aplicativo
!define PRODUCT_NAME "Nexo Download"
!define PRODUCT_SUBTITLE "Mídia Digital Livre"
!define PRODUCT_PUBLISHER "Nexo Digital"
!define PRODUCT_VERSION "2.1.0"
!define PRODUCT_EXE "NexoDownload.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\NexoDownload"

; Configurações do Executável
Name "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"
OutFile "..\dist\NexoDownload-Setup.exe"
InstallDir "$LOCALAPPDATA\Programs\NexoDownload"
RequestExecutionLevel user
SetCompressor /SOLID lzma

; Ícones
Icon "..\web_app\static\icons\app_icon.ico"
UninstallIcon "..\web_app\static\icons\app_icon.ico"

; Remove completamente rodapé Nullsoft e linha divisória
BrandingText " "

; Oculta listagem técnica de arquivos e fecha automaticamente ao concluir
ShowInstDetails nevershow
ShowUninstDetails nevershow
AutoCloseWindow true

; ============================================================================
; Página Única de Instalação Silenciosa com Barra Fluida
; ============================================================================
Page instfiles "" SetupInstShow

; Páginas de Desinstalação
UninstPage uninstConfirm
UninstPage instfiles

; ============================================================================
; Personalização Visual: Transforma em Card Compacto Moderno
; ============================================================================
Function SetupInstShow
    ; Título limpo da janela
    SendMessage $HWNDPARENT 0x000C 0 "STR:Instalando ${PRODUCT_NAME} Pro..."

    ; Oculta todos os botões clássicos dos anos 90 e divisórias
    GetDlgItem $0 $HWNDPARENT 1    ; Próximo / Fechar
    ShowWindow $0 0
    GetDlgItem $0 $HWNDPARENT 2    ; Cancelar
    ShowWindow $0 0
    GetDlgItem $0 $HWNDPARENT 3    ; Voltar
    ShowWindow $0 0
    GetDlgItem $0 $HWNDPARENT 1035 ; Linha divisória cinza
    ShowWindow $0 0
    GetDlgItem $0 $HWNDPARENT 1028 ; Texto Nullsoft
    ShowWindow $0 0

    ; Redimensiona e centraliza a janela no meio da tela (Card 440 x 175)
    System::Call "user32::GetSystemMetrics(i 0) i .r1" ; Largura da tela
    System::Call "user32::GetSystemMetrics(i 1) i .r2" ; Altura da tela
    
    IntOp $3 $1 - 440
    IntOp $3 $3 / 2 ; Posição X centralizada
    IntOp $4 $2 - 175
    IntOp $4 $4 / 2 ; Posição Y centralizada
    
    System::Call "user32::SetWindowPos(i $HWNDPARENT, i 0, i $3, i $4, i 440, i 175, i 0x0040)"

    ; Localiza e ajusta os controles dentro da janela interna
    FindWindow $0 "#32770" "" $HWNDPARENT
    ${If} $0 != 0
        ; Preenche o diálogo interno
        System::Call "user32::SetWindowPos(i $0, i 0, i 0, i 0, i 440, i 145, i 0x0040)"

        ; Reposiciona o texto de status (ID 1006)
        GetDlgItem $1 $0 1006
        ${If} $1 != 0
            System::Call "user32::SetWindowPos(i $1, i 0, i 35, i 26, i 370, i 22, i 0x0040)"
        ${EndIf}

        ; Reposiciona a barra de progresso (ID 1004) - "fiozinho" moderno
        GetDlgItem $2 $0 1004
        ${If} $2 != 0
            System::Call "user32::SetWindowPos(i $2, i 0, i 35, i 58, i 370, i 15, i 0x0040)"
        ${EndIf}
    ${EndIf}
FunctionEnd

; ============================================================================
; Seção Principal de Instalação (Silenciosa e Direta)
; ============================================================================
Section "InstalacaoNexo" SecInstall
    SetOutPath "$INSTDIR"

    DetailPrint "Instalando Nexo Download Pro..."
    Sleep 300

    ; Extrai o pacote de distribuição blindado
    SetDetailsPrint none
    File /r "..\dist\NexoDownload\*.*"
    File "..\web_app\static\icons\app_icon.ico"
    SetDetailsPrint both

    DetailPrint "Configurando atalhos e sistema..."

    ; Desinstalador Oficial
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Atalho na Área de Trabalho
    CreateShortcut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0 SW_SHOWNORMAL "" "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"

    ; Atalho no Menu Iniciar
    CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}" "" "$INSTDIR\${PRODUCT_EXE}" 0 SW_SHOWNORMAL "" "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"
    CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar ${PRODUCT_NAME}.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0

    ; Registro Oficial no Painel do Windows (Adicionar/Remover Programas)
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\app_icon.ico"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "${PRODUCT_UNINST_KEY}" "InstallLocation" "$INSTDIR"
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoModify" 1
    WriteRegDWORD HKCU "${PRODUCT_UNINST_KEY}" "NoRepair" 1

    DetailPrint "Finalizando..."
    Sleep 400

    ; Inicia automaticamente o aplicativo e fecha o instalador na hora
    Exec "$INSTDIR\${PRODUCT_EXE}"
    Quit
SectionEnd

; ============================================================================
; Desinstalação Limpa (Preserva Arquivos de Mídia na Pasta downloads/)
; ============================================================================
Section "Uninstall"
    ; Remove atalhos
    Delete "$DESKTOP\${PRODUCT_NAME}.lnk"
    Delete "$DESKTOP\${PRODUCT_NAME} - ${PRODUCT_SUBTITLE}.lnk"
    Delete "$DESKTOP\Nexo.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
    Delete "$SMPROGRAMS\${PRODUCT_NAME}\Desinstalar ${PRODUCT_NAME}.lnk"
    RMDir "$SMPROGRAMS\${PRODUCT_NAME}"

    ; Remove entradas do Registro
    DeleteRegKey HKCU "${PRODUCT_UNINST_KEY}"

    ; Remove binários do aplicativo
    Delete "$INSTDIR\${PRODUCT_EXE}"
    Delete "$INSTDIR\Uninstall.exe"
    Delete "$INSTDIR\app_icon.ico"
    RMDir /r "$INSTDIR\_internal"
    RMDir /r "$INSTDIR\bin"
    RMDir /r "$INSTDIR\web_app"

    ; Tenta remover pasta raiz apenas se estiver vazia (downloads/ preservados)
    RMDir "$INSTDIR"
SectionEnd
