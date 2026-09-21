# 🚀 YouTube Intelligence Transcriber & Organizer

Uma suíte de engenharia de software desenvolvida com rigor e arquitetura inspirados nos princípios da **Google**, projetada para transformar vídeos, shorts e transmissões ao vivo do YouTube em uma base de conhecimento estruturada, pesquisável e sumarizada.

---

## 🌟 Recursos Principais

- 🎯 **Parser Universal de URLs**: Aceita qualquer link do YouTube (`watch?v=`, `youtu.be/`, `/shorts/`, `/live/`, `/embed/` ou IDs diretos).
- 🏷️ **Metadados Ricos Oficiais**: Extrai título autêntico, nome do canal, URL do canal, thumbnail e duração através dos serviços de oEmbed da Google.
- ⏱️ **Transcrição Resiliente Multi-idioma**: Busca prioritária para Português (`pt`, `pt-BR`), com fallback adaptativo para Inglês (`en`), Espanhol (`es`) e tradução automática de contingência.
- 🧠 **Smart Paragraphing**: Elimina as frases picadas de 2 segundos das legendas automáticas brutas, agrupando em blocos semânticos coesos baseados em pausas e cadência.
- 📑 **Exportação Multi-formato de Alta Fidelidade**:
  1. `01_transcricao_formatada.md`: Leitura com timestamps hipertextuais clicáveis (abre o vídeo no minuto exato).
  2. `02_transcricao_pura.txt`: Texto corrido contínuo, perfeito para prompts de LLMs e pesquisas rápidas.
  3. `03_resumo_e_insights.md`: Relatório executivo com síntese, minutagem temática e conceitos-chave.
  4. `04_legendas.srt`: Legendas sincronizadas padrão SubRip para editores de vídeo (Premiere, DaVinci, CapCut).
  5. `05_legendas.vtt`: WebVTT para navegadores e players web.
  6. `06_caderno_cornell.md`: **Caderno de Estudos no Método Cornell** com tabela de pistas/perguntas ativas, anotações e síntese para revisão espaçada (compatível com Obsidian e Notion).
  7. `estudo_interativo.html`: **Study Player Interativo Local**, com player embutido do YouTube sincronizado à transcrição, botões de velocidade (1x a 2x), busca em tempo real com destaque e auto-scroll dinâmico.
  8. `metadados.json`: Schema completo em JSON com todas as estatísticas e segmentos temporais.
- 📚 **Catálogo Mestre `BIBLIOTECA.md`**: Índice consolidado atualizado incrementalmente a cada vídeo processado, com estatísticas de horas transcritas, palavras totais e links de acesso rápido.
- 🤖 **Motor de Síntese Híbrido**:
  - **Modo Google Gemini**: Se a variável `GEMINI_API_KEY` estiver configurada, gera resumos analíticos com inteligência de ponta via Gemini 2.5 Flash.
  - **Modo Algorítmico Local**: Motor interno baseado em relevância e pontuação TF-IDF heurística, funcionando 100% offline e sem custos.
- 🎨 **CLI Rica e Modo Interativo**: Interface moderna no terminal utilizando `rich`, com spinners, tabelas e avisos coloridos.

---

## 🛠️ Como Usar

### 1. Modo Interativo (Mais Fácil)
Basta rodar o script diretamente. Ele exibirá a interface gráfica no terminal e solicitará o link:
```bash
python resumidor.py
```

### 2. Linha de Comando (CLI)
Passe a URL diretamente como argumento:
```bash
python resumidor.py "https://www.youtube.com/watch?v=XHzzIHvi0BI"
```

#### Baixar o Vídeo (MP4) ou Áudio (Podcast) junto com a transcrição:
```bash
# Baixar vídeo completo em MP4 (720p/1080p):
python resumidor.py "LINK_DO_YOUTUBE" --video

# Baixar apenas o áudio para ouvir offline:
python resumidor.py "LINK_DO_YOUTUBE" --audio

# Baixar ambos:
python resumidor.py "LINK_DO_YOUTUBE" --video --audio
```

### 3. Pelo Painel Lateral da Extensão do Chrome
Basta clicar nos novos ícones no topo do painel:
- 🎬 **Ícone de Filme:** Baixa o vídeo em MP4 direto para a pasta da aula.
- 🎧 **Ícone de Fone:** Extrai e baixa o áudio podcast da aula.

### 3. Processamento em Lote (Batch com Múltiplos Vídeos)
Crie um arquivo `.txt` contendo uma lista de links (um por linha) e execute:
```bash
python resumidor.py --file lista_de_videos.txt
```

### 4. Usando Inteligência Artificial Google Gemini
Defina sua chave de API do Gemini no terminal ou passe via argumento:
```bash
# Via variável de ambiente:
set GEMINI_API_KEY=sua_chave_aqui

# Ou diretamente no comando:
python resumidor.py --url "https://youtu.be/SEU_VIDEO" --gemini-key "sua_chave_aqui"
```

---

## 📂 Estrutura de Pastas Gerada

```
transcricoes/
│
├── BIBLIOTECA.md                       # Catálogo mestre com índice navegável de todos os vídeos
│
└── Canal/                              # Organizado automaticamente por Canal
    └── YYYY-MM-DD_Titulo_Higienizado/
        ├── 01_transcricao_formatada.md
        ├── 02_transcricao_pura.txt
        ├── 03_resumo_e_insights.md
        ├── 04_legendas.srt
        ├── 05_legendas.vtt
        ├── 06_caderno_cornell.md
        ├── estudo_interativo.html
        └── metadados.json
```

---

## 📦 Distribuição & Aplicativo Desktop (Nexo Download)

- **Instalador Autônomo Windows:** [`dist/NexoDownload-Setup.exe`](file:///c:/Users/Boni%20Jr/Desktop/Transcrições%20YouTube/dist/NexoDownload-Setup.exe) (Setup único silencioso, com runtime, WebView2 e FFmpeg embutidos).
- **Verificação de Integridade:** [`dist/SHA256SUMS.txt`](file:///c:/Users/Boni%20Jr/Desktop/Transcrições%20YouTube/dist/SHA256SUMS.txt).
- **Extensão de Estudos:** [`chrome_extension/`](file:///c:/Users/Boni%20Jr/Desktop/Transcrições%20YouTube/chrome_extension) com o iniciador [`INICIAR_SERVIDOR_ESTUDOS.bat`](file:///c:/Users/Boni%20Jr/Desktop/Transcrições%20YouTube/INICIAR_SERVIDOR_ESTUDOS.bat).

---

## 🏛️ Arquitetura do Projeto

```
.
├── dist/                     # Saída oficial de release (NexoDownload-Setup.exe)
├── chrome_extension/         # Extensão Chrome/Edge (Side Panel com Cornell)
├── installer/                # Script NSIS Modern UI 2 (apenas build)
├── web_app/                  # Interface Web/Desktop (FastAPI + Jinja2 + JS)
├── youtube_engine/           # Motor de transcrição, IA Gemini e catalogação
├── downloads/                # Mídias locais baixadas
├── transcricoes/             # Acervo de estudos gerado
├── NexoDownload.spec         # Especificação oficial de compilação PyInstaller
├── build_installer.py        # Pipeline de compilação oficial (Spec + FFmpeg + NSIS)
├── main_desktop.py           # Launcher com WebView2 nativo e FastAPI assíncrono
├── resumidor.py              # CLI e Servidor de Transcrição
└── INICIAR_SERVIDOR_ESTUDOS.bat # Atalho 1-clique para servidor da extensão
```

