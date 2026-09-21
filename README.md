# ⚡ Nexo Download Pro — Mídia Digital Livre

<div align="center">

![Nexo Download Banner](web_app/static/img/app_banner.png)

**Central Desktop de Download e Processamento Multimídia de Alta Fidelidade**  
*Blindagem C Nativa • Licenciamento HWID Criptográfico • Resolução Inteligente de Álbuns • Auto-Updater Silencioso*

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Cython](https://img.shields.io/badge/C--Native-Cython%203.0-FFD43B?style=for-the-badge&logo=c&logoColor=black)](https://cython.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-WebSocket%20Live-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Windows](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011%20x64-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com)
[![Status](https://img.shields.io/badge/Release-v2.1.0-10B981?style=for-the-badge)](https://github.com/junior-aguiar-eng/NexoDownload/releases)

</div>

---

## 📖 Visão Geral

O **Nexo Download Pro** é uma suíte desktop autônoma, veloz e elegante projetada para download, conversão e catalogação de áudio e vídeo de mais de 10 plataformas em qualidade máxima. 

Diferente de baixadores convencionais, o Nexo Download integra **injeção atômica de metadados oficiais** (capa HD embutida no Windows Explorer, artista, álbum, ano, gênero), processamento local via **FFmpeg**, motor inteligente de resolução de **álbuns e playlists completos** (Spotify e Apple Music), blindagem antirreversa em código nativo C e instalador minimalista ultra silencioso.

---

## 🌟 Principais Recursos

### 1. 🎵 Resolução Inteligente de Álbuns & Playlists
- **Spotify & Apple Music:** Ao colar o link de um álbum (ex: *Sam Smith: Music Room*) ou playlist, o motor mapeia todas as faixas da coleção.
- **Faixas Individuais + Álbum Completo:** Salva em pasta dedicada todas as faixas separadas numeradas e tagueadas (`01 - Faixa.mp3`, `02 - Faixa.mp3`...) e simultaneamente cria o arquivo mesclado sem perdas (`{Álbum} (Álbum Completo).mp3`).

### 2. 🎬 Metadados Atômicos & Capas em Alta Resolução
- **Vídeos MP4:** Capas oficiais embutidas diretamente no container MP4 através de atom tagging (`covr`), permitindo visualização de miniaturas no Windows Explorer e reprodutores de mídia.
- **Áudio MP3 320 kbps:** Tags ID3v2.4 completas com capa HD quadrada de alta resolução, nome do artista, álbum, número da faixa e data de lançamento.

### 3. 🛡️ Blindagem Antirreversa C-Native
- Os núcleos vitais da aplicação (`security_engine`, `spotify_engine`, `apple_music_engine`, `audio_processor`, `updater_engine`) são transcompilados para linguagem C e compilados como binários nativos de 64 bits (`.pyd` via Cython + MSVC C++).
- Os códigos-fonte em Python são completamente suprimidos dos pacotes de distribuição para proteção de propriedade intelectual.

### 4. 🔐 Licenciamento Criptográfico HWID-Lock
- **Trava de Máquina Física:** Gera uma identidade única e inalterável (`HWID`) baseada no `MachineGuid` do Windows, UUID da placa-mãe e ID do processador.
- **Assinatura Criptográfica:** Licenças assinadas via HMAC-SHA256 com chave mestra AES, permitindo ativação offline instantânea de licenças permanentes ou com expiração temporal (ex: 30 dias).

### 5. 🎨 Interface Moderna & 5 Temas Visuais
- Design moderno com glassmorphism, microanimações e feedback de progresso em tempo real via WebSocket.
- Seletor nativo de pastas integrado à API do Windows Explorer (`/api/select-folder`).
- **5 Paletas de Cores:**
  - 🌲 **Esmeralda Profundo** (Padrão)
  - 🌊 **Ciano Cibernético**
  - 🔮 **Roxo Cósmico**
  - 🌅 **Sunset Neon**
  - 🔷 **Azul Noturno**

### 6. 🔄 Auto-Updater Silencioso em 1 Clique
- Comunicação direta com a API do GitHub Releases para checagem assíncrona de novas versões.
- Notificação modal amigável com visualização do *changelog*.
- Download em segundo plano com barra de progresso e aplicação silenciosa (`/S`) sem intervenção manual.

### 7. 📦 Instalador Minimalista ("Fiozinho")
- Instalador executável compilado via NSIS (`NexoDownload-Setup.exe`).
- Oculta completamente a descompactação de listas de arquivos (`SetDetailsPrint none`), exibindo apenas a marca e a barra de progresso suave estilo Spotify/Discord.

---

## 🌐 Plataformas Suportadas

| Plataforma | Áudio | Vídeo | Resolução de Coleções / Álbuns |
| :--- | :---: | :---: | :---: |
| **YouTube** | MP3 (320 kbps) | Até 4K HDR | Playlists e Canais |
| **Spotify** | MP3 (320 kbps Master) | — | Álbuns completos & Playlists |
| **Apple Music** | MP3 (320 kbps Master) | — | Álbuns completos & Playlists |
| **TikTok** | MP3 | MP4 HD Sem Marca | Vídeos individuais |
| **Instagram** | MP3 | MP4 HD | Reels, Stories e Vídeos |
| **Twitter / X** | MP3 | MP4 HD | Vídeos e GIFs de tweets |
| **SoundCloud** | MP3 Original | — | Músicas e Sets |
| **Twitch** | MP3 | MP4 HD | Clipes e VODs |
| **Facebook** | MP3 | MP4 HD | Vídeos públicos |
| **Pinterest** | MP3 | MP4 HD | Vídeos e Pins multimídia |

---

## 🚀 Como Executar em Desenvolvimento

### Pré-requisitos
- Python 3.11 ou superior (x64)
- Ferramentas de compilação C++ (Microsoft Visual C++ 14.0+ ou Visual Studio Build Tools)
- FFmpeg (disponível na pasta `bin/` ou no PATH do sistema)

### Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/junior-aguiar-eng/NexoDownload.git
cd NexoDownload

# 2. Criar e ativar o ambiente virtual (opcional, recomendado)
python -m venv venv
.\venv\Scripts\activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Compilar os módulos C nativos (.pyd)
python compile_pyd.py

# 5. Iniciar o aplicativo desktop
python main_desktop.py
```

O aplicativo iniciará o servidor local e abrirá automaticamente a janela do Nexo Download.

---

## 🔑 Gerador Administrativo de Licenças

Para gerar chaves de ativação para clientes vinculadas ao Hardware ID:

```bash
# Gerar licença permanente para um HWID de cliente
python gerador_licencas.py NEXO-XXXX-XXXX-XXXX

# Gerar licença com período de teste ou validade (ex: 30 dias)
python gerador_licencas.py NEXO-XXXX-XXXX-XXXX --dias 30
```

---

## 🏗️ Empacotamento do Instalador (Setup.exe)

Para compilar o pacote binário final e o instalador executável:

```bash
python build_installer.py
```

O script executará:
1. Compilação dos motores em bibliotecas C nativas (`.pyd`).
2. Congelamento via PyInstaller com limpeza de arquivos `.py` desnecessários.
3. Incorporação do FFmpeg e dependências estáticas.
4. Geração do instalador NSIS minimalista em `dist/NexoDownload-Setup.exe`.
5. Cálculo do hash criptográfico em `dist/SHA256SUMS.txt`.

---

## 📁 Arquitetura do Repositório

```plaintext
NexoDownload/
├── installer/
│   └── installer.nsi          # Script NSIS do instalador minimalista silencioso
├── web_app/
│   ├── app.py                 # Servidor de rotas e WebSockets (FastAPI)
│   ├── security_engine.py     # Motor HWID, hashing HMAC e validação de licença
│   ├── spotify_engine.py      # Resolução de metadados de álbuns/playlists Spotify
│   ├── apple_music_engine.py  # Parser e extrator estruturado do Apple Music
│   ├── audio_processor.py     # Injeção ID3/MP4 e concatenação de álbuns
│   ├── updater_engine.py      # Verificador remoto e instalador de updates
│   ├── static/                # Estilos CSS, temas dinâmicos, JS e ícones
│   └── templates/             # Interface HTML5 moderna
├── main_desktop.py            # Ponto de entrada do executável desktop
├── compile_pyd.py             # Compilador Cython C-Native (.pyd)
├── build_installer.py         # Pipeline de build automatizado e instalador NSIS
├── gerador_licencas.py        # Utilitário CLI para geração de licenças
├── NexoDownload.spec          # Especificação de empacotamento PyInstaller
├── requirements.txt           # Dependências do projeto
└── version.json               # Manifest de versão do Auto-Updater
```

---

## 📄 Licença & Propriedade

Desenvolvido exclusivamente por **Junior Aguiar** ([@junior-aguiar-eng](https://github.com/junior-aguiar-eng)).  
Todos os direitos reservados.
