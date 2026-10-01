"""
Gerador do Study Player HTML Interativo Local.
Ambiente integrado de estudos com sincronização em tempo real entre o player do YouTube e a transcrição.
"""

import json
from typing import List
from .models import VideoMetadata, ParagraphBlock


def generate_study_player_html(
    metadata: VideoMetadata,
    paragraphs: List[ParagraphBlock],
    cornell_notes_markdown: str
) -> str:
    """
    Gera página HTML standalone com YouTube IFrame API e sincronização bidirecional.
    """
    # Serializa os parágrafos para embutir diretamente no JavaScript
    paragraphs_json = json.dumps([
        {
            "id": i,
            "start": p.start_time,
            "end": p.end_time,
            "timestamp": p.format_timestamp(),
            "text": p.text
        }
        for i, p in enumerate(paragraphs)
    ], ensure_ascii=False)

    escaped_title = metadata.title.replace('"', '&quot;')
    escaped_channel = metadata.channel_name.replace('"', '&quot;')
    
    # Converte Markdown do Cornell de forma simplificada para HTML seguro dentro da aba
    escaped_cornell_text = json.dumps(cornell_notes_markdown, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Study Player: {escaped_title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-main: #0b0f19;
      --bg-card: #131b2e;
      --bg-card-hover: #1c2742;
      --bg-active: rgba(56, 189, 248, 0.12);
      --border-color: #23304d;
      --border-active: #38bdf8;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --accent: #38bdf8;
      --accent-glow: rgba(56, 189, 248, 0.4);
      --badge-bg: #1e293b;
      --mark-bg: #fef08a;
      --mark-text: #854d0e;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-main);
      color: var(--text-primary);
      height: 100vh;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}

    /* Top Navigation Bar */
    header {{
      background-color: var(--bg-card);
      border-bottom: 1px solid var(--border-color);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      z-index: 10;
    }}

    .header-info {{
      display: flex;
      align-items: center;
      gap: 12px;
      overflow: hidden;
    }}

    .logo-badge {{
      background: linear-gradient(135deg, #0284c7, #38bdf8);
      color: white;
      font-weight: 700;
      font-size: 13px;
      padding: 6px 12px;
      border-radius: 8px;
      letter-spacing: 0.5px;
      white-space: nowrap;
    }}

    .video-title {{
      font-size: 15px;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 600px;
    }}

    .video-meta {{
      font-size: 12px;
      color: var(--text-secondary);
      white-space: nowrap;
    }}

    .header-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}

    .btn {{
      background-color: var(--bg-card-hover);
      color: var(--text-primary);
      border: 1px solid var(--border-color);
      padding: 7px 14px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
      text-decoration: none;
    }}

    .btn:hover {{
      background-color: var(--border-color);
      border-color: var(--accent);
    }}

    .btn-primary {{
      background: linear-gradient(135deg, #0284c7, #38bdf8);
      border: none;
      color: white;
    }}

    .btn-primary:hover {{
      box-shadow: 0 0 12px var(--accent-glow);
    }}

    /* Split Container Layout */
    .app-container {{
      display: flex;
      flex: 1;
      height: calc(100vh - 65px);
      overflow: hidden;
    }}

    /* Left Panel: Video & Controls */
    .video-panel {{
      flex: 1.1;
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--border-color);
      background-color: #070a12;
      padding: 20px;
      gap: 16px;
      overflow-y: auto;
    }}

    .player-wrapper {{
      position: relative;
      width: 100%;
      aspect-ratio: 16 / 9;
      background: #000;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
      border: 1px solid var(--border-color);
    }}

    .player-wrapper iframe {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      border: none;
    }}

    .controls-strip {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 10px 16px;
      gap: 12px;
      flex-wrap: wrap;
    }}

    .speed-buttons {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .speed-btn {{
      background: transparent;
      border: 1px solid var(--border-color);
      color: var(--text-secondary);
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 12px;
      font-family: 'JetBrains Mono', monospace;
      cursor: pointer;
      transition: all 0.2s;
    }}

    .speed-btn:hover, .speed-btn.active {{
      background: var(--accent);
      color: #000;
      font-weight: 700;
      border-color: var(--accent);
    }}

    .toggle-group {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--text-secondary);
      user-select: none;
    }}

    .toggle-group input {{
      cursor: pointer;
      accent-color: var(--accent);
    }}

    /* Right Panel: Content & Search */
    .content-panel {{
      flex: 1.4;
      display: flex;
      flex-direction: column;
      background-color: var(--bg-main);
      overflow: hidden;
    }}

    .content-header {{
      background-color: var(--bg-card);
      border-bottom: 1px solid var(--border-color);
      padding: 12px 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .tabs-bar {{
      display: flex;
      gap: 8px;
      border-bottom: 1px solid var(--border-color);
      padding-bottom: 8px;
    }}

    .tab-item {{
      background: transparent;
      border: none;
      color: var(--text-secondary);
      font-size: 14px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 8px;
      cursor: pointer;
      transition: all 0.2s;
    }}

    .tab-item.active {{
      background-color: var(--bg-card-hover);
      color: var(--accent);
    }}

    .search-box {{
      position: relative;
      display: flex;
      align-items: center;
    }}

    .search-input {{
      width: 100%;
      background-color: var(--bg-main);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 9px 36px 9px 14px;
      color: var(--text-primary);
      font-size: 13px;
      outline: none;
      transition: border-color 0.2s;
    }}

    .search-input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 8px var(--accent-glow);
    }}

    .search-icon {{
      position: absolute;
      right: 12px;
      color: var(--text-secondary);
      pointer-events: none;
      font-size: 14px;
    }}

    .search-stats {{
      font-size: 12px;
      color: var(--text-secondary);
    }}

    /* Scrollable Transcript List */
    .transcript-scroll {{
      flex: 1;
      overflow-y: auto;
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 12px;
      scroll-behavior: smooth;
    }}

    .paragraph-card {{
      background-color: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 14px 16px;
      cursor: pointer;
      transition: all 0.25s ease;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}

    .paragraph-card:hover {{
      background-color: var(--bg-card-hover);
      border-color: #3b4c74;
    }}

    .paragraph-card.active {{
      background-color: var(--bg-active);
      border-color: var(--border-active);
      box-shadow: 0 0 15px rgba(56, 189, 248, 0.15);
    }}

    .paragraph-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .time-badge {{
      background-color: var(--badge-bg);
      color: var(--accent);
      border: 1px solid rgba(56, 189, 248, 0.3);
      padding: 3px 8px;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 12px;
      font-weight: 600;
    }}

    .paragraph-text {{
      font-size: 14.5px;
      line-height: 1.65;
      color: #cbd5e1;
    }}

    .paragraph-card.active .paragraph-text {{
      color: #ffffff;
      font-weight: 500;
    }}

    mark {{
      background-color: var(--mark-bg);
      color: var(--mark-text);
      padding: 1px 4px;
      border-radius: 3px;
      font-weight: 600;
    }}

    /* Cornell Tab View */
    .cornell-view {{
      display: none;
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      font-size: 14px;
      line-height: 1.7;
      color: #cbd5e1;
      white-space: pre-wrap;
      font-family: 'Inter', sans-serif;
    }}

    /* Scrollbars */
    ::-webkit-scrollbar {{
      width: 8px;
      height: 8px;
    }}
    ::-webkit-scrollbar-track {{
      background: var(--bg-main);
    }}
    ::-webkit-scrollbar-thumb {{
      background: #1e293b;
      border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
      background: #334155;
    }}
  </style>
</head>
<body>

  <header>
    <div class="header-info">
      <div class="logo-badge">STUDY PLAYER</div>
      <div>
        <div class="video-title">{escaped_title}</div>
        <div class="video-meta">{escaped_channel} • Duração: {metadata.formatted_duration}</div>
      </div>
    </div>
    <div class="header-actions">
      <button class="btn" onclick="copyFullTranscript()">📋 Copiar Transcrição</button>
      <a href="https://www.youtube.com/watch?v={metadata.video_id}" target="_blank" class="btn btn-primary">▶️ Abrir no YouTube</a>
    </div>
  </header>

  <div class="app-container">
    <!-- Painel do Vídeo -->
    <div class="video-panel">
      <div class="player-wrapper">
        <div id="yt-player"></div>
      </div>

      <div class="controls-strip">
        <div class="speed-buttons">
          <span style="font-size: 12px; color: var(--text-secondary); margin-right: 4px;">Velocidade:</span>
          <button class="speed-btn" onclick="setSpeed(1.0)">1.0x</button>
          <button class="speed-btn" onclick="setSpeed(1.25)">1.25x</button>
          <button class="speed-btn active" onclick="setSpeed(1.5)">1.5x</button>
          <button class="speed-btn" onclick="setSpeed(1.75)">1.75x</button>
          <button class="speed-btn" onclick="setSpeed(2.0)">2.0x</button>
        </div>

        <div class="toggle-group">
          <label><input type="checkbox" id="auto-scroll-toggle" checked> Auto-Scroll Acompanhado</label>
        </div>
      </div>

      <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 14px 16px;">
        <h4 style="font-size: 13px; color: var(--accent); margin-bottom: 6px;">💡 Dica de Estudo Ativo:</h4>
        <p style="font-size: 12.5px; color: var(--text-secondary); line-height: 1.5;">
          Clique em qualquer parágrafo à direita para navegar o vídeo instantaneamente. Use a busca para encontrar leis, artigos, prazos ou termos citados pelo professor.
        </p>
      </div>
    </div>

    <!-- Painel de Conteúdo e Transcrição -->
    <div class="content-panel">
      <div class="content-header">
        <div class="tabs-bar">
          <button class="tab-item active" id="tab-transcript" onclick="switchTab('transcript')">📑 Transcrição Interativa</button>
          <button class="tab-item" id="tab-cornell" onclick="switchTab('cornell')">🎓 Caderno Cornell</button>
        </div>
        <div class="search-box">
          <input type="search" id="search-input" class="search-input" placeholder="Buscar palavras na fala do professor..." oninput="handleSearch()">
          <span class="search-icon">🔍</span>
        </div>
        <div class="search-stats" id="search-stats">Exibindo todos os {len(paragraphs)} blocos da aula.</div>
      </div>

      <div class="transcript-scroll" id="transcript-container">
        <!-- Renderizado via Javascript -->
      </div>

      <div class="cornell-view" id="cornell-container">
        <!-- Conteúdo Cornell renderizado via JS -->
      </div>
    </div>
  </div>

  <!-- YouTube IFrame API -->
  <script src="https://www.youtube.com/iframe_api"></script>
  <script>
    const PARAGRAPHS = {paragraphs_json};
    const CORNELL_MD = {escaped_cornell_text};
    const VIDEO_ID = "{metadata.video_id}";

    let player = null;
    let activeParagraphId = -1;
    let autoScroll = true;

    // Inicializa YouTube IFrame API
    function onYouTubeIframeAPIReady() {{
      player = new YT.Player('yt-player', {{
        videoId: VIDEO_ID,
        playerVars: {{
          'playsinline': 1,
          'rel': 0,
          'modestbranding': 1
        }},
        events: {{
          'onReady': onPlayerReady
        }}
      }});
    }}

    function onPlayerReady(event) {{
      setSpeed(1.5);
      // Loop de sincronização em tempo real (250ms)
      setInterval(syncActiveParagraph, 250);
    }}

    function setSpeed(rate) {{
      if (player && player.setPlaybackRate) {{
        player.setPlaybackRate(rate);
      }}
      document.querySelectorAll('.speed-btn').forEach(b => {{
        b.classList.toggle('active', parseFloat(b.innerText) === rate);
      }});
    }}

    function jumpToTime(seconds) {{
      if (player && player.seekTo) {{
        player.seekTo(seconds, true);
        player.playVideo();
      }}
    }}

    // Sincroniza o parágrafo iluminado com o tempo atual do vídeo
    function syncActiveParagraph() {{
      if (!player || !player.getCurrentTime) return;
      const currentTime = player.getCurrentTime();

      let currentId = -1;
      for (let i = 0; i < PARAGRAPHS.length; i++) {{
        if (currentTime >= PARAGRAPHS[i].start && currentTime <= PARAGRAPHS[i].end) {{
          currentId = i;
          break;
        }}
      }}

      if (currentId !== -1 && currentId !== activeParagraphId) {{
        // Remove destaque anterior
        if (activeParagraphId !== -1) {{
          const prevEl = document.getElementById(`p-card-${{activeParagraphId}}`);
          if (prevEl) prevEl.classList.remove('active');
        }}

        activeParagraphId = currentId;
        const currentEl = document.getElementById(`p-card-${{activeParagraphId}}`);
        if (currentEl) {{
          currentEl.classList.add('active');
          if (autoScroll && document.getElementById('auto-scroll-toggle').checked) {{
            currentEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
          }}
        }}
      }}
    }}

    // Renderização dos cards da transcrição
    function renderTranscript(filterText = '') {{
      const container = document.getElementById('transcript-container');
      container.innerHTML = '';

      const query = filterText.trim().toLowerCase();
      let matchedCount = 0;

      PARAGRAPHS.forEach(p => {{
        const textLower = p.text.toLowerCase();
        if (query && !textLower.includes(query)) return;

        matchedCount++;
        const card = document.createElement('div');
        card.className = `paragraph-card ${{p.id === activeParagraphId ? 'active' : ''}}`;
        card.id = `p-card-${{p.id}}`;
        card.onclick = () => jumpToTime(p.start);

        let displayText = p.text;
        if (query) {{
          const regex = new RegExp(`(${{query}})`, 'gi');
          displayText = displayText.replace(regex, '<mark>$1</mark>');
        }}

        card.innerHTML = `
          <div class="paragraph-header">
            <span class="time-badge">⏱️ ${{p.timestamp}}</span>
          </div>
          <div class="paragraph-text">${{displayText}}</div>
        `;

        container.appendChild(card);
      }});

      const statsEl = document.getElementById('search-stats');
      if (query) {{
        statsEl.innerText = `Encontrados ${{matchedCount}} de ${{PARAGRAPHS.length}} blocos contendo "${{query}}"`;
      }} else {{
        statsEl.innerText = `Exibindo todos os ${{PARAGRAPHS.length}} blocos da aula.`;
      }}
    }}

    function handleSearch() {{
      const q = document.getElementById('search-input').value;
      renderTranscript(q);
    }}

    function switchTab(tab) {{
      const isTranscript = tab === 'transcript';
      document.getElementById('transcript-container').style.display = isTranscript ? 'flex' : 'none';
      document.getElementById('cornell-container').style.display = isTranscript ? 'none' : 'block';
      document.getElementById('tab-transcript').classList.toggle('active', isTranscript);
      document.getElementById('tab-cornell').classList.toggle('active', !isTranscript);
      document.querySelector('.search-box').style.display = isTranscript ? 'flex' : 'none';
    }}

    function copyFullTranscript() {{
      const fullText = PARAGRAPHS.map(p => `[${{p.timestamp}}] ${{p.text}}`).join('\\n\\n');
      navigator.clipboard.writeText(fullText).then(() => {{
        alert('Transcrição copiada com sucesso para a área de transferência!');
      }});
    }}

    // Inicialização
    document.addEventListener('DOMContentLoaded', () => {{
      renderTranscript();
      document.getElementById('cornell-container').innerText = CORNELL_MD;
      document.getElementById('auto-scroll-toggle').addEventListener('change', (e) => {{
        autoScroll = e.target.checked;
      }});
    }});
  </script>
</body>
</html>
"""
    return html_content
