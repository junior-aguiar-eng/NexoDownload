/**
 * Nexo Download Pro - Mídia Digital Livre
 * JavaScript Oficial: Sincronização desktop via Heartbeat, WebSocket em tempo real,
 * licenciamento criptográfico HWID, seletor de pastas nativo, temas de cores dinâmicos
 * e gerenciamento de perfil e configurações.
 */

document.addEventListener("DOMContentLoaded", () => {
    // =========================================================================
    // 1. Elementos Principais da Interface
    // =========================================================================
    const urlInput = document.getElementById("urlInput");
    const btnClearInput = document.getElementById("btnClearInput");
    const downloadForm = document.getElementById("downloadForm");
    const btnAnalyze = document.getElementById("btnAnalyze");
    
    // Preview Card
    const mediaPreviewCard = document.getElementById("mediaPreviewCard");
    const previewThumb = document.getElementById("previewThumb");
    const previewBadge = document.getElementById("previewBadge");
    const previewTitle = document.getElementById("previewTitle");
    const previewAuthor = document.getElementById("previewAuthor");
    const btnDirectDownload = document.getElementById("btnDirectDownload");

    // Plataformas
    const platformCards = document.querySelectorAll(".platform-card");

    // Opções de Download
    const selFormat = document.getElementById("selFormat");
    const selQuality = document.getElementById("selQuality");
    const selAudioQuality = document.getElementById("selAudioQuality");
    const selVideoAudio = document.getElementById("selVideoAudio");
    const inputFolderPath = document.getElementById("inputFolderPath");
    const btnBrowseFolder = document.getElementById("btnBrowseFolder");
    const chkMetadata = document.getElementById("chkMetadata");
    const optQualityWrap = document.getElementById("optQualityWrap");
    const optVideoAudioWrap = document.getElementById("optVideoAudioWrap");

    // Listas de Download
    const activeDownloadsContainer = document.getElementById("activeDownloadsContainer");
    const completedDownloadsContainer = document.getElementById("completedDownloadsContainer");
    const emptyActiveDownloads = document.getElementById("emptyActiveDownloads");
    const emptyCompletedDownloads = document.getElementById("emptyCompletedDownloads");
    const activeCount = document.getElementById("activeCount");
    const completedCount = document.getElementById("completedCount");
    const btnClearCompleted = document.getElementById("btnClearCompleted");

    // Top Header & Perfil
    const userPill = document.getElementById("userPill");
    const headerUserName = document.querySelector(".user-name");
    const headerUserAvatar = document.querySelector(".user-avatar");

    // Modal de Configurações
    const settingsModal = document.getElementById("settingsModal");
    const btnCloseSettings = document.getElementById("btnCloseSettings");
    const btnCancelSettings = document.getElementById("btnCancelSettings");
    const btnSaveSettings = document.getElementById("btnSaveSettings");
    const settingUserName = document.getElementById("settingUserName");
    const profileAvatarPreview = document.getElementById("profileAvatarPreview");
    const settingFolderPath = document.getElementById("settingFolderPath");
    const btnChangeFolderNative = document.getElementById("btnChangeFolderNative");
    const btnOpenDefaultFolder = document.getElementById("btnOpenDefaultFolder");
    const settingDefaultVideoQuality = document.getElementById("settingDefaultVideoQuality");
    const settingDefaultAudioQuality = document.getElementById("settingDefaultAudioQuality");
    const settingLicenseStatusBadge = document.getElementById("settingLicenseStatusBadge");
    const settingLicensePlanText = document.getElementById("settingLicensePlanText");
    const settingHwidCode = document.getElementById("settingHwidCode");
    const btnResetData = document.getElementById("btnResetData");
    const themeButtons = document.querySelectorAll(".theme-btn");

    // Modal de Bloqueio por Licença
    const licenseModal = document.getElementById("licenseModal");
    const lockHwidDisplay = document.getElementById("lockHwidDisplay");
    const btnCopyHwid = document.getElementById("btnCopyHwid");
    const inputLicenseKey = document.getElementById("inputLicenseKey");
    const btnActivateLicense = document.getElementById("btnActivateLicense");
    const licenseErrorMsg = document.getElementById("licenseErrorMsg");

    // Modal de Atualização Oficial
    const btnUpdateNotice = document.getElementById("btnUpdateNotice");
    const updatePillText = document.getElementById("updatePillText");
    const updateModal = document.getElementById("updateModal");
    const btnCloseUpdate = document.getElementById("btnCloseUpdate");
    const btnRemindLater = document.getElementById("btnRemindLater");
    const btnStartAutoUpdate = document.getElementById("btnStartAutoUpdate");
    const btnStartUpdateText = document.getElementById("btnStartUpdateText");
    const updateCurrentVer = document.getElementById("updateCurrentVer");
    const updateNewVer = document.getElementById("updateNewVer");
    const updateChangelogContent = document.getElementById("updateChangelogContent");
    let pendingUpdateData = null;

    // Toast
    const toast = document.getElementById("toast");
    const toastMessage = document.getElementById("toastMessage");

    let currentMetadata = null;
    let activeTasksCount = 0;
    let completedTasksCount = 0;
    let analyzeDebounce = null;

    // =========================================================================
    // 2. Watchdog de Ciclo de Vida Desktop (Heartbeat & Shutdown)
    // =========================================================================
    function sendHeartbeat() {
        fetch("/api/heartbeat", { method: "POST" }).catch(() => {});
    }
    sendHeartbeat();
    setInterval(sendHeartbeat, 2000);

    window.addEventListener("beforeunload", () => {
        if (navigator.sendBeacon) {
            navigator.sendBeacon("/api/shutdown");
        }
    });

    // =========================================================================
    // 3. Sistema de Licenciamento Criptográfico (HWID-Lock)
    // =========================================================================
    async function checkLicenseStatus() {
        try {
            const resp = await fetch("/api/license/status");
            const data = await resp.json();
            
            if (data.machine_id) {
                if (lockHwidDisplay) lockHwidDisplay.textContent = data.machine_id;
                if (settingHwidCode) settingHwidCode.textContent = data.machine_id;
            }

            if (data.activated) {
                if (licenseModal) licenseModal.classList.add("hidden");
                if (settingLicenseStatusBadge) {
                    settingLicenseStatusBadge.textContent = "Ativado";
                    settingLicenseStatusBadge.style.background = "#dcfce7";
                    settingLicenseStatusBadge.style.color = "#15803d";
                }
                if (settingLicensePlanText) {
                    settingLicensePlanText.textContent = `${data.plan} (${data.expires})`;
                }
            } else {
                if (licenseModal) licenseModal.classList.remove("hidden");
                if (settingLicenseStatusBadge) {
                    settingLicenseStatusBadge.textContent = "Não Ativado";
                    settingLicenseStatusBadge.style.background = "#fee2e2";
                    settingLicenseStatusBadge.style.color = "#b91c1c";
                }
                if (settingLicensePlanText) {
                    settingLicensePlanText.textContent = "Aguardando ativação";
                }
            }
        } catch (e) {
            console.warn("Falha ao verificar licença:", e);
        }
    }

    checkLicenseStatus();

    if (btnCopyHwid) {
        btnCopyHwid.addEventListener("click", () => {
            const hwid = lockHwidDisplay.textContent;
            navigator.clipboard.writeText(hwid).then(() => {
                showToast("ID da Máquina copiado!");
            }).catch(() => {
                showToast("ID: " + hwid);
            });
        });
    }

    if (btnActivateLicense) {
        btnActivateLicense.addEventListener("click", async () => {
            const key = inputLicenseKey.value.trim();
            if (!key) {
                licenseErrorMsg.textContent = "Por favor, digite a chave de ativação.";
                licenseErrorMsg.classList.remove("hidden");
                return;
            }

            btnActivateLicense.disabled = true;
            btnActivateLicense.textContent = "Validando chave...";

            try {
                const resp = await fetch("/api/license/activate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ key: key })
                });
                const data = await resp.json();

                if (data.success) {
                    licenseErrorMsg.classList.add("hidden");
                    licenseModal.classList.add("hidden");
                    showToast("Nexo Download ativado com sucesso!");
                    checkLicenseStatus();
                } else {
                    licenseErrorMsg.textContent = data.message || "Chave inválida para este computador.";
                    licenseErrorMsg.classList.remove("hidden");
                }
            } catch (e) {
                licenseErrorMsg.textContent = "Erro ao conectar com o serviço de segurança.";
                licenseErrorMsg.classList.remove("hidden");
            } finally {
                btnActivateLicense.disabled = false;
                btnActivateLicense.innerHTML = `<span>Ativar e Entrar no Nexo</span><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"></polyline></svg>`;
            }
        });
    }

    // =========================================================================
    // 3.1. Sistema de Auto-Atualização Silenciosa em 1-Clique
    // =========================================================================
    async function checkForAppUpdates() {
        try {
            const resp = await fetch("/api/check-update");
            const data = await resp.json();
            if (data.has_update) {
                pendingUpdateData = data;
                if (btnUpdateNotice) {
                    btnUpdateNotice.classList.remove("hidden");
                    if (updatePillText) updatePillText.textContent = `v${data.latest_version} Disponível`;
                }
                if (updateCurrentVer) updateCurrentVer.textContent = data.current_version;
                if (updateNewVer) updateNewVer.textContent = data.latest_version;
                if (updateChangelogContent) updateChangelogContent.textContent = data.changelog;
            }
        } catch (e) {
            // Silencioso se offline
        }
    }

    setTimeout(checkForAppUpdates, 1500);

    if (btnUpdateNotice) {
        btnUpdateNotice.addEventListener("click", () => {
            if (updateModal) updateModal.classList.remove("hidden");
        });
    }

    if (btnCloseUpdate) {
        btnCloseUpdate.addEventListener("click", () => {
            if (updateModal) updateModal.classList.add("hidden");
        });
    }

    if (btnRemindLater) {
        btnRemindLater.addEventListener("click", () => {
            if (updateModal) updateModal.classList.add("hidden");
        });
    }

    if (btnStartAutoUpdate) {
        btnStartAutoUpdate.addEventListener("click", async () => {
            if (!pendingUpdateData || !pendingUpdateData.download_url) {
                showToast("URL do instalador não encontrada.");
                return;
            }

            btnStartAutoUpdate.disabled = true;
            btnStartUpdateText.textContent = "Baixando e instalando em segundo plano...";
            showToast("Atualização iniciada! O Nexo Download será reiniciado em instantes.");

            try {
                await fetch("/api/apply-update", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ download_url: pendingUpdateData.download_url })
                });
            } catch (e) {
                showToast("Erro ao disparar download da atualização.");
                btnStartAutoUpdate.disabled = false;
                btnStartUpdateText.textContent = "Tentar Novamente";
            }
        });
    }

    // =========================================================================
    // 4. Perfil, Temas de Cores e Preferências do Usuário
    // =========================================================================
    function applyTheme(themeName) {
        document.body.setAttribute("data-theme", themeName);
        themeButtons.forEach(btn => {
            btn.classList.toggle("active", btn.dataset.theme === themeName);
        });
        localStorage.setItem("nexo_theme", themeName);
    }

    function loadUserPreferences() {
        const savedTheme = localStorage.getItem("nexo_theme") || "emerald";
        applyTheme(savedTheme);

        const savedName = localStorage.getItem("nexo_username") || "Usuário";
        if (headerUserName) headerUserName.textContent = savedName;
        if (settingUserName) settingUserName.value = savedName;
        updateAvatarLetter(savedName);

        const savedVid = localStorage.getItem("nexo_video_quality");
        if (savedVid && selQuality) {
            selQuality.value = savedVid;
            if (settingDefaultVideoQuality) settingDefaultVideoQuality.value = savedVid;
        }

        const savedAud = localStorage.getItem("nexo_audio_quality");
        if (savedAud && selAudioQuality) {
            selAudioQuality.value = savedAud;
            if (settingDefaultAudioQuality) settingDefaultAudioQuality.value = savedAud;
        }
    }

    function updateAvatarLetter(name) {
        const letter = (name && name.trim().length > 0) ? name.trim().charAt(0).toUpperCase() : "U";
        if (headerUserAvatar) headerUserAvatar.textContent = letter;
        if (profileAvatarPreview) profileAvatarPreview.textContent = letter;
    }

    if (settingUserName) {
        settingUserName.addEventListener("input", (e) => {
            updateAvatarLetter(e.target.value);
        });
    }

    themeButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            applyTheme(btn.dataset.theme);
        });
    });

    loadUserPreferences();

    // =========================================================================
    // 5. Inicialização da Pasta Padrão e Seletor Nativo do Windows
    // =========================================================================
    fetch("/api/downloads-dir")
        .then(r => r.json())
        .then(data => {
            if (data.path) {
                inputFolderPath.value = data.path;
                if (settingFolderPath) settingFolderPath.value = data.path;
            }
        })
        .catch(() => {});

    loadCompletedHistory();

    // Seletor nativo do Windows Explorer
    if (btnChangeFolderNative) {
        btnChangeFolderNative.addEventListener("click", async () => {
            btnChangeFolderNative.disabled = true;
            try {
                const resp = await fetch("/api/select-folder", { method: "POST" });
                const data = await resp.json();
                if (data.success && data.path) {
                    settingFolderPath.value = data.path;
                    inputFolderPath.value = data.path;
                    showToast("Pasta selecionada: " + data.path);
                }
            } catch (e) {
                showToast("Erro ao abrir seletor de pastas");
            } finally {
                btnChangeFolderNative.disabled = false;
            }
        });
    }

    if (btnOpenDefaultFolder) {
        btnOpenDefaultFolder.addEventListener("click", () => {
            openFolder(settingFolderPath.value || inputFolderPath.value);
        });
    }

    // Modal de Configurações (Abrir / Fechar / Salvar)
    function openSettingsModal() {
        if (settingsModal) {
            settingsModal.classList.remove("hidden");
        }
    }

    function closeSettingsModal() {
        if (settingsModal) {
            settingsModal.classList.add("hidden");
        }
    }

    if (userPill) userPill.addEventListener("click", openSettingsModal);
    if (btnCloseSettings) btnCloseSettings.addEventListener("click", closeSettingsModal);
    if (btnCancelSettings) btnCancelSettings.addEventListener("click", closeSettingsModal);

    if (settingsModal) {
        settingsModal.addEventListener("click", (e) => {
            if (e.target === settingsModal) closeSettingsModal();
        });
    }

    if (btnSaveSettings) {
        btnSaveSettings.addEventListener("click", async () => {
            const newName = settingUserName.value.trim() || "Usuário";
            localStorage.setItem("nexo_username", newName);
            if (headerUserName) headerUserName.textContent = newName;
            updateAvatarLetter(newName);

            const vidQual = settingDefaultVideoQuality.value;
            const audQual = settingDefaultAudioQuality.value;
            localStorage.setItem("nexo_video_quality", vidQual);
            localStorage.setItem("nexo_audio_quality", audQual);
            if (selQuality) selQuality.value = vidQual;
            if (selAudioQuality) selAudioQuality.value = audQual;

            const folder = settingFolderPath.value.trim();
            if (folder) {
                inputFolderPath.value = folder;
                await fetch("/api/set-downloads-dir", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ path: folder })
                });
            }

            closeSettingsModal();
            showToast("Preferências salvas com sucesso!");
        });
    }

    if (btnResetData) {
        btnResetData.addEventListener("click", () => {
            if (confirm("Deseja limpar a lista de histórico e o cache local?")) {
                completedDownloadsContainer.innerHTML = "";
                completedDownloadsContainer.appendChild(emptyCompletedDownloads);
                emptyCompletedDownloads.classList.remove("hidden");
                completedTasksCount = 0;
                updateCounts();
                showToast("Histórico limpo!");
            }
        });
    }

    // =========================================================================
    // 6. Detecção e Interação com Plataformas
    // =========================================================================
    function detectPlatform(url) {
        if (!url) return null;
        const u = url.toLowerCase().trim();
        if (u.includes("spotify.com") || u.includes("spotify:") || u.includes("spotify.link")) return "Spotify";
        if (u.includes("pinterest") || u.includes("pin.it")) return "Pinterest";
        if (u.includes("youtube.com") || u.includes("youtu.be")) return "YouTube";
        if (u.includes("tiktok.com")) return "TikTok";
        if (u.includes("instagram.com")) return "Instagram";
        if (u.includes("twitter.com") || u.includes("x.com")) return "Twitter";
        if (u.includes("facebook.com") || u.includes("fb.watch")) return "Facebook";
        if (u.includes("apple.com") || u.includes("music.apple.com")) return "AppleMusic";
        if (u.includes("discord.com") || u.includes("discordapp.com")) return "Discord";
        if (u.includes("vimeo.com")) return "Vimeo";
        return null;
    }

    function highlightPlatformCard(platformName) {
        platformCards.forEach(card => {
            if (card.dataset.platform.toLowerCase() === (platformName || "").toLowerCase()) {
                card.classList.add("active-platform");
            } else {
                card.classList.remove("active-platform");
            }
        });
    }

    platformCards.forEach(card => {
        card.addEventListener("click", () => {
            const plat = card.dataset.platform;
            showToast(`Filtro selecionado: ${plat}`);
            highlightPlatformCard(plat);
            urlInput.focus();
        });
    });

    // =========================================================================
    // 7. Input, Limpeza e Pré-Visualização
    // =========================================================================
    urlInput.addEventListener("input", () => {
        const val = urlInput.value.trim();
        btnClearInput.classList.toggle("hidden", val.length === 0);

        const plat = detectPlatform(val);
        highlightPlatformCard(plat);

        if (plat === "Spotify" || plat === "AppleMusic") {
            selFormat.value = "audio";
            toggleFormatOptions();
        }

        clearTimeout(analyzeDebounce);
        if (val.startsWith("http://") || val.startsWith("https://")) {
            analyzeDebounce = setTimeout(() => analyzeUrl(val), 600);
        } else {
            mediaPreviewCard.classList.add("hidden");
        }
    });

    btnClearInput.addEventListener("click", () => {
        urlInput.value = "";
        btnClearInput.classList.add("hidden");
        mediaPreviewCard.classList.add("hidden");
        highlightPlatformCard(null);
        urlInput.focus();
    });

    downloadForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const val = urlInput.value.trim();
        if (val) triggerDownload(val);
    });

    btnDirectDownload.addEventListener("click", () => {
        const val = urlInput.value.trim();
        if (val) triggerDownload(val);
    });

    async function analyzeUrl(url) {
        try {
            const resp = await fetch(`/api/info?url=${encodeURIComponent(url)}`);
            const data = await resp.json();
            if (data.valid) {
                currentMetadata = data;
                let titleText = data.title || "Mídia Pronta para Download";
                if (data.is_collection && data.tracks_count > 1) {
                    titleText += ` (${data.tracks_count} faixas + Álbum Completo)`;
                }
                previewTitle.textContent = titleText;
                previewAuthor.textContent = data.artist || data.platform;
                previewBadge.textContent = data.platform;
                
                if (data.thumbnail) {
                    previewThumb.src = data.thumbnail;
                    previewThumb.classList.remove("hidden");
                } else {
                    previewThumb.src = "/static/icons/app_icon.png";
                }
                
                mediaPreviewCard.classList.remove("hidden");
                highlightPlatformCard(data.platform);
            }
        } catch (e) {
            console.warn("Erro na pré-análise:", e);
        }
    }

    // =========================================================================
    // 8. Opções de Formato (Vídeo vs Áudio)
    // =========================================================================
    selFormat.addEventListener("change", toggleFormatOptions);

    function toggleFormatOptions() {
        const isAudio = selFormat.value === "audio";
        if (isAudio) {
            optQualityWrap.style.opacity = "0.4";
            optQualityWrap.style.pointerEvents = "none";
            optVideoAudioWrap.style.opacity = "0.4";
            optVideoAudioWrap.style.pointerEvents = "none";
        } else {
            optQualityWrap.style.opacity = "1";
            optQualityWrap.style.pointerEvents = "auto";
            optVideoAudioWrap.style.opacity = "1";
            optVideoAudioWrap.style.pointerEvents = "auto";
        }
    }

    // =========================================================================
    // 9. Disparo do Download e WebSocket em Tempo Real
    // =========================================================================
    async function triggerDownload(url) {
        showToast("Iniciando download...");
        btnAnalyze.disabled = true;

        const payload = {
            url: url,
            media_type: selFormat.value,
            quality: parseInt(selQuality.value) || 1080,
            audio_quality: parseInt(selAudioQuality.value) || 320,
            split_chapters: false,
            metadata: chkMetadata.checked,
            custom_folder: inputFolderPath.value || null
        };

        try {
            const response = await fetch("/api/download", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Falha ao iniciar download");
            }

            const data = await response.json();
            const taskId = data.task_id;
            const platform = data.platform || detectPlatform(url) || "Geral";
            const initialTitle = (currentMetadata && currentMetadata.title) ? currentMetadata.title : (url.length > 40 ? url.substring(0, 38) + "..." : url);
            const thumbUrl = (currentMetadata && currentMetadata.thumbnail) ? currentMetadata.thumbnail : "/static/icons/app_icon.png";

            createActiveDownloadCard(taskId, initialTitle, platform, thumbUrl);
            connectWebSocket(taskId);

            urlInput.value = "";
            btnClearInput.classList.add("hidden");
            mediaPreviewCard.classList.add("hidden");
            currentMetadata = null;
        } catch (err) {
            showToast(`Erro: ${err.message}`);
        } finally {
            btnAnalyze.disabled = false;
        }
    }

    function connectWebSocket(taskId) {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws/progress/${taskId}`;
        const ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                updateActiveCard(taskId, data);

                if (data.status === "finished" || data.status === "error") {
                    ws.close();
                }
            } catch (e) {
                console.error("Erro no processamento do WebSocket:", e);
            }
        };

        ws.onerror = () => {
            updateActiveCard(taskId, {
                status: "error",
                message: "Falha na conexão de progresso em tempo real."
            });
        };
    }

    function createActiveDownloadCard(taskId, title, platform, thumbUrl) {
        emptyActiveDownloads.classList.add("hidden");
        activeTasksCount++;
        updateCounts();

        const card = document.createElement("div");
        card.className = "download-card active-item";
        card.id = `task-${taskId}`;
        card.innerHTML = `
            <div class="download-thumb-wrap">
                <img src="${thumbUrl}" alt="Thumbnail" class="download-thumb-img" onerror="this.src='/static/icons/app_icon.png'">
                <span class="download-platform-tag tag-${platform.toLowerCase()}">${platform}</span>
            </div>
            <div class="download-details">
                <div class="download-header-line">
                    <h4 class="download-title" title="${escapeHtml(title)}">${escapeHtml(title)}</h4>
                    <span class="download-status-badge status-starting" id="badge-${taskId}">Iniciando...</span>
                </div>
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="fill-${taskId}" style="width: 5%"></div>
                </div>
                <div class="download-meta-line">
                    <span class="download-status-msg" id="msg-${taskId}">Conectando...</span>
                    <div class="download-stats">
                        <span id="speed-${taskId}">--</span>
                        <span class="stats-sep">&bull;</span>
                        <span id="eta-${taskId}">--</span>
                        <span class="stats-sep">&bull;</span>
                        <span id="percent-${taskId}">0%</span>
                    </div>
                </div>
            </div>
        `;

        activeDownloadsContainer.prepend(card);
    }

    function updateActiveCard(taskId, data) {
        const card = document.getElementById(`task-${taskId}`);
        if (!card) return;

        const badge = document.getElementById(`badge-${taskId}`);
        const fill = document.getElementById(`fill-${taskId}`);
        const msg = document.getElementById(`msg-${taskId}`);
        const speed = document.getElementById(`speed-${taskId}`);
        const eta = document.getElementById(`eta-${taskId}`);
        const percent = document.getElementById(`percent-${taskId}`);

        if (data.percent !== undefined) {
            fill.style.width = `${Math.min(data.percent, 100)}%`;
            percent.textContent = `${Math.round(data.percent)}%`;
        }

        if (data.message) msg.textContent = data.message;
        if (data.speed_str) speed.textContent = data.speed_str;
        if (data.eta_str) eta.textContent = `ETA: ${data.eta_str}`;

        if (data.status === "downloading") {
            badge.className = "download-status-badge status-downloading";
            badge.textContent = "Baixando";
        } else if (data.status === "converting") {
            badge.className = "download-status-badge status-converting";
            badge.textContent = "Processando";
        } else if (data.status === "finished") {
            badge.className = "download-status-badge status-finished";
            badge.textContent = "Concluído";
            showToast("Download concluído com sucesso!");

            setTimeout(() => {
                card.remove();
                activeTasksCount = Math.max(0, activeTasksCount - 1);
                if (activeTasksCount === 0) {
                    emptyActiveDownloads.classList.remove("hidden");
                }
                updateCounts();
                addCompletedCard(data);
            }, 1200);
        } else if (data.status === "error") {
            badge.className = "download-status-badge status-error";
            badge.textContent = "Falhou";
            fill.style.background = "#ef4444";
            msg.textContent = data.error || "Ocorreu um erro no download.";
            showToast("Erro durante o download");
        }
    }

    function addCompletedCard(data) {
        emptyCompletedDownloads.classList.add("hidden");
        completedTasksCount++;
        updateCounts();

        const title = data.filename || data.name || "Arquivo Baixado";
        const platform = data.platform || "Geral";
        const sizeMb = data.size_mb || 0;
        const filePath = data.file_path || "";
        const folderPath = data.folder_path || "";
        const ext = data.ext || (filePath.endsWith(".mp3") ? "mp3" : "mp4");

        const card = document.createElement("div");
        card.className = "download-card completed-item";
        card.innerHTML = `
            <div class="completed-icon-box ext-${ext}">
                ${ext.toUpperCase()}
            </div>
            <div class="download-details">
                <div class="download-header-line">
                    <h4 class="download-title" title="${escapeHtml(title)}">${escapeHtml(title)}</h4>
                    <span class="completed-platform-tag">${platform}</span>
                </div>
                <div class="download-meta-line">
                    <span class="completed-size">${sizeMb > 0 ? sizeMb + " MB" : ""}</span>
                    <span class="completed-meta-text">Pronto para reproduzir</span>
                </div>
            </div>
            <div class="completed-actions">
                <button type="button" class="btn-action-ghost btn-open-file" title="Abrir Arquivo">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    <span>Reproduzir</span>
                </button>
                <button type="button" class="btn-action-ghost btn-open-folder" title="Abrir Pasta">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                </button>
            </div>
        `;

        card.querySelector(".btn-open-file").addEventListener("click", () => {
            openFile(filePath);
        });

        card.querySelector(".btn-open-folder").addEventListener("click", () => {
            openFolder(folderPath || filePath);
        });

        completedDownloadsContainer.prepend(card);
    }

    async function loadCompletedHistory() {
        try {
            const resp = await fetch("/api/history");
            const data = await resp.json();
            if (data.files && data.files.length > 0) {
                emptyCompletedDownloads.classList.add("hidden");
                data.files.forEach(f => {
                    addCompletedCard(f);
                });
            } else {
                emptyCompletedDownloads.classList.remove("hidden");
            }
        } catch (e) {
            console.warn("Não foi possível carregar o histórico:", e);
        }
    }

    btnClearCompleted.addEventListener("click", () => {
        completedDownloadsContainer.innerHTML = "";
        completedDownloadsContainer.appendChild(emptyCompletedDownloads);
        emptyCompletedDownloads.classList.remove("hidden");
        completedTasksCount = 0;
        updateCounts();
        showToast("Lista de downloads limpa.");
    });

    btnBrowseFolder.addEventListener("click", () => {
        openFolder(inputFolderPath.value);
    });

    async function openFolder(folderOrFilePath) {
        try {
            const res = await fetch("/api/open-folder", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file_path: folderOrFilePath })
            });
            if (res.ok) {
                showToast("Pasta aberta no Windows Explorer");
            } else {
                showToast("Pasta não encontrada");
            }
        } catch (e) {
            showToast("Erro ao abrir pasta");
        }
    }

    async function openFile(filePath) {
        try {
            const res = await fetch("/api/open-file", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file_path: filePath })
            });
            if (res.ok) {
                showToast("Abrindo mídia...");
            } else {
                showToast("Arquivo não encontrado");
            }
        } catch (e) {
            showToast("Erro ao abrir arquivo");
        }
    }

    function updateCounts() {
        activeCount.textContent = `(${activeTasksCount})`;
        completedCount.textContent = `(${completedTasksCount})`;
    }

    // =========================================================================
    // 10. Navegação da Sidebar
    // =========================================================================
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            navItems.forEach(n => n.classList.remove("active"));
            item.classList.add("active");
            const view = item.dataset.view;

            if (view === "downloads") {
                document.getElementById("sectionActiveDownloads").scrollIntoView({ behavior: "smooth" });
            } else if (view === "historico") {
                document.getElementById("sectionCompletedDownloads").scrollIntoView({ behavior: "smooth" });
            } else if (view === "plataformas") {
                document.querySelector(".platforms-section").scrollIntoView({ behavior: "smooth" });
            } else if (view === "configuracoes") {
                openSettingsModal();
            }
        });
    });

    // =========================================================================
    // 11. Utilitários
    // =========================================================================
    function showToast(msg) {
        toastMessage.textContent = msg;
        toast.classList.remove("hidden");
        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.add("hidden");
        }, 3200);
    }

    function escapeHtml(str) {
        if (!str) return "";
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
});
