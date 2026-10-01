/**
 * Content Script - YouTube Study Intelligence
 * Executado dentro da página oficial do YouTube (youtube.com/watch)
 * Controla o elemento <video> com precisão milimétrica e comunica com o Side Panel.
 */

(() => {
  let videoElement = null;
  let syncInterval = null;

  function findVideo() {
    return document.querySelector("video.html5-main-video") || document.querySelector("video");
  }

  function initSync() {
    videoElement = findVideo();
    if (!videoElement) {
      setTimeout(initSync, 1000);
      return;
    }

    // Monitora atualizações de tempo do player oficial do YouTube
    videoElement.addEventListener("timeupdate", () => {
      chrome.runtime.sendMessage({
        type: "VIDEO_TIME_UPDATE",
        currentTime: videoElement.currentTime,
        duration: videoElement.duration || 0,
        paused: videoElement.paused
      }).catch(() => {});
    });
  }

  // Escuta comandos vindos do Side Panel
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    videoElement = findVideo();

    if (request.type === "SEEK_TO") {
      if (videoElement) {
        videoElement.currentTime = request.seconds;
        if (request.play !== false && videoElement.paused) {
          videoElement.play();
        }
        sendResponse({ success: true, currentTime: videoElement.currentTime });
      } else {
        sendResponse({ success: false, error: "Vídeo não encontrado no DOM" });
      }
      return true;
    }

    if (request.type === "SET_SPEED") {
      if (videoElement) {
        videoElement.playbackRate = request.rate;
        sendResponse({ success: true, rate: videoElement.playbackRate });
      }
      return true;
    }

    if (request.type === "GET_VIDEO_INFO") {
      const urlParams = new URLSearchParams(window.location.search);
      const videoId = urlParams.get("v");
      const titleEl = document.querySelector("h1.style-scope.ytd-watch-metadata yt-formatted-string") ||
                      document.querySelector("h1.title") ||
                      document.querySelector("meta[name='title']");
      const title = titleEl ? (titleEl.innerText || titleEl.getAttribute("content") || document.title) : document.title;
      
      const channelEl = document.querySelector("#channel-name #text") || 
                        document.querySelector("ytd-channel-name yt-formatted-string");
      const channel = channelEl ? channelEl.innerText.trim() : "Canal do YouTube";

      sendResponse({
        videoId: videoId,
        title: title.replace(" - YouTube", "").trim(),
        channel: channel,
        currentTime: videoElement ? videoElement.currentTime : 0,
        duration: videoElement ? videoElement.duration : 0,
        url: window.location.href
      });
      return true;
    }

    if (request.type === "STEP_TIME") {
      if (videoElement) {
        videoElement.currentTime = Math.max(0, videoElement.currentTime + (request.delta || 0));
        sendResponse({ success: true, currentTime: videoElement.currentTime });
      }
      return true;
    }
  });

  // Inicializa quando o DOM estiver pronto
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSync);
  } else {
    initSync();
  }
})();
