/**
 * YouTube Study Intelligence - Side Panel Controller (Padrão Diamante)
 * Controle direto via Chrome Scripting API com Resiliência Dupla:
 * 1. Servidor Local de Alta Performance (127.0.0.1:8765) com IA, Método Cornell e Resumos.
 * 2. Fallback Nativo no Navegador: Extrai legendas oficiais do YouTube diretamente se o motor estiver offline.
 */

const LOCAL_SERVER_URL = "http://127.0.0.1:8765";
const SERVER_URLS = ["http://127.0.0.1:8765", "http://localhost:8765"];

// Estado da Aplicação
let currentVideoId = null;
let currentMetadata = null;
let paragraphsData = [];
let cornellData = "";
let summaryData = "";
let activeParagraphIndex = -1;
let autoScrollEnabled = true;
let isLoadingTranscript = false;

// Elementos do DOM
const syncLabel = document.getElementById("sync-label");
const statusDot = document.querySelector(".status-dot");
const titleEl = document.getElementById("display-video-title");
const channelEl = document.getElementById("display-video-channel");
const transcriptListEl = document.getElementById("transcript-list");
const cornellDisplayEl = document.getElementById("cornell-display");
const summaryDisplayEl = document.getElementById("summary-display");
const emptyStateEl = document.getElementById("empty-state");
const searchInput = document.getElementById("input-search");
const searchCounter = document.getElementById("search-counter");
const autoScrollToggle = document.getElementById("toggle-autoscroll");

// Inicialização
document.addEventListener("DOMContentLoaded", async () => {
  setupEventListeners();
  await checkActiveTabAndLoad();

  // Loop de sincronização em tempo real de alta precisão (350ms)
  setInterval(syncVideoTimeLoop, 350);

  // Monitora mudança de vídeo a cada 2 segundos caso não venha evento do background
  setInterval(checkActiveTabAndLoad, 2000);
});

// Configuração de Eventos da Interface
function setupEventListeners() {
  // Alternância de Abas
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetTab = btn.getAttribute("data-tab");
      document.getElementById(`pane-${targetTab}`).classList.add("active");

      const searchSection = document.getElementById("search-section");
      searchSection.style.display = targetTab === "transcript" ? "flex" : "none";
    });
  });

  // Campo de Busca
  searchInput.addEventListener("input", () => {
    renderTranscript(searchInput.value);
  });

  // Toggle Auto-Scroll
  autoScrollToggle.addEventListener("change", (e) => {
    autoScrollEnabled = e.target.checked;
  });

  // Controles de Velocidade
  document.querySelectorAll(".btn-speed").forEach(btn => {
    btn.addEventListener("click", async () => {
      const rate = parseFloat(btn.getAttribute("data-rate"));
      document.querySelectorAll(".btn-speed").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      await executeOnVideo((r) => {
        const v = document.querySelector("video.html5-main-video") || document.querySelector("video");
        if (v) v.playbackRate = r;
      }, [rate]);
    });
  });

  // Controles de Passo (-5s / +5s)
  document.getElementById("btn-rewind").addEventListener("click", async () => {
    await executeOnVideo((d) => {
      const v = document.querySelector("video.html5-main-video") || document.querySelector("video");
      if (v) v.currentTime = Math.max(0, v.currentTime + d);
    }, [-5]);
  });

  document.getElementById("btn-forward").addEventListener("click", async () => {
    await executeOnVideo((d) => {
      const v = document.querySelector("video.html5-main-video") || document.querySelector("video");
      if (v) v.currentTime = Math.max(0, v.currentTime + d);
    }, [5]);
  });

  // Botões de Ação do Topo
  document.getElementById("btn-refresh").addEventListener("click", () => {
    checkActiveTabAndLoad(true);
  });
  document.getElementById("btn-copy").addEventListener("click", copyTranscript);
  document.getElementById("btn-download").addEventListener("click", downloadMarkdown);
  document.getElementById("btn-download-pdf").addEventListener("click", downloadPdfAction);
  document.getElementById("btn-download-video").addEventListener("click", () => downloadMediaAction("video"));
  document.getElementById("btn-download-audio").addEventListener("click", () => downloadMediaAction("audio"));
  document.getElementById("btn-manual-load").addEventListener("click", () => {
    loadTranscript(currentVideoId, true);
  });

  // Escuta notificações do background worker (mudança de URL ou aba ativada)
  chrome.runtime.onMessage.addListener((message) => {
    if (message.type === "TAB_URL_CHANGED") {
      checkActiveTabAndLoad();
    }
  });
}

// Localiza a aba do YouTube de forma inteligente priorizando a janela atual
async function getYouTubeTab() {
  try {
    // 1. Tenta a aba ativa na janela atual (onde o Side Panel está acoplado)
    const activeCurrent = await chrome.tabs.query({ active: true, currentWindow: true });
    for (const t of activeCurrent) {
      if (t.url && t.url.includes("youtube.com/watch")) return t;
    }
    // 2. Tenta a aba ativa em qualquer janela
    const tabs = await chrome.tabs.query({ active: true });
    for (const t of tabs) {
      if (t.url && t.url.includes("youtube.com/watch")) return t;
    }
    // 3. Tenta qualquer aba do YouTube aberta
    const ytTabs = await chrome.tabs.query({ url: "*://*.youtube.com/watch*" });
    if (ytTabs.length > 0) return ytTabs[0];
  } catch (e) {
    console.error("Erro ao buscar aba do YouTube:", e);
  }
  return null;
}

// Execução direta e infalível no DOM da aba do YouTube via chrome.scripting
async function executeOnVideo(func, args = [], world = "ISOLATED") {
  const tab = await getYouTubeTab();
  if (!tab || !tab.id) return null;

  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      world: world,
      func: func,
      args: args
    });
    if (results && results[0]) {
      return results[0].result;
    }
  } catch (err) {
    // Ignora erro se a aba estiver recarregando
  }
  return null;
}

// Loop contínuo que lê a posição atual do vídeo e sincroniza a transcrição
async function syncVideoTimeLoop() {
  const tab = await getYouTubeTab();
  if (!tab || !tab.id) {
    if (!paragraphsData.length) {
      setConnectionStatus(false, "Aguardando YouTube...");
    }
    return;
  }

  const res = await executeOnVideo(() => {
    const v = document.querySelector("video.html5-main-video") || document.querySelector("video");
    if (!v) return null;
    return {
      currentTime: v.currentTime,
      duration: v.duration,
      paused: v.paused,
      playbackRate: v.playbackRate
    };
  });

  if (res && typeof res.currentTime === "number") {
    if (paragraphsData.length > 0) {
      setConnectionStatus(true, res.paused ? "Vídeo pausado" : "Sincronizado em tempo real");
      highlightCurrentParagraph(res.currentTime);
    } else {
      // Quando não há parágrafos carregados ainda, reflete o estado fidedigno
      if (emptyStateEl.style.display !== "none") {
        setConnectionStatus(false, "Motor Local Necessário");
      } else if (isLoadingTranscript) {
        setConnectionStatus(true, "Carregando transcrição...");
      } else {
        setConnectionStatus(false, "Vídeo ativo (sem transcrição)");
      }
    }
  } else {
    setConnectionStatus(false, "Player não detectado");
  }
}

// Pula para o segundo exato no player oficial do YouTube
async function jumpToVideoTime(seconds) {
  await executeOnVideo((sec) => {
    const v = document.querySelector("video.html5-main-video") || document.querySelector("video");
    if (v) {
      v.currentTime = sec;
      v.play();
    }
  }, [seconds]);
}

// Ilumina o parágrafo correspondente e faz auto-scroll
function highlightCurrentParagraph(currentTime) {
  if (!paragraphsData.length) return;

  let foundIndex = -1;
  for (let i = 0; i < paragraphsData.length; i++) {
    const p = paragraphsData[i];
    if (currentTime >= p.start_time && currentTime <= p.end_time) {
      foundIndex = i;
      break;
    }
  }

  if (foundIndex !== -1 && foundIndex !== activeParagraphIndex) {
    if (activeParagraphIndex !== -1) {
      const prevEl = document.getElementById(`card-p-${activeParagraphIndex}`);
      if (prevEl) prevEl.classList.remove("active");
    }

    activeParagraphIndex = foundIndex;
    const currentEl = document.getElementById(`card-p-${activeParagraphIndex}`);
    if (currentEl) {
      currentEl.classList.add("active");
      if (autoScrollEnabled) {
        currentEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }
  }
}

// Verifica se o usuário trocou de vídeo no YouTube ou se precisa carregar a aula
async function checkActiveTabAndLoad(forceRefresh = false) {
  const tab = await getYouTubeTab();
  if (!tab || !tab.url || !tab.url.includes("youtube.com/watch")) {
    if (!paragraphsData.length && !isLoadingTranscript) {
      showEmptyState("Abra um vídeo no YouTube", "Navegue até qualquer vídeo ou aula no YouTube para sincronizar.");
    }
    return;
  }

  try {
    const urlParams = new URLSearchParams(new URL(tab.url).search);
    const videoId = urlParams.get("v");

    if (!videoId) return;

    // Recarrega se trocou de vídeo, se forçado, ou se o vídeo atual ainda não tem transcrição carregada
    if (videoId !== currentVideoId || forceRefresh || (paragraphsData.length === 0 && !isLoadingTranscript)) {
      currentVideoId = videoId;
      await loadTranscript(videoId, forceRefresh);
    }
  } catch (err) {
    console.error("Erro ao verificar URL da aba:", err);
  }
}

// Faz requisição HTTP resiliente ao servidor local testando 127.0.0.1 e localhost
async function fetchFromLocalServer(endpoint) {
  for (const baseUrl of SERVER_URLS) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 2000);
      const resp = await fetch(`${baseUrl}${endpoint}`, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (resp.ok) {
        const data = await resp.json();
        return { ok: true, data: data, baseUrl: baseUrl };
      }
    } catch (e) {
      // Tenta próximo endereço caso IPv6 localhost falhe
    }
  }
  return { ok: false };
}

// Estratégia Híbrida: Servidor Local (IA) -> Fallback Nativo do YouTube (Navegador)
async function loadTranscript(videoId, force = false) {
  if (isLoadingTranscript) return;
  isLoadingTranscript = true;

  try {
    setConnectionStatus(false, "Sincronizando aula...");

    // 1. Tenta cache local da extensão
    if (!force) {
      const cached = await chrome.storage.local.get(videoId);
      if (cached && cached[videoId]) {
        applyTranscriptData(cached[videoId]);
        return;
      }
    }

    // 2. Tenta requisição ao Servidor Local de Estudos (127.0.0.1:8765)
    setConnectionStatus(true, "Conectando ao motor local...");
    const serverResult = await fetchFromLocalServer(`/api/transcript?v=${videoId}`);
    if (serverResult.ok && serverResult.data) {
      const toCache = {};
      toCache[videoId] = serverResult.data;
      await chrome.storage.local.set(toCache);
      applyTranscriptData(serverResult.data);
      return;
    }

    // 3. Fallback Nativo Infalível: Extrai legendas diretamente do player do YouTube no navegador
    setConnectionStatus(true, "Extraindo legendas oficiais do YouTube...");
    const tab = await getYouTubeTab();
    if (tab && tab.id) {
      const nativeData = await extractTranscriptDirectlyFromYouTube(tab.id, videoId);
      if (nativeData && nativeData.paragraphs && nativeData.paragraphs.length > 0) {
        const toCache = {};
        toCache[videoId] = nativeData;
        await chrome.storage.local.set(toCache);
        applyTranscriptData(nativeData);
        setConnectionStatus(true, "Sincronizado nativamente (Motor offline)");
        return;
      }
    }

    // 4. Se nem o servidor nem as legendas nativas puderem ser acessadas
    const info = await executeOnVideo(() => {
      const titleEl = document.querySelector("h1.style-scope.ytd-watch-metadata yt-formatted-string") ||
                      document.querySelector("h1.title") ||
                      document.querySelector("meta[name='title']");
      const channelEl = document.querySelector("#channel-name #text") || 
                        document.querySelector("ytd-channel-name yt-formatted-string");
      return {
        title: titleEl ? (titleEl.innerText || titleEl.getAttribute("content") || document.title) : document.title,
        channel: channelEl ? channelEl.innerText.trim() : "Canal do YouTube"
      };
    });

    if (info && info.title) {
      titleEl.innerText = info.title.replace(" - YouTube", "").trim();
      channelEl.innerText = info.channel || "YouTube";
    }

    showEmptyState(
      "Motor Local Necessário",
      "Este vídeo não possui legendas de texto direto. Inicie o motor local com duplo clique em <code>INICIAR_SERVIDOR_ESTUDOS.bat</code> para transcrever com a inteligência acústica Whisper/Gemini."
    );
  } finally {
    isLoadingTranscript = false;
  }
}

// Extrai legendas diretamente do DOM e API de timedtext do YouTube sem depender do Python
async function extractTranscriptDirectlyFromYouTube(tabId, videoId) {
  try {
    const pageData = await chrome.scripting.executeScript({
      target: { tabId: tabId },
      world: "MAIN",
      func: () => {
        let playerResp = null;
        try {
          if (window.ytInitialPlayerResponse) {
            playerResp = window.ytInitialPlayerResponse;
          } else {
            const player = document.querySelector("#movie_player");
            if (player && typeof player.getPlayerResponse === "function") {
              playerResp = player.getPlayerResponse();
            }
          }
        } catch (e) {}

        const titleEl = document.querySelector("h1.style-scope.ytd-watch-metadata yt-formatted-string") ||
                        document.querySelector("h1.title") ||
                        document.querySelector("meta[name='title']");
        const channelEl = document.querySelector("#channel-name #text") || 
                          document.querySelector("ytd-channel-name yt-formatted-string");

        let tracks = playerResp?.captions?.playerCaptionsTracklistRenderer?.captionTracks || [];

        // Fallback de extração via regex no HTML se playerResponse não for direto
        if (!tracks || tracks.length === 0) {
          const match = document.documentElement.innerHTML.match(/"captionTracks":\s*(\[[^\]]+\])/);
          if (match) {
            try {
              tracks = JSON.parse(match[1]);
            } catch (err) {}
          }
        }

        return {
          title: titleEl ? (titleEl.innerText || titleEl.getAttribute("content") || document.title) : document.title,
          channel: channelEl ? channelEl.innerText.trim() : "Canal do YouTube",
          tracks: tracks
        };
      }
    });

    const info = pageData && pageData[0] && pageData[0].result;
    if (!info || !info.tracks || info.tracks.length === 0) {
      return null;
    }

    // Seleciona idioma prioritário (português)
    let selectedTrack = info.tracks.find(t => t.languageCode === "pt" || t.languageCode === "pt-BR");
    if (!selectedTrack) selectedTrack = info.tracks.find(t => t.languageCode && t.languageCode.startsWith("pt"));
    if (!selectedTrack) selectedTrack = info.tracks[0];

    if (!selectedTrack || !selectedTrack.baseUrl) return null;

    // Busca o arquivo XML de legendas diretamente da CDN do YouTube
    const xmlResp = await fetch(selectedTrack.baseUrl);
    if (!xmlResp.ok) return null;
    const xmlText = await xmlResp.text();

    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlText, "text/xml");
    const textNodes = Array.from(xmlDoc.getElementsByTagName("text"));
    if (!textNodes.length) return null;

    const rawSnippets = textNodes.map(node => {
      const start = parseFloat(node.getAttribute("start") || "0");
      const dur = parseFloat(node.getAttribute("dur") || "0");
      let rawContent = node.textContent || "";
      const doc = new DOMParser().parseFromString(rawContent, "text/html");
      const decodedText = doc.body.textContent || rawContent;
      return {
        start: start,
        end: start + dur,
        text: decodedText.trim()
      };
    }).filter(s => s.text.length > 0);

    if (!rawSnippets.length) return null;

    const paragraphs = buildBrowserSemanticParagraphs(rawSnippets);
    const cleanTitle = (info.title || "Aula do YouTube").replace(" - YouTube", "").trim();
    const cleanChannel = info.channel || "YouTube";

    return {
      metadata: {
        video_id: videoId,
        canonical_url: `https://www.youtube.com/watch?v=${videoId}`,
        title: cleanTitle,
        channel_name: cleanChannel,
        duration_formatted: formatSeconds(rawSnippets[rawSnippets.length - 1].end),
        detected_language: selectedTrack.languageCode || "pt"
      },
      paragraphs: paragraphs,
      summary: {
        full_markdown: `### 🎯 Resumo da Aula: ${cleanTitle}\n\n**Canal:** ${cleanChannel}\n\n*Esta transcrição foi sincronizada nativamente através do navegador!*\n\n> 💡 **Para gerar Resumo com IA e Métricas:** Inicie o motor local com duplo clique em \`INICIAR_SERVIDOR_ESTUDOS.bat\`.`,
        engine_used: "youtube-native"
      },
      cornell_markdown: `# CADERNO DE ESTUDOS: ${cleanTitle}\n\n**Canal:** ${cleanChannel} • **Vídeo ID:** ${videoId}\n\n---\n\n## 📝 Notas de Aula Sincronizadas\n*Legendas oficiais do YouTube integradas nativamente.*\n\nVocê pode clicar em qualquer parágrafo da aba **Transcrição** para navegar no vídeo instantaneamente.\n\n> 💡 **Dica Padrão Diamante:** Inicie o arquivo \`INICIAR_SERVIDOR_ESTUDOS.bat\` para enriquecer este caderno com análise do Método Cornell gerada por Inteligência Artificial e download de PDF diagramado.`,
      cached: false,
      nativeBrowser: true
    };
  } catch (err) {
    console.warn("Falha na extração de legendas nativas do YouTube:", err);
    return null;
  }
}

// Agrupa fragmentos individuais de fala em parágrafos semânticos estruturados
function buildBrowserSemanticParagraphs(snippets) {
  const paragraphs = [];
  let currentWords = [];
  let pStart = 0;
  let pEnd = 0;

  for (let i = 0; i < snippets.length; i++) {
    const s = snippets[i];
    if (currentWords.length === 0) {
      pStart = s.start;
    }
    currentWords.push(s.text);
    pEnd = s.end;

    const fullCurrentText = currentWords.join(" ");
    const wordCount = fullCurrentText.split(/\s+/).length;
    const endsWithTerminal = /[.!?]$/.test(s.text.trim());
    const nextPause = (i < snippets.length - 1) ? (snippets[i + 1].start - s.end) : 0;

    if ((wordCount >= 45 && endsWithTerminal) || nextPause > 2.0 || wordCount >= 70 || i === snippets.length - 1) {
      paragraphs.push({
        start_time: pStart,
        end_time: pEnd,
        timestamp_formatted: formatSeconds(pStart),
        text: cleanNoiseText(fullCurrentText, false)
      });
      currentWords = [];
    }
  }

  return paragraphs;
}

// Higieniza ruídos acústicos com opção de preservar quebras de linha em documentos Markdown
function cleanNoiseText(text, preserveLineBreaks = false) {
  if (!text) return "";
  let cleaned = text
    .replace(/\[\s*(?:música|musica|music|som|aplausos|risos|vinheta|ruído|ruido|tosse|roncando|áudio|audio|suspiro|grito)[^\]]*\]/gi, "")
    .replace(/\(\s*(?:música|musica|music|aplausos|risos|vinheta)[^\)]*\)/gi, "")
    .replace(/^(?:>>|>>>|--)\s*/gm, "")
    .replace(/[^\S\r\n]+([,.:;!?])/g, "$1");

  if (preserveLineBreaks) {
    return cleaned
      .replace(/[^\S\r\n]+/g, " ")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  return cleaned
    .replace(/\s+/g, " ")
    .trim();
}

function applyTranscriptData(data) {
  emptyStateEl.style.display = "none";
  currentMetadata = data.metadata;
  
  const rawParas = data.paragraphs || [];
  paragraphsData = rawParas
    .map(p => {
      return {
        ...p,
        text: cleanNoiseText(p.text, false)
      };
    })
    .filter(p => p.text.length > 2);

  cornellData = cleanNoiseText(data.cornell_markdown || "", true);
  summaryData = cleanNoiseText(data.summary ? (data.summary.full_markdown || data.summary.executive_summary) : "", true);

  titleEl.innerText = currentMetadata.title;
  channelEl.innerText = `${currentMetadata.channel_name} • Duração: ${currentMetadata.duration_formatted}`;

  renderTranscript();
  cornellDisplayEl.innerText = cornellData;
  summaryDisplayEl.innerText = summaryData;

  const statusText = data.nativeBrowser ? "Sincronizado nativamente com o YouTube" : "Sincronizado com o Motor de Estudos";
  setConnectionStatus(true, statusText);
}

function showEmptyState(title, desc) {
  emptyStateEl.style.display = "flex";
  document.getElementById("empty-title").innerText = title;
  document.getElementById("empty-desc").innerHTML = desc;
  setConnectionStatus(false, "Desconectado");
}

function setConnectionStatus(connected, text) {
  statusDot.classList.toggle("active", connected);
  syncLabel.innerText = text;
}

// Renderiza a lista de cartões da transcrição
function renderTranscript(filterQuery = "") {
  transcriptListEl.innerHTML = "";
  const query = filterQuery.trim().toLowerCase();
  let matches = 0;

  paragraphsData.forEach((p, idx) => {
    const textLower = p.text.toLowerCase();
    if (query && !textLower.includes(query)) return;

    matches++;
    const card = document.createElement("div");
    card.className = `study-card ${idx === activeParagraphIndex ? "active" : ""}`;
    card.id = `card-p-${idx}`;

    let highlightedText = p.text;
    if (query) {
      const regex = new RegExp(`(${query})`, "gi");
      highlightedText = highlightedText.replace(regex, "<mark>$1</mark>");
    }

    card.innerHTML = `
      <div class="card-header">
        <span class="card-timestamp">⏱️ ${p.timestamp_formatted || formatSeconds(p.start_time)}</span>
      </div>
      <div class="card-text">${highlightedText}</div>
    `;

    card.addEventListener("click", () => {
      jumpToVideoTime(p.start_time);
    });

    transcriptListEl.appendChild(card);
  });

  if (query) {
    searchCounter.innerText = `${matches} de ${paragraphsData.length} parágrafos contendo "${query}"`;
  } else {
    searchCounter.innerText = `${paragraphsData.length} blocos de estudo carregados`;
  }
}

function formatSeconds(secs) {
  const total = Math.floor(secs);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

// Ações de Cópia e Download
function copyTranscript() {
  if (!paragraphsData.length) return;
  const full = paragraphsData.map(p => `[${p.timestamp_formatted}] ${p.text}`).join("\n\n");
  navigator.clipboard.writeText(full).then(() => {
    alert("Transcrição copiada para a área de transferência!");
  });
}

function downloadMarkdown() {
  if (!cornellData && !paragraphsData.length) return;
  const text = cornellData || paragraphsData.map(p => `[${p.timestamp_formatted}] ${p.text}`).join("\n\n");
  const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Estudo_${currentVideoId}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

// Dispara download de Vídeo ou Áudio através do motor local
async function downloadMediaAction(type) {
  if (!currentVideoId) {
    alert("Abra uma vídeo-aula no YouTube primeiro!");
    return;
  }

  const label = type === "video" ? "vídeo MP4" : "áudio (podcast)";
  setConnectionStatus(true, `Iniciando download do ${label}...`);

  const serverResult = await fetchFromLocalServer(`/api/download?v=${currentVideoId}&type=${type}`);
  if (serverResult.ok && serverResult.data && serverResult.data.success) {
    setConnectionStatus(true, `Download concluído: ${serverResult.data.filename}`);
    alert(`Sucesso! O ${label} foi salvo na pasta da aula:\n${serverResult.data.file_path}`);
    return;
  }

  setConnectionStatus(false, "Falha na conexão");
  alert(`Para baixar o ${label}, certifique-se de que o motor local está ativo:\nExecute com duplo clique em INICIAR_SERVIDOR_ESTUDOS.bat.`);
}

// Abre ou baixa o Caderno de Estudos em PDF estruturado
function downloadPdfAction() {
  if (!currentVideoId) {
    alert("Abra uma vídeo-aula no YouTube primeiro!");
    return;
  }
  const pdfUrl = `${LOCAL_SERVER_URL}/api/pdf?v=${currentVideoId}`;
  if (chrome && chrome.tabs && chrome.tabs.create) {
    chrome.tabs.create({ url: pdfUrl });
  } else {
    window.open(pdfUrl, "_blank");
  }
}
