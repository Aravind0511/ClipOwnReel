/**
 * ClipOwn - Modern Instagram Downloader Client Application
 * Phase 2: Live Extractor Integration, Streaming Downloads & Settings Modal
 */

document.addEventListener('DOMContentLoaded', () => {
    // --------------------------------------------------------------------------
    // Initialize Icons & DOM Elements
    // --------------------------------------------------------------------------
    if (window.lucide) {
        window.lucide.createIcons();
    }

    const videoUrlInput = document.getElementById('videoUrlInput');
    const pasteBtn = document.getElementById('pasteBtn');
    const clearBtn = document.getElementById('clearBtn');
    const fetchBtn = document.getElementById('fetchBtn');
    const sampleLinkBtn = document.getElementById('sampleLinkBtn');

    const loadingState = document.getElementById('loadingState');
    const resultState = document.getElementById('resultState');
    const authNoticeBanner = document.getElementById('authNoticeBanner');
    const openSettingsLink = document.getElementById('openSettingsLink');
    const closeResultBtn = document.getElementById('closeResultBtn');
    const downloadAnotherBtn = document.getElementById('downloadAnotherBtn');
    const copyDirectLinkBtn = document.getElementById('copyDirectLinkBtn');

    // Result Card Elements
    const previewThumbnail = document.getElementById('previewThumbnail');
    const previewDuration = document.getElementById('previewDuration');
    const creatorAvatar = document.getElementById('creatorAvatar');
    const creatorName = document.getElementById('creatorName');
    const videoCaption = document.getElementById('videoCaption');
    const specFormat = document.getElementById('specFormat');
    const specResolution = document.getElementById('specResolution');
    const specSize = document.getElementById('specSize');

    const btnDownloadHD = document.getElementById('btnDownloadHD');
    const btnDownloadSD = document.getElementById('btnDownloadSD');
    const btnDownloadAudio = document.getElementById('btnDownloadAudio');

    // Settings Modal Elements
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeSettingsBtn = document.getElementById('closeSettingsBtn');
    const cancelSettingsBtn = document.getElementById('cancelSettingsBtn');
    const saveCookieBtn = document.getElementById('saveCookieBtn');
    const clearCookieBtn = document.getElementById('clearCookieBtn');
    const cookieInput = document.getElementById('cookieInput');

    // Privacy & Terms Modal Elements
    const privacyTermsModal = document.getElementById('privacyTermsModal');
    const closePolicyBtn = document.getElementById('closePolicyBtn');
    const agreePolicyBtn = document.getElementById('agreePolicyBtn');
    const tabPrivacyBtn = document.getElementById('tabPrivacyBtn');
    const tabTermsBtn = document.getElementById('tabTermsBtn');
    const privacyTabContent = document.getElementById('privacyTabContent');
    const termsTabContent = document.getElementById('termsTabContent');
    const openPrivacyBtn = document.getElementById('openPrivacyBtn');
    const openTermsBtn = document.getElementById('openTermsBtn');
    const legalPrivacyBtn = document.getElementById('legalPrivacyBtn');
    const legalTermsBtn = document.getElementById('legalTermsBtn');

    // Video Player & Trimmer Elements
    const previewVideo = document.getElementById('previewVideo');
    const playOverlayBtn = document.getElementById('playOverlayBtn');
    const trimToolSection = document.getElementById('trimToolSection');
    const toggleTrimBtn = document.getElementById('toggleTrimBtn');
    const trimControlsArea = document.getElementById('trimControlsArea');
    const trimToggleLabel = document.getElementById('trimToggleLabel');
    const trimChevronIcon = document.getElementById('trimChevronIcon');
    const trimStartVal = document.getElementById('trimStartVal');
    const trimEndVal = document.getElementById('trimEndVal');
    const trimDurationVal = document.getElementById('trimDurationVal');
    const trimStartRange = document.getElementById('trimStartRange');
    const trimEndRange = document.getElementById('trimEndRange');
    const timelineHighlight = document.getElementById('timelineHighlight');
    const previewSegmentBtn = document.getElementById('previewSegmentBtn');
    const previewSegmentIcon = document.getElementById('previewSegmentIcon');
    const previewSegmentText = document.getElementById('previewSegmentText');
    const btnDownloadTrimmedVideo = document.getElementById('btnDownloadTrimmedVideo');
    const btnDownloadTrimmedAudio = document.getElementById('btnDownloadTrimmedAudio');
    const trimVideoSubtext = document.getElementById('trimVideoSubtext');
    const trimAudioSubtext = document.getElementById('trimAudioSubtext');
    const trimVideoLoader = document.getElementById('trimVideoLoader');
    const trimAudioLoader = document.getElementById('trimAudioLoader');
    const presetChips = document.querySelectorAll('.preset-chip');

    // Current fetched media object
    let currentMedia = null;

    // Load saved cookie preference
    const savedCookie = localStorage.getItem('clipown_ig_cookie');
    if (savedCookie && cookieInput) {
        cookieInput.value = savedCookie;
    }

    // --------------------------------------------------------------------------
    // Toast Notification System
    // --------------------------------------------------------------------------
    function showToast(message, type = 'info', duration = 3500) {
        const container = document.getElementById('toastContainer');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        let iconName = 'info';
        if (type === 'success') iconName = 'check-circle';
        if (type === 'error') iconName = 'alert-circle';

        toast.innerHTML = `
            <i data-lucide="${iconName}"></i>
            <span>${message}</span>
        `;

        container.appendChild(toast);
        if (window.lucide) window.lucide.createIcons({ root: toast });

        setTimeout(() => {
            toast.classList.add('toast-hide');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, duration);
    }

    // --------------------------------------------------------------------------
    // Clipboard & Input Management
    // --------------------------------------------------------------------------
    function toggleClearButton() {
        if (videoUrlInput.value.trim().length > 0) {
            clearBtn.classList.remove('hidden');
        } else {
            clearBtn.classList.add('hidden');
        }
    }

    videoUrlInput.addEventListener('input', toggleClearButton);

    clearBtn.addEventListener('click', () => {
        videoUrlInput.value = '';
        toggleClearButton();
        videoUrlInput.focus();
    });

    pasteBtn.addEventListener('click', async () => {
        try {
            if (!navigator.clipboard || !navigator.clipboard.readText) {
                showToast('Clipboard API not supported in this browser. Please use Ctrl+V', 'error');
                videoUrlInput.focus();
                return;
            }

            const text = await navigator.clipboard.readText();
            if (text && text.trim()) {
                videoUrlInput.value = text.trim();
                toggleClearButton();
                showToast('Link pasted from clipboard!', 'success');
                if (isInstagramUrl(videoUrlInput.value)) {
                    triggerMediaFetch(videoUrlInput.value);
                }
            } else {
                showToast('Clipboard is empty', 'info');
            }
        } catch (err) {
            console.warn('Clipboard read error:', err);
            showToast('Unable to read clipboard. Please paste manually (Ctrl+V).', 'info');
            videoUrlInput.focus();
        }
    });

    // --------------------------------------------------------------------------
    // Sample Link Demo Feature
    // --------------------------------------------------------------------------
    sampleLinkBtn.addEventListener('click', () => {
        const sampleUrl = 'https://www.instagram.com/reel/Dcp3JkzJTA6/';
        videoUrlInput.value = sampleUrl;
        toggleClearButton();
        showToast('Sample Reel link loaded!', 'info');
        triggerMediaFetch(sampleUrl);
    });

    // --------------------------------------------------------------------------
    // Instagram URL Validation
    // --------------------------------------------------------------------------
    function isInstagramUrl(url) {
        if (!url) return false;
        const igRegex = /(?:https?:\/\/)?(?:www\.)?(?:instagram\.com)\/(?:p|reel|tv|stories)\/([A-Za-z0-9_-]+)/i;
        return igRegex.test(url) || url.includes('instagram.com');
    }

    // --------------------------------------------------------------------------
    // Fetch & Preview Logic
    // --------------------------------------------------------------------------
    fetchBtn.addEventListener('click', () => {
        const url = videoUrlInput.value.trim();
        if (!url) {
            showToast('Please paste an Instagram link first', 'error');
            videoUrlInput.focus();
            return;
        }

        if (!isInstagramUrl(url)) {
            showToast('Please enter a valid Instagram Reel, Video, or Post URL', 'error');
            return;
        }

        triggerMediaFetch(url);
    });

    videoUrlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            fetchBtn.click();
        }
    });

    async function triggerMediaFetch(url) {
        // UI State: Loading
        setLoadingState(true);
        resultState.classList.add('hidden');
        loadingState.classList.remove('hidden');

        // Smooth scroll to loading section
        loadingState.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        try {
            const apiBase = window.location.hostname.includes('github.io') 
                ? (localStorage.getItem('clipown_backend_url') || '') 
                : '';
            const apiUrl = apiBase 
                ? `${apiBase.replace(/\/$/, '')}/api/fetch-info?url=${encodeURIComponent(url)}` 
                : `/api/fetch-info?url=${encodeURIComponent(url)}`;
            
            let mediaData = null;
            try {
                const response = await fetch(apiUrl);
                if (response.ok) {
                    mediaData = await response.json();
                }
            } catch (netErr) {
                console.warn('Backend fetch failed, checking demo fallback:', netErr);
            }

            if (!mediaData || !mediaData.success) {
                // If running on GitHub Pages (static host), fallback to interactive demo reel
                if (window.location.hostname.includes('github.io')) {
                    mediaData = {
                        success: true,
                        is_mock: true,
                        shortcode: 'Dcp3JkzJTA6',
                        title: 'ClipOwn Demo Reel • Instagram Video Downloader & Trimmer',
                        author: 'aravind_k0504',
                        author_avatar: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80',
                        thumbnail: 'https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800&auto=format&fit=crop&q=80',
                        duration: '0:30',
                        duration_seconds: 30.0,
                        format: 'MP4 (H.264)',
                        resolution: '1080 x 1920',
                        size: '~ 18.5 MB',
                        download_url_hd: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                        download_url_sd: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                        download_url_audio: 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4',
                        direct_link: url,
                        source: 'demo_preview'
                    };
                    showToast('GitHub Pages Demo Mode: Live preview active! Run locally with python app.py or deploy to Render for full Instagram downloads.', 'info', 6000);
                } else {
                    throw new Error((mediaData && mediaData.message) || 'Failed to extract video.');
                }
            }

            renderMediaResult(mediaData);
            if (!mediaData.is_mock) {
                showToast('Instagram media retrieved successfully!', 'success');
            }
        } catch (err) {
            console.error('Error fetching media:', err);
            showToast(err.message || 'Failed to retrieve media. Please check link.', 'error');
        } finally {
            setLoadingState(false);
            loadingState.classList.add('hidden');
        }
    }

    function setLoadingState(isLoading) {
        const btnText = fetchBtn.querySelector('.btn-text');
        const btnIcon = fetchBtn.querySelector('.btn-icon-right');
        const btnLoader = fetchBtn.querySelector('.btn-loader');

        if (isLoading) {
            fetchBtn.disabled = true;
            btnText.classList.add('hidden');
            btnIcon.classList.add('hidden');
            btnLoader.classList.remove('hidden');
        } else {
            fetchBtn.disabled = false;
            btnText.classList.remove('hidden');
            btnIcon.classList.remove('hidden');
            btnLoader.classList.add('hidden');
        }
    }

    function renderMediaResult(data) {
        currentMedia = data;

        previewThumbnail.src = data.thumbnail;
        previewDuration.textContent = data.duration || '0:30';
        creatorAvatar.src = data.author_avatar;
        creatorName.textContent = `@${data.author || 'instagram_user'}`;
        videoCaption.textContent = data.title || 'Instagram Video';
        specFormat.textContent = data.format || 'MP4';
        specResolution.textContent = data.resolution || '1080 x 1920';
        specSize.textContent = data.size || '18.5 MB';

        // Toggle authentication notice banner
        if (data.auth_required && authNoticeBanner) {
            authNoticeBanner.classList.remove('hidden');
        } else if (authNoticeBanner) {
            authNoticeBanner.classList.add('hidden');
        }

        // Initialize Trimmer & Video Preview
        initTrimmer(data);

        resultState.classList.remove('hidden');
        if (window.lucide) window.lucide.createIcons({ root: resultState });

        resultState.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // --------------------------------------------------------------------------
    // Download Action Handlers (Stream via /api/download)
    // --------------------------------------------------------------------------
    btnDownloadHD.addEventListener('click', () => {
        if (!currentMedia) return;
        showToast('Initiating 1080p HD Video download...', 'success');
        const downloadUrl = `/api/download?url=${encodeURIComponent(currentMedia.download_url_hd || currentMedia.direct_link)}&filename=clipown_1080p_${currentMedia.shortcode || 'video'}.mp4`;
        triggerBrowserDownload(downloadUrl);
    });

    btnDownloadSD.addEventListener('click', () => {
        if (!currentMedia) return;
        showToast('Initiating 720p Video download...', 'success');
        const downloadUrl = `/api/download?url=${encodeURIComponent(currentMedia.download_url_sd || currentMedia.direct_link)}&filename=clipown_720p_${currentMedia.shortcode || 'video'}.mp4`;
        triggerBrowserDownload(downloadUrl);
    });

    btnDownloadAudio.addEventListener('click', () => {
        if (!currentMedia) return;
        showToast('Initiating MP3 Audio download...', 'success');
        const downloadUrl = `/api/download?url=${encodeURIComponent(currentMedia.download_url_audio || currentMedia.direct_link)}&filename=clipown_audio_${currentMedia.shortcode || 'audio'}.mp3`;
        triggerBrowserDownload(downloadUrl);
    });

    function triggerBrowserDownload(url) {
        const a = document.createElement('a');
        a.href = url;
        a.download = '';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    copyDirectLinkBtn.addEventListener('click', async () => {
        if (!currentMedia || !currentMedia.direct_link) return;
        try {
            await navigator.clipboard.writeText(currentMedia.direct_link);
            showToast('Instagram URL copied to clipboard!', 'success');
        } catch (e) {
            showToast('Failed to copy link', 'error');
        }
    });

    function resetResult() {
        resultState.classList.add('hidden');
        videoUrlInput.value = '';
        toggleClearButton();
        cleanupTrimmer();
        currentMedia = null;
        document.getElementById('downloader').scrollIntoView({ behavior: 'smooth' });
    }

    closeResultBtn.addEventListener('click', resetResult);
    downloadAnotherBtn.addEventListener('click', resetResult);

    // --------------------------------------------------------------------------
    // Video & Audio Trimmer Controller
    // --------------------------------------------------------------------------
    function formatSeconds(sec) {
        if (isNaN(sec) || sec < 0) return '00:00';
        const total = Math.floor(sec);
        const m = Math.floor(total / 60);
        const s = total % 60;
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }

    function initTrimmer(data) {
        if (!trimToolSection) return;
        const duration = data.duration_seconds || 30.0;

        if (trimStartRange && trimEndRange) {
            trimStartRange.min = '0';
            trimStartRange.max = duration.toString();
            trimStartRange.step = '0.5';
            trimStartRange.value = '0';

            trimEndRange.min = '0';
            trimEndRange.max = duration.toString();
            trimEndRange.step = '0.5';
            trimEndRange.value = duration.toString();
        }

        // Reset preset chips
        presetChips.forEach(chip => {
            if (chip.dataset.preset === 'full') {
                chip.classList.add('active');
            } else {
                chip.classList.remove('active');
            }
        });

        updateTrimUI();

        // Setup preview video stream
        if (previewVideo) {
            const streamSrc = `/api/stream?url=${encodeURIComponent(data.download_url_hd || data.download_url_sd || data.direct_link)}`;
            previewVideo.src = streamSrc;
            previewVideo.load();
            previewVideo.classList.add('hidden');
        }
        if (previewThumbnail) previewThumbnail.classList.remove('hidden');
        if (playOverlayBtn) playOverlayBtn.classList.remove('hidden');

        resetPreviewSegmentBtn();
    }

    function updateTrimUI() {
        if (!trimStartRange || !trimEndRange) return;
        let start = parseFloat(trimStartRange.value) || 0;
        let end = parseFloat(trimEndRange.value) || 0;
        const maxVal = parseFloat(trimStartRange.max) || 30;

        if (start >= end - 0.5) {
            start = Math.max(0, end - 0.5);
            trimStartRange.value = start.toString();
        }

        const duration = Math.max(0.5, end - start);

        if (trimStartVal) trimStartVal.textContent = formatSeconds(start);
        if (trimEndVal) trimEndVal.textContent = formatSeconds(end);
        if (trimDurationVal) trimDurationVal.textContent = formatSeconds(duration);

        if (timelineHighlight) {
            const leftPct = (start / maxVal) * 100;
            const widthPct = (duration / maxVal) * 100;
            timelineHighlight.style.left = `${leftPct}%`;
            timelineHighlight.style.width = `${widthPct}%`;
        }

        const rangeStr = `${formatSeconds(start)} - ${formatSeconds(end)} (${Math.round(duration)}s)`;
        if (trimVideoSubtext) {
            trimVideoSubtext.innerHTML = `MP4 with Audio • <span class="range-preview-text">${rangeStr}</span>`;
        }
        if (trimAudioSubtext) {
            trimAudioSubtext.innerHTML = `Audio Only • <span class="range-preview-text">${rangeStr}</span>`;
        }
    }

    function cleanupTrimmer() {
        if (previewVideo) {
            previewVideo.pause();
            previewVideo.removeAttribute('src');
            previewVideo.load();
            previewVideo.classList.add('hidden');
        }
        if (previewThumbnail) previewThumbnail.classList.remove('hidden');
        if (playOverlayBtn) playOverlayBtn.classList.remove('hidden');
        resetPreviewSegmentBtn();
    }

    function clearActivePresets() {
        presetChips.forEach(c => c.classList.remove('active'));
    }

    function syncVideoTime(sec) {
        if (previewVideo && isFinite(sec)) {
            if (!previewVideo.paused) {
                previewVideo.pause();
                resetPreviewSegmentBtn();
            }
            previewVideo.currentTime = sec;
        }
    }

    // Toggle Trimmer Section
    if (toggleTrimBtn) {
        toggleTrimBtn.addEventListener('click', () => {
            const isCollapsed = trimControlsArea.classList.toggle('collapsed');
            if (trimToggleLabel) {
                trimToggleLabel.textContent = isCollapsed ? 'Expand' : 'Collapse';
            }
            if (trimChevronIcon) {
                trimChevronIcon.setAttribute('data-lucide', isCollapsed ? 'chevron-down' : 'chevron-up');
                if (window.lucide) window.lucide.createIcons({ root: toggleTrimBtn });
            }
        });
    }

    // Sliders input handling
    if (trimStartRange) {
        trimStartRange.addEventListener('input', () => {
            const start = parseFloat(trimStartRange.value);
            const end = parseFloat(trimEndRange.value);
            if (start >= end - 0.5) {
                trimStartRange.value = (end - 0.5).toString();
            }
            clearActivePresets();
            updateTrimUI();
            syncVideoTime(parseFloat(trimStartRange.value));
        });
    }

    if (trimEndRange) {
        trimEndRange.addEventListener('input', () => {
            const start = parseFloat(trimStartRange.value);
            const end = parseFloat(trimEndRange.value);
            if (end <= start + 0.5) {
                trimEndRange.value = (start + 0.5).toString();
            }
            clearActivePresets();
            updateTrimUI();
            syncVideoTime(parseFloat(trimEndRange.value));
        });
    }

    // Presets
    presetChips.forEach(chip => {
        chip.addEventListener('click', () => {
            if (!currentMedia) return;
            const total = currentMedia.duration_seconds || 30.0;
            const preset = chip.dataset.preset;

            clearActivePresets();
            chip.classList.add('active');

            if (preset === 'full') {
                trimStartRange.value = '0';
                trimEndRange.value = total.toString();
            } else if (preset === 'first15') {
                trimStartRange.value = '0';
                trimEndRange.value = Math.min(15, total).toString();
            } else if (preset === 'first30') {
                trimStartRange.value = '0';
                trimEndRange.value = Math.min(30, total).toString();
            } else if (preset === 'last15') {
                trimStartRange.value = Math.max(0, total - 15).toString();
                trimEndRange.value = total.toString();
            }
            updateTrimUI();
            syncVideoTime(parseFloat(trimStartRange.value));
        });
    });

    // Preview clip playback
    let isAuditioning = false;

    function resetPreviewSegmentBtn() {
        isAuditioning = false;
        if (previewSegmentText) previewSegmentText.textContent = 'Play Clip';
        if (previewSegmentIcon) {
            previewSegmentIcon.setAttribute('data-lucide', 'play');
            if (window.lucide && previewSegmentBtn) window.lucide.createIcons({ root: previewSegmentBtn });
        }
    }

    function startClipAudition() {
        if (!previewVideo) return;
        const start = parseFloat(trimStartRange.value) || 0;

        previewVideo.classList.remove('hidden');
        if (previewThumbnail) previewThumbnail.classList.add('hidden');
        if (playOverlayBtn) playOverlayBtn.classList.add('hidden');

        previewVideo.currentTime = start;
        previewVideo.play().then(() => {
            isAuditioning = true;
            if (previewSegmentText) previewSegmentText.textContent = 'Pause Clip';
            if (previewSegmentIcon) {
                previewSegmentIcon.setAttribute('data-lucide', 'pause');
                if (window.lucide && previewSegmentBtn) window.lucide.createIcons({ root: previewSegmentBtn });
            }
        }).catch(err => {
            console.warn('Playback error:', err);
        });
    }

    function stopClipAudition() {
        if (previewVideo) previewVideo.pause();
        resetPreviewSegmentBtn();
    }

    if (previewSegmentBtn) {
        previewSegmentBtn.addEventListener('click', () => {
            if (isAuditioning && previewVideo && !previewVideo.paused) {
                stopClipAudition();
            } else {
                startClipAudition();
            }
        });
    }

    if (playOverlayBtn) {
        playOverlayBtn.addEventListener('click', () => {
            startClipAudition();
        });
    }

    if (previewVideo) {
        previewVideo.addEventListener('timeupdate', () => {
            if (isAuditioning) {
                const end = parseFloat(trimEndRange.value) || 0;
                if (previewVideo.currentTime >= end) {
                    previewVideo.pause();
                    previewVideo.currentTime = parseFloat(trimStartRange.value) || 0;
                    resetPreviewSegmentBtn();
                }
            }
        });

        previewVideo.addEventListener('pause', () => {
            if (isAuditioning && previewVideo.currentTime < parseFloat(trimEndRange.value)) {
                resetPreviewSegmentBtn();
            }
        });
    }

    // Trimmed Downloads
    async function executeTrimDownload(mediaType) {
        if (!currentMedia) return;

        const start = parseFloat(trimStartRange.value) || 0;
        const end = parseFloat(trimEndRange.value) || 0;
        const isVideo = (mediaType === 'video');
        const sourceUrl = isVideo 
            ? (currentMedia.download_url_hd || currentMedia.direct_link) 
            : (currentMedia.download_url_audio || currentMedia.download_url_hd || currentMedia.direct_link);

        const btn = isVideo ? btnDownloadTrimmedVideo : btnDownloadTrimmedAudio;
        const loader = isVideo ? trimVideoLoader : trimAudioLoader;
        const ext = isVideo ? 'mp4' : 'mp3';
        const label = isVideo ? 'Trimmed Video HD (with Audio)' : 'Trimmed Audio MP3';
        const filename = `clipown_trim_${Math.round(start)}s_to_${Math.round(end)}s_${currentMedia.shortcode || 'clip'}.${ext}`;

        if (btn) btn.disabled = true;
        if (loader) loader.classList.remove('hidden');
        showToast(`Preparing ${label}... Cutting with synchronized sound!`, 'info', 4000);

        const trimDownloadUrl = `/api/trim-download?url=${encodeURIComponent(sourceUrl)}&start=${start}&end=${end}&media_type=${mediaType}&filename=${encodeURIComponent(filename)}`;

        try {
            triggerBrowserDownload(trimDownloadUrl);
            setTimeout(() => {
                showToast(`${label} download started!`, 'success');
                if (btn) btn.disabled = false;
                if (loader) loader.classList.add('hidden');
            }, 2000);
        } catch (err) {
            console.error(err);
            showToast(`Failed to download ${label}`, 'error');
            if (btn) btn.disabled = false;
            if (loader) loader.classList.add('hidden');
        }
    }

    if (btnDownloadTrimmedVideo) {
        btnDownloadTrimmedVideo.addEventListener('click', () => executeTrimDownload('video'));
    }

    if (btnDownloadTrimmedAudio) {
        btnDownloadTrimmedAudio.addEventListener('click', () => executeTrimDownload('audio'));
    }

    // --------------------------------------------------------------------------
    // Settings & Cookie Modal Handlers
    // --------------------------------------------------------------------------
    function openModal() {
        if (settingsModal) {
            settingsModal.classList.remove('hidden');
            if (window.lucide) window.lucide.createIcons({ root: settingsModal });
        }
    }

    function closeModal() {
        if (settingsModal) {
            settingsModal.classList.add('hidden');
        }
    }

    if (settingsBtn) settingsBtn.addEventListener('click', openModal);
    if (openSettingsLink) openSettingsLink.addEventListener('click', openModal);
    if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeModal);
    if (cancelSettingsBtn) cancelSettingsBtn.addEventListener('click', closeModal);

    if (settingsModal) {
        settingsModal.addEventListener('click', (e) => {
            if (e.target === settingsModal) {
                closeModal();
            }
        });
    }

    if (saveCookieBtn) {
        saveCookieBtn.addEventListener('click', async () => {
            const cookieVal = cookieInput ? cookieInput.value.trim() : '';
            try {
                const res = await fetch('/api/settings/cookie', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cookie: cookieVal })
                });
                const result = await res.json();
                if (result.success) {
                    localStorage.setItem('clipown_ig_cookie', cookieVal);
                    showToast('Cookie saved! Full extraction active.', 'success');
                    closeModal();
                } else {
                    showToast('Failed to save cookie: ' + result.message, 'error');
                }
            } catch (err) {
                showToast('Error saving cookie', 'error');
            }
        });
    }

    if (clearCookieBtn) {
        clearCookieBtn.addEventListener('click', async () => {
            if (cookieInput) cookieInput.value = '';
            localStorage.removeItem('clipown_ig_cookie');
            await fetch('/api/settings/cookie', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cookie: '' })
            });
            showToast('Cookie cleared', 'info');
        });
    }

    // --------------------------------------------------------------------------
    // FAQ Accordion Toggle
    // --------------------------------------------------------------------------
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach(item => {
        const questionBtn = item.querySelector('.faq-question');
        questionBtn.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            faqItems.forEach(otherItem => {
                if (otherItem !== item) {
                    otherItem.classList.remove('active');
                }
            });
            if (isActive) {
                item.classList.remove('active');
            } else {
                item.classList.add('active');
            }
        });
    });

    // --------------------------------------------------------------------------
    // Privacy Policy & Terms Modal Handlers
    // --------------------------------------------------------------------------
    function switchPolicyTab(tab) {
        if (tab === 'privacy') {
            tabPrivacyBtn?.classList.add('active');
            tabTermsBtn?.classList.remove('active');
            privacyTabContent?.classList.remove('hidden');
            termsTabContent?.classList.add('hidden');
        } else {
            tabTermsBtn?.classList.add('active');
            tabPrivacyBtn?.classList.remove('active');
            termsTabContent?.classList.remove('hidden');
            privacyTabContent?.classList.add('hidden');
        }
        if (window.lucide && privacyTermsModal) {
            window.lucide.createIcons({ root: privacyTermsModal });
        }
    }

    function openPolicyModal(tab = 'privacy') {
        if (privacyTermsModal) {
            switchPolicyTab(tab);
            privacyTermsModal.classList.remove('hidden');
            if (window.lucide) window.lucide.createIcons({ root: privacyTermsModal });
        }
    }

    function closePolicyModal() {
        if (privacyTermsModal) {
            privacyTermsModal.classList.add('hidden');
        }
    }

    // Modal triggers from footer
    if (openPrivacyBtn) openPrivacyBtn.addEventListener('click', () => openPolicyModal('privacy'));
    if (legalPrivacyBtn) legalPrivacyBtn.addEventListener('click', () => openPolicyModal('privacy'));
    if (openTermsBtn) openTermsBtn.addEventListener('click', () => openPolicyModal('terms'));
    if (legalTermsBtn) legalTermsBtn.addEventListener('click', () => openPolicyModal('terms'));

    // Tab buttons inside modal
    if (tabPrivacyBtn) tabPrivacyBtn.addEventListener('click', () => switchPolicyTab('privacy'));
    if (tabTermsBtn) tabTermsBtn.addEventListener('click', () => switchPolicyTab('terms'));

    // Close actions
    if (closePolicyBtn) closePolicyBtn.addEventListener('click', closePolicyModal);
    if (agreePolicyBtn) agreePolicyBtn.addEventListener('click', () => {
        closePolicyModal();
        showToast('Privacy & Terms accepted', 'info');
    });

    if (privacyTermsModal) {
        privacyTermsModal.addEventListener('click', (e) => {
            if (e.target === privacyTermsModal) {
                closePolicyModal();
            }
        });
    }

    // Escape key closes open modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModal();
            closePolicyModal();
        }
    });
});
