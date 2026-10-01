/**
 * Service Worker (Manifest V3) - YouTube Study Intelligence
 * Gerencia a ativação do Chrome Side Panel e eventos de abas.
 */

// Permite abrir o Side Panel ao clicar no ícone da extensão na barra de ferramentas
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error("Falha ao configurar comportamento do side panel:", error));

// Monitora mudanças de página e navegação SPA (pushState) no YouTube
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  const targetUrl = changeInfo.url || (changeInfo.status === "complete" ? tab.url : null);
  if (targetUrl && targetUrl.includes("youtube.com/watch")) {
    chrome.runtime.sendMessage({
      type: "TAB_URL_CHANGED",
      tabId: tabId,
      url: targetUrl
    }).catch(() => {
      // Painel pode não estar aberto no momento; ignora erro de recepção
    });
  }
});

// Monitora alternância de abas para sincronizar imediatamente se o usuário mudar para o YouTube
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab && tab.url && tab.url.includes("youtube.com/watch")) {
      chrome.runtime.sendMessage({
        type: "TAB_URL_CHANGED",
        tabId: activeInfo.tabId,
        url: tab.url
      }).catch(() => {});
    }
  } catch (e) {
    // Aba pode ter sido fechada
  }
});
