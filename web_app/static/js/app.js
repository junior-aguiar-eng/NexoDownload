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
    const btnSelectFolderInline = document.getElementById("btnSelectFolderInline");
    const chkMetadata = document.getElementById("chkMetadata");
    const chkSplitChapters = document.getElementById("chkSplitChapters");
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

    if (btnSelectFolderInline) {
        btnSelectFolderInline.addEventListener("click", async () => {
            btnSelectFolderInline.disabled = true;
            try {
                const resp = await fetch("/api/select-folder", { method: "POST" });
                const data = await resp.json();
                if (data.success && data.path) {
                    inputFolderPath.value = data.path;
                    if (settingFolderPath) settingFolderPath.value = data.path;
                    await fetch("/api/set-downloads-dir", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ path: data.path })
                    });
                    showToast("Pasta alterada: " + data.path);
                }
            } catch (e) {
                showToast("Erro ao abrir seletor de pastas");
            } finally {
                btnSelectFolderInline.disabled = false;
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
        if (u.includes("soundcloud.com") || u.includes("snd.sc")) return "SoundCloud";
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

        if (plat === "Spotify" || plat === "AppleMusic" || plat === "SoundCloud") {
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
                if (data.requires_prive_unlock) {
                    showToast("Conteúdo Privê detectado. Desbloqueie com sua senha.");
                    openPriveAuthModal(() => {
                        analyzeUrl(url);
                    });
                    return;
                }

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
        const isPriveUrl = (currentMetadata && currentMetadata.is_prive) || url.toLowerCase().includes("xvideos");
        if (isPriveUrl && !isPriveUnlocked) {
            showToast("Sessão Privê bloqueada. Desbloqueie para baixar.");
            openPriveAuthModal(() => {
                triggerDownload(url);
            });
            btnAnalyze.disabled = false;
            return;
        }

        showToast("Iniciando download...");
        btnAnalyze.disabled = true;

        const payload = {
            url: url,
            media_type: selFormat.value,
            quality: parseInt(selQuality.value, 10) || 1080,
            audio_quality: parseInt(selAudioQuality.value, 10) || 320,
            video_audio: selVideoAudio ? selVideoAudio.value : "with_audio",
            split_chapters: chkSplitChapters ? chkSplitChapters.checked : false,
            metadata: chkMetadata ? chkMetadata.checked : true,
            custom_folder: inputFolderPath.value || null,
            is_prive: isPriveUrl
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
        let retryCount = 0;
        const maxRetries = 3;

        function initWs() {
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
                if (retryCount < maxRetries) {
                    retryCount++;
                    setTimeout(initWs, 1200);
                } else {
                    // Fallback resiliente: ativa polling HTTP se WebSocket cair
                    startFallbackPolling();
                }
            };
        }

        function startFallbackPolling() {
            const pollTimer = setInterval(async () => {
                try {
                    const res = await fetch(`/api/download/status/${taskId}`);
                    if (res.ok) {
                        const statusData = await res.json();
                        const payload = statusData.last_payload && Object.keys(statusData.last_payload).length > 0 
                            ? statusData.last_payload 
                            : {
                                status: statusData.status,
                                percent: statusData.percent,
                                message: statusData.message,
                                platform: statusData.platform,
                                is_prive: statusData.is_prive
                            };
                        updateActiveCard(taskId, payload);
                        if (statusData.status === "finished" || statusData.status === "error" || statusData.status === "cancelled") {
                            clearInterval(pollTimer);
                        }
                    } else if (res.status === 404) {
                        clearInterval(pollTimer);
                    }
                } catch {
                    // Ignora falhas transitórias durante polling
                }
            }, 2000);
        }

        initWs();
    }

    window.cancelDownloadTask = async function(taskId) {
        const btn = document.getElementById(`cancel-${taskId}`);
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = `<span>Cancelando...</span>`;
        }
        try {
            const resp = await fetch(`/api/download/cancel/${taskId}`, { method: "POST" });
            if (resp.ok) {
                const resData = await resp.json();
                if (resData.success) {
                    showToast("Cancelamento solicitado.");
                }
            }
        } catch (e) {
            console.error("Erro ao cancelar tarefa:", e);
        }
    };

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
                    <div class="download-header-actions">
                        <span class="download-status-badge status-starting" id="badge-${taskId}">Iniciando...</span>
                        <button type="button" class="btn-cancel-task" id="cancel-${taskId}" title="Cancelar Download" onclick="window.cancelDownloadTask('${taskId}')">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                            <span>Cancelar</span>
                        </button>
                    </div>
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
        const cancelBtn = document.getElementById(`cancel-${taskId}`);

        if (data.status === "cancelled") {
            if (badge) {
                badge.className = "download-status-badge status-error";
                badge.textContent = "Cancelado";
            }
            if (fill) fill.style.background = "#94a3b8";
            if (msg) msg.textContent = data.message || "Download cancelado pelo usuário.";
            if (cancelBtn) cancelBtn.remove();
            showToast("Download cancelado");
            setTimeout(() => {
                card.remove();
                activeTasksCount = Math.max(0, activeTasksCount - 1);
                if (activeTasksCount === 0) {
                    emptyActiveDownloads.classList.remove("hidden");
                }
                updateCounts();
            }, 2200);
            return;
        }

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
            if (cancelBtn) cancelBtn.remove();
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
            if (cancelBtn) cancelBtn.remove();
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

        const isPriveItem = !!data.is_prive;
        const priveTagHtml = isPriveItem ? '<span class="prive-badge-pill">Privê 18+</span>' : '';

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
                    ${priveTagHtml}
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
            const resp = await fetch(`/api/history?show_prive=${isPriveUnlocked}`);
            const data = await resp.json();
            completedDownloadsContainer.innerHTML = "";
            completedDownloadsContainer.appendChild(emptyCompletedDownloads);
            if (data.files && data.files.length > 0) {
                emptyCompletedDownloads.classList.add("hidden");
                completedTasksCount = data.files.length;
                data.files.forEach(f => {
                    addCompletedCard(f);
                });
            } else {
                completedTasksCount = 0;
                emptyCompletedDownloads.classList.remove("hidden");
            }
            updateCounts();
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
            if (view === "inicio") {
                window.scrollTo({ top: 0, behavior: "smooth" });
                if (urlInput) urlInput.focus();
            } else if (view === "downloads") {
                document.getElementById("sectionActiveDownloads").scrollIntoView({ behavior: "smooth" });
            } else if (view === "historico") {
                document.getElementById("sectionCompletedDownloads").scrollIntoView({ behavior: "smooth" });
            } else if (view === "plataformas") {
                document.querySelector(".platforms-section").scrollIntoView({ behavior: "smooth" });
            } else if (view === "configuracoes") {
                openSettingsModal();
            } else if (view === "estudio-voz") {
                const studioSection = document.getElementById("sectionEstudioVoz");
                if (studioSection) studioSection.scrollIntoView({ behavior: "smooth" });
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

    // =========================================================================
    // 12. Sessão Privê (18+ / Conteúdo Adulto Protegido por Senha)
    // =========================================================================
    let isPriveUnlocked = false;
    let isPriveConfigured = false;
    let privePendingCallback = null;

    const btnPriveToggle = document.getElementById("btnPriveToggle");
    const priveLockIcon = document.getElementById("priveLockIcon");
    const priveToggleText = document.getElementById("priveToggleText");

    const modalPriveSetup = document.getElementById("modalPriveSetup");
    const btnClosePriveSetup = document.getElementById("btnClosePriveSetup");
    const btnCancelPriveSetup = document.getElementById("btnCancelPriveSetup");
    const btnSavePriveSetup = document.getElementById("btnSavePriveSetup");
    const priveSetupPwd = document.getElementById("priveSetupPwd");
    const priveSetupPwdConfirm = document.getElementById("priveSetupPwdConfirm");
    const priveSetupError = document.getElementById("priveSetupError");

    const modalPriveUnlock = document.getElementById("modalPriveUnlock");
    const btnClosePriveUnlock = document.getElementById("btnClosePriveUnlock");
    const btnCancelPriveUnlock = document.getElementById("btnCancelPriveUnlock");
    const btnConfirmPriveUnlock = document.getElementById("btnConfirmPriveUnlock");
    const btnForgotPrive = document.getElementById("btnForgotPrive");
    const priveUnlockPwd = document.getElementById("priveUnlockPwd");
    const priveUnlockError = document.getElementById("priveUnlockError");

    const priveSettingsStatusBadge = document.getElementById("priveSettingsStatusBadge");
    const btnResetPriveCredentials = document.getElementById("btnResetPriveCredentials");

    async function checkPriveStatus() {
        try {
            const resp = await fetch("/api/prive/status");
            const data = await resp.json();
            isPriveConfigured = !!data.configured;
            isPriveUnlocked = !!data.unlocked;
            updatePriveUI();
        } catch (e) {
            console.warn("Erro ao checar status privê:", e);
        }
    }

    function updatePriveUI() {
        if (!btnPriveToggle) return;
        if (isPriveUnlocked) {
            btnPriveToggle.classList.add("unlocked");
            priveLockIcon.textContent = "🔓";
            priveToggleText.textContent = "Privê Ativo (Trancar)";
            btnPriveToggle.title = "Sessão Privê Desbloqueada. Clique para trancar.";
        } else {
            btnPriveToggle.classList.remove("unlocked");
            priveLockIcon.textContent = "🔒";
            priveToggleText.textContent = "Privê";
            btnPriveToggle.title = "Sessão Privê (Conteúdo Adulto Protegido por Senha)";
        }

        if (priveSettingsStatusBadge) {
            if (isPriveConfigured) {
                priveSettingsStatusBadge.textContent = "Senha Ativa";
                priveSettingsStatusBadge.className = "prive-status-badge active";
            } else {
                priveSettingsStatusBadge.textContent = "Não Configurada";
                priveSettingsStatusBadge.className = "prive-status-badge";
            }
        }
    }

    if (btnPriveToggle) {
        btnPriveToggle.addEventListener("click", async () => {
            if (isPriveUnlocked) {
                try {
                    await fetch("/api/prive/lock", { method: "POST" });
                    isPriveUnlocked = false;
                    updatePriveUI();
                    loadCompletedHistory();
                    showToast("Sessão Privê trancada com segurança.");
                } catch (e) {
                    showToast("Erro ao trancar sessão.");
                }
            } else {
                openPriveAuthModal();
            }
        });
    }

    function openPriveAuthModal(onSuccess) {
        privePendingCallback = onSuccess || null;
        if (!isPriveConfigured) {
            priveSetupPwd.value = "";
            priveSetupPwdConfirm.value = "";
            priveSetupError.classList.add("hidden");
            modalPriveSetup.classList.remove("hidden");
            priveSetupPwd.focus();
        } else {
            priveUnlockPwd.value = "";
            priveUnlockError.classList.add("hidden");
            modalPriveUnlock.classList.remove("hidden");
            priveUnlockPwd.focus();
        }
    }

    // Handlers do Modal de Setup
    if (btnClosePriveSetup) btnClosePriveSetup.addEventListener("click", () => modalPriveSetup.classList.add("hidden"));
    if (btnCancelPriveSetup) btnCancelPriveSetup.addEventListener("click", () => modalPriveSetup.classList.add("hidden"));

    if (btnSavePriveSetup) {
        btnSavePriveSetup.addEventListener("click", async () => {
            const pwd = priveSetupPwd.value.trim();
            const pwdConf = priveSetupPwdConfirm.value.trim();

            if (pwd.length < 4) {
                priveSetupError.textContent = "A senha deve conter no mínimo 4 caracteres.";
                priveSetupError.classList.remove("hidden");
                return;
            }
            if (pwd !== pwdConf) {
                priveSetupError.textContent = "As senhas não coincidem. Digite novamente.";
                priveSetupError.classList.remove("hidden");
                return;
            }

            try {
                const resp = await fetch("/api/prive/setup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ password: pwd })
                });
                const data = await resp.json();
                if (data.success) {
                    isPriveConfigured = true;
                    isPriveUnlocked = true;
                    updatePriveUI();
                    modalPriveSetup.classList.add("hidden");
                    showToast("Senha cadastrada! Sessão Privê desbloqueada.");
                    loadCompletedHistory();
                    if (typeof privePendingCallback === "function") {
                        privePendingCallback();
                        privePendingCallback = null;
                    }
                } else {
                    priveSetupError.textContent = data.message || "Erro ao salvar senha.";
                    priveSetupError.classList.remove("hidden");
                }
            } catch (e) {
                priveSetupError.textContent = "Erro ao conectar com o servidor.";
                priveSetupError.classList.remove("hidden");
            }
        });
    }

    // Handlers do Modal de Unlock
    if (btnClosePriveUnlock) btnClosePriveUnlock.addEventListener("click", () => modalPriveUnlock.classList.add("hidden"));
    if (btnCancelPriveUnlock) btnCancelPriveUnlock.addEventListener("click", () => modalPriveUnlock.classList.add("hidden"));

    if (btnConfirmPriveUnlock) {
        btnConfirmPriveUnlock.addEventListener("click", async () => {
            const pwd = priveUnlockPwd.value.trim();
            if (!pwd) {
                priveUnlockError.textContent = "Digite sua senha privê.";
                priveUnlockError.classList.remove("hidden");
                return;
            }

            try {
                const resp = await fetch("/api/prive/unlock", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ password: pwd })
                });
                const data = await resp.json();
                if (data.success) {
                    isPriveUnlocked = true;
                    updatePriveUI();
                    modalPriveUnlock.classList.add("hidden");
                    showToast("Sessão Privê desbloqueada com sucesso!");
                    loadCompletedHistory();
                    if (typeof privePendingCallback === "function") {
                        privePendingCallback();
                        privePendingCallback = null;
                    }
                } else {
                    priveUnlockError.textContent = data.message || "Senha incorreta.";
                    priveUnlockError.classList.remove("hidden");
                }
            } catch (e) {
                priveUnlockError.textContent = "Erro ao validar senha.";
                priveUnlockError.classList.remove("hidden");
            }
        });
    }

    if (priveUnlockPwd) {
        priveUnlockPwd.addEventListener("keydown", (e) => {
            if (e.key === "Enter") btnConfirmPriveUnlock.click();
        });
    }
    if (priveSetupPwdConfirm) {
        priveSetupPwdConfirm.addEventListener("keydown", (e) => {
            if (e.key === "Enter") btnSavePriveSetup.click();
        });
    }

    if (btnForgotPrive) {
        btnForgotPrive.addEventListener("click", async () => {
            if (confirm("Deseja redefinir sua senha da Sessão Privê?\\n\\n(Nota: Seus vídeos baixados no computador NÃO serão apagados).")) {
                try {
                    await fetch("/api/prive/reset", { method: "POST" });
                    isPriveConfigured = false;
                    isPriveUnlocked = false;
                    updatePriveUI();
                    modalPriveUnlock.classList.add("hidden");
                    showToast("Credenciais Privê redefinidas. Agora você pode cadastrar uma nova senha.");
                    openPriveAuthModal(privePendingCallback);
                } catch (e) {
                    showToast("Erro ao redefinir credenciais.");
                }
            }
        });
    }

    if (btnResetPriveCredentials) {
        btnResetPriveCredentials.addEventListener("click", async () => {
            if (confirm("Tem certeza que deseja redefinir sua senha da Sessão Privê?\\n\\nIsso permitirá cadastrar uma nova senha. Os arquivos baixados no disco continuam intactos.")) {
                try {
                    await fetch("/api/prive/reset", { method: "POST" });
                    isPriveConfigured = false;
                    isPriveUnlocked = false;
                    updatePriveUI();
                    loadCompletedHistory();
                    showToast("Senha da Sessão Privê redefinida com sucesso.");
                } catch (e) {
                    showToast("Erro ao redefinir senha privê.");
                }
            }
        });
    }

    // Inicialização da Sessão Privê
    checkPriveStatus();

    // =========================================================================
    // 13. Estúdio de Voz & IA (DSP Tradicional, RVC Neural e Treinador Applio)
    // =========================================================================
    const studioHwBadge = document.getElementById("studioHwBadge");
    const studioHwText = document.getElementById("studioHwText");
    const tabBtnModificador = document.getElementById("tabBtnModificador");
    const tabBtnTreinador = document.getElementById("tabBtnTreinador");
    const tabModificador = document.getElementById("tabModificador");
    const tabTreinador = document.getElementById("tabTreinador");

    const inputAudioStudioSource = document.getElementById("inputAudioStudioSource");
    const btnBrowseAudioSource = document.getElementById("btnBrowseAudioSource");
    const btnUseDemoAudio = document.getElementById("btnUseDemoAudio");

    const cardEngineDsp = document.getElementById("cardEngineDsp");
    const cardEngineRvc = document.getElementById("cardEngineRvc");
    const radioEngineDsp = document.querySelector('input[name="audioEngineType"][value="dsp"]');
    const radioEngineRvc = document.querySelector('input[name="audioEngineType"][value="rvc"]');
    const boxDspControls = document.getElementById("boxDspControls");
    const boxRvcControls = document.getElementById("boxRvcControls");

    const selDspPreset = document.getElementById("selDspPreset");
    const chkDspDenoise = document.getElementById("chkDspDenoise");
    const sliderDspPitch = document.getElementById("sliderDspPitch");
    const sliderDspFormant = document.getElementById("sliderDspFormant");
    const dspPitchVal = document.getElementById("dspPitchVal");
    const dspFormantVal = document.getElementById("dspFormantVal");

    const selRvcModel = document.getElementById("selRvcModel");
    const btnOpenModelsFolder = document.getElementById("btnOpenModelsFolder");
    const selRvcF0 = document.getElementById("selRvcF0");
    const sliderRvcPitch = document.getElementById("sliderRvcPitch");
    const sliderRvcIndex = document.getElementById("sliderRvcIndex");
    const rvcPitchVal = document.getElementById("rvcPitchVal");
    const rvcIndexVal = document.getElementById("rvcIndexVal");

    const btnExecuteVoiceProcess = document.getElementById("btnExecuteVoiceProcess");
    const btnExecuteVoiceText = document.getElementById("btnExecuteVoiceText");
    const studioPlayerCard = document.getElementById("studioPlayerCard");
    const playerAudioTitle = document.getElementById("playerAudioTitle");
    const playerAudioMeta = document.getElementById("playerAudioMeta");
    const audioStudioPlayer = document.getElementById("audioStudioPlayer");
    const btnOpenProcessedFile = document.getElementById("btnOpenProcessedFile");

    // Treinador
    const inputTrainAudioSource = document.getElementById("inputTrainAudioSource");
    const btnBrowseTrainSource = document.getElementById("btnBrowseTrainSource");
    const btnUseDemoForTraining = document.getElementById("btnUseDemoForTraining");
    const inputTrainModelName = document.getElementById("inputTrainModelName");
    const selTrainSampleRate = document.getElementById("selTrainSampleRate");
    const sliderTrainEpochs = document.getElementById("sliderTrainEpochs");
    const trainEpochsVal = document.getElementById("trainEpochsVal");
    const chkTrainDenoise = document.getElementById("chkTrainDenoise");
    const btnStartTraining = document.getElementById("btnStartTraining");
    const btnStartTrainText = document.getElementById("btnStartTrainText");
    const trainProgressCard = document.getElementById("trainProgressCard");
    const trainProgressTitle = document.getElementById("trainProgressTitle");
    const trainProgressPercent = document.getElementById("trainProgressPercent");
    const trainProgressBar = document.getElementById("trainProgressBar");
    const trainProgressMsg = document.getElementById("trainProgressMsg");

    let lastProcessedFilePath = null;
    let audioDemoPath = "";
    let dspPresetsCatalog = {};
    let trainPollingInterval = null;

    // Alternância de Abas: Modificador vs Treinador
    if (tabBtnModificador && tabBtnTreinador) {
        tabBtnModificador.addEventListener("click", () => {
            tabBtnModificador.classList.add("active");
            tabBtnTreinador.classList.remove("active");
            tabModificador.classList.remove("hidden");
            tabTreinador.classList.add("hidden");
        });
        tabBtnTreinador.addEventListener("click", () => {
            tabBtnTreinador.classList.add("active");
            tabBtnModificador.classList.remove("active");
            tabTreinador.classList.remove("hidden");
            tabModificador.classList.add("hidden");
        });
    }

    // Alternância de Motor (DSP vs RVC)
    function updateEngineView() {
        const isDsp = radioEngineDsp && radioEngineDsp.checked;
        if (cardEngineDsp) cardEngineDsp.classList.toggle("active", isDsp);
        if (cardEngineRvc) cardEngineRvc.classList.toggle("active", !isDsp);
        if (boxDspControls) boxDspControls.classList.toggle("hidden", !isDsp);
        if (boxRvcControls) boxRvcControls.classList.toggle("hidden", isDsp);
    }

    if (radioEngineDsp) radioEngineDsp.addEventListener("change", updateEngineView);
    if (radioEngineRvc) radioEngineRvc.addEventListener("change", updateEngineView);

    // Carregamento de Status e Modelos
    async function loadAudioEngineStatus() {
        try {
            const resp = await fetch("/api/audio/status");
            const data = await resp.json();
            if (data.available) {
                if (studioHwText) {
                    const devText = (data.device === "cuda") ? "GPU (CUDA Ativo)" : "CPU (Processamento Local)";
                    studioHwText.textContent = devText;
                }
                if (data.demo_path) audioDemoPath = data.demo_path;
                if (data.dsp_presets) dspPresetsCatalog = data.dsp_presets;
            } else {
                if (studioHwText) studioHwText.textContent = "Motor Não Carregado";
            }
        } catch (e) {
            console.warn("[AudioStudio]: Falha ao checar status:", e);
        }
    }

    async function loadAudioModels() {
        if (!selRvcModel) return;
        try {
            const resp = await fetch("/api/audio/models");
            const data = await resp.json();
            selRvcModel.innerHTML = "";
            if (data.models && data.models.length > 0) {
                data.models.forEach(m => {
                    const opt = document.createElement("option");
                    opt.value = m.name;
                    opt.textContent = `${m.name} (${m.size_mb} MB${m.has_index ? " • FAISS Index" : ""})`;
                    selRvcModel.appendChild(opt);
                });
            } else {
                const opt = document.createElement("option");
                opt.value = "";
                opt.textContent = "Nenhum modelo .pth encontrado em 'modelos/'";
                selRvcModel.appendChild(opt);
            }
        } catch (e) {
            console.warn("[AudioStudio]: Falha ao listar modelos:", e);
        }
    }

    // Seletor Nativo de Áudio de Entrada
    if (btnBrowseAudioSource) {
        btnBrowseAudioSource.addEventListener("click", async () => {
            btnBrowseAudioSource.disabled = true;
            try {
                const resp = await fetch("/api/audio/select-file", { method: "POST" });
                const data = await resp.json();
                if (data.success && data.path) {
                    inputAudioStudioSource.value = data.path;
                    showToast("Áudio selecionado: " + (data.name || data.path));
                }
            } catch (e) {
                showToast("Erro ao abrir seletor de arquivos.");
            } finally {
                btnBrowseAudioSource.disabled = false;
            }
        });
    }

    // Botão de Áudio Demo
    if (btnUseDemoAudio) {
        btnUseDemoAudio.addEventListener("click", () => {
            if (audioDemoPath) {
                inputAudioStudioSource.value = audioDemoPath;
                showToast("Áudio de demonstração carregado com sucesso!");
            } else {
                showToast("Áudio de demonstração não localizado.");
            }
        });
    }

    // Controle de Sliders DSP
    if (sliderDspPitch && dspPitchVal) {
        sliderDspPitch.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value);
            dspPitchVal.textContent = `${val >= 0 ? "+" : ""}${val.toFixed(1)} st`;
            if (selDspPreset) selDspPreset.value = "custom";
        });
    }

    if (sliderDspFormant && dspFormantVal) {
        sliderDspFormant.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value);
            dspFormantVal.textContent = `${val >= 0 ? "+" : ""}${val.toFixed(1)} st`;
            if (selDspPreset) selDspPreset.value = "custom";
        });
    }

    // Preset selecionado no DSP
    if (selDspPreset) {
        selDspPreset.addEventListener("change", (e) => {
            const pKey = e.target.value;
            if (pKey !== "custom" && dspPresetsCatalog[pKey]) {
                const p = dspPresetsCatalog[pKey];
                sliderDspPitch.value = p.semitones;
                dspPitchVal.textContent = `${p.semitones >= 0 ? "+" : ""}${p.semitones.toFixed(1)} st`;
                sliderDspFormant.value = p.formant_shift_semitones;
                dspFormantVal.textContent = `${p.formant_shift_semitones >= 0 ? "+" : ""}${p.formant_shift_semitones.toFixed(1)} st`;
                if (chkDspDenoise) chkDspDenoise.checked = p.reduce_noise;
            }
        });
    }

    // Controle de Sliders RVC
    if (sliderRvcPitch && rvcPitchVal) {
        sliderRvcPitch.addEventListener("input", (e) => {
            const val = parseInt(e.target.value);
            rvcPitchVal.textContent = `${val >= 0 ? "+" : ""}${val} st`;
        });
    }

    if (sliderRvcIndex && rvcIndexVal) {
        sliderRvcIndex.addEventListener("input", (e) => {
            rvcIndexVal.textContent = e.target.value;
        });
    }

    // Abrir pasta de modelos no Explorer
    if (btnOpenModelsFolder) {
        btnOpenModelsFolder.addEventListener("click", async () => {
            try {
                await fetch("/api/audio/open-models-folder", { method: "POST" });
                showToast("Pasta de modelos aberta no Windows Explorer");
            } catch (e) {
                showToast("Erro ao abrir pasta de modelos");
            }
        });
    }

    // Executar Modificação Vocal (DSP ou RVC)
    if (btnExecuteVoiceProcess) {
        btnExecuteVoiceProcess.addEventListener("click", async () => {
            const inputPath = inputAudioStudioSource ? inputAudioStudioSource.value.trim() : "";
            if (!inputPath) {
                showToast("Selecione primeiro um arquivo de áudio de origem!");
                return;
            }

            const isDsp = radioEngineDsp && radioEngineDsp.checked;
            btnExecuteVoiceProcess.disabled = true;
            const originalText = btnExecuteVoiceText.textContent;
            btnExecuteVoiceText.textContent = isDsp ? "Processando filtros DSP..." : "Realizando inferência RVC neural...";

            try {
                let resp;
                if (isDsp) {
                    const payload = {
                        input_path: inputPath,
                        preset: selDspPreset ? selDspPreset.value : "custom",
                        semitones: parseFloat(sliderDspPitch.value),
                        formant_shift_semitones: parseFloat(sliderDspFormant.value),
                        preserve_formants: true,
                        reduce_noise: chkDspDenoise ? chkDspDenoise.checked : true,
                        noise_prop_decrease: 0.85
                    };
                    resp = await fetch("/api/audio/process-dsp", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });
                } else {
                    const selectedModel = selRvcModel ? selRvcModel.value : "";
                    if (!selectedModel) {
                        showToast("Selecione um modelo de voz RVC válido (.pth)!");
                        btnExecuteVoiceProcess.disabled = false;
                        btnExecuteVoiceText.textContent = originalText;
                        return;
                    }
                    const payload = {
                        input_path: inputPath,
                        model_name: selectedModel,
                        pitch_semitones: parseInt(sliderRvcPitch.value),
                        index_rate: parseFloat(sliderRvcIndex.value),
                        f0_method: selRvcF0 ? selRvcF0.value : "rmvpe"
                    };
                    resp = await fetch("/api/audio/process-rvc", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify(payload)
                    });
                }

                const data = await resp.json();
                if (resp.ok && data.success) {
                    lastProcessedFilePath = data.output_path;
                    if (playerAudioTitle) playerAudioTitle.textContent = data.filename;
                    if (playerAudioMeta) playerAudioMeta.textContent = `${data.size_mb} MB • 24-bit PCM WAV Estúdio`;
                    if (audioStudioPlayer) {
                        audioStudioPlayer.src = data.stream_url;
                        audioStudioPlayer.load();
                        audioStudioPlayer.play().catch(() => {});
                    }
                    if (studioPlayerCard) studioPlayerCard.classList.remove("hidden");
                    studioPlayerCard.scrollIntoView({ behavior: "smooth" });
                    showToast("Áudio gerado com sucesso em 24-bit PCM!");
                } else {
                    showToast("Falha no processamento: " + (data.detail || "Erro desconhecido"));
                }
            } catch (err) {
                showToast("Erro na comunicação com o servidor de áudio.");
            } finally {
                btnExecuteVoiceProcess.disabled = false;
                btnExecuteVoiceText.textContent = originalText;
            }
        });
    }

    // Botão para abrir áudio processado
    if (btnOpenProcessedFile) {
        btnOpenProcessedFile.addEventListener("click", () => {
            if (lastProcessedFilePath) {
                openFolder(lastProcessedFilePath);
            }
        });
    }

    // =========================================================================
    // Treinador de Voz (Applio Clonador)
    // =========================================================================
    if (sliderTrainEpochs && trainEpochsVal) {
        sliderTrainEpochs.addEventListener("input", (e) => {
            trainEpochsVal.textContent = `${e.target.value} épocas`;
        });
    }

    if (btnBrowseTrainSource) {
        btnBrowseTrainSource.addEventListener("click", async () => {
            btnBrowseTrainSource.disabled = true;
            try {
                const resp = await fetch("/api/audio/select-file", { method: "POST" });
                const data = await resp.json();
                if (data.success && data.path) {
                    inputTrainAudioSource.value = data.path;
                    showToast("Gravação selecionada: " + (data.name || data.path));
                }
            } catch (e) {
                showToast("Erro ao abrir seletor.");
            } finally {
                btnBrowseTrainSource.disabled = false;
            }
        });
    }

    if (btnUseDemoForTraining) {
        btnUseDemoForTraining.addEventListener("click", () => {
            if (audioDemoPath) {
                inputTrainAudioSource.value = audioDemoPath;
                showToast("Gravação demo carregada para treinamento!");
            }
        });
    }

    if (btnStartTraining) {
        btnStartTraining.addEventListener("click", async () => {
            const src = inputTrainAudioSource ? inputTrainAudioSource.value.trim() : "";
            const modelName = inputTrainModelName ? inputTrainModelName.value.trim() : "";
            if (!src) {
                showToast("Selecione um arquivo de gravação vocal para o dataset!");
                return;
            }
            if (!modelName) {
                showToast("Informe um nome para o novo modelo de voz!");
                return;
            }

            btnStartTraining.disabled = true;
            btnStartTrainText.textContent = "Iniciando Treinamento...";
            if (trainProgressCard) trainProgressCard.classList.remove("hidden");
            if (trainProgressBar) trainProgressBar.style.width = "5%";
            if (trainProgressPercent) trainProgressPercent.textContent = "5%";
            if (trainProgressMsg) trainProgressMsg.textContent = "Preparando workspace acústico...";

            try {
                const payload = {
                    audio_source: src,
                    model_name: modelName,
                    epochs: parseInt(sliderTrainEpochs.value),
                    sample_rate: selTrainSampleRate ? selTrainSampleRate.value : "40k",
                    f0_method: "rmvpe",
                    denoise: chkTrainDenoise ? chkTrainDenoise.checked : true
                };

                const resp = await fetch("/api/audio/train-voice", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();

                if (resp.ok && data.success) {
                    const taskId = data.task_id;
                    showToast(`Treinamento de '${modelName}' iniciado em segundo plano!`);

                    if (trainPollingInterval) clearInterval(trainPollingInterval);
                    trainPollingInterval = setInterval(async () => {
                        try {
                            const statusResp = await fetch(`/api/audio/train-status/${taskId}`);
                            const statusData = await statusResp.json();
                            if (statusData) {
                                const pct = statusData.percent || 0;
                                if (trainProgressBar) trainProgressBar.style.width = `${pct}%`;
                                if (trainProgressPercent) trainProgressPercent.textContent = `${pct}%`;
                                if (trainProgressMsg) trainProgressMsg.textContent = statusData.message || "";

                                if (statusData.status === "finished") {
                                    clearInterval(trainPollingInterval);
                                    btnStartTraining.disabled = false;
                                    btnStartTrainText.textContent = "Iniciar Treinamento da Nova Voz";
                                    showToast(`Voz '${modelName}' treinada e compilada com sucesso!`);
                                    await loadAudioModels();
                                    if (selRvcModel) selRvcModel.value = modelName;
                                } else if (statusData.status === "error") {
                                    clearInterval(trainPollingInterval);
                                    btnStartTraining.disabled = false;
                                    btnStartTrainText.textContent = "Iniciar Treinamento da Nova Voz";
                                    showToast("Erro no treinamento: " + (statusData.error || "Falha"));
                                }
                            }
                        } catch (e) {
                            clearInterval(trainPollingInterval);
                        }
                    }, 1200);
                } else {
                    showToast("Erro ao iniciar treino: " + (data.detail || "Falha"));
                    btnStartTraining.disabled = false;
                    btnStartTrainText.textContent = "Iniciar Treinamento da Nova Voz";
                }
            } catch (e) {
                showToast("Erro ao conectar com o orquestrador de treinamento.");
                btnStartTraining.disabled = false;
                btnStartTrainText.textContent = "Iniciar Treinamento da Nova Voz";
            }
        });
    }

    // Inicialização do Estúdio de Voz
    loadAudioEngineStatus();
    loadAudioModels();
});
