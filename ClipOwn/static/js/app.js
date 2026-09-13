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
            const response = await fetch(`/api/fetch-info?url=${encodeURIComponent(url)}`);
            const mediaData = await response.json();

            if (!response.ok || !mediaData.success) {
                throw new Error(mediaData.message || 'Failed to extract video.');
            }

            renderMediaResult(mediaData);
            showToast('Instagram media retrieved successfully!', 'success');
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
        currentMedia = null;
        document.getElementById('downloader').scrollIntoView({ behavior: 'smooth' });
    }

    closeResultBtn.addEventListener('click', resetResult);
    downloadAnotherBtn.addEventListener('click', resetResult);

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
});
