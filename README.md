# ClipOwn - Modern Instagram Video & Reel Downloader ⚡ (v1.0.0 Final Release)

A high-performance, modern web application designed to download Instagram Reels, Videos, and Posts in crystal-clear High Definition. Built with a sleek dark glassmorphism interface, real-time clipboard integration, server-accelerated video streaming, precision clip trimmer, and zero third-party ads.

🌐 **Live Production Application**: [https://instagram-reels-downloader-project.onrender.com](https://instagram-reels-downloader-project.onrender.com)

---

## 🌟 Key Features

- **Modern Glassmorphic UI**: Cosmic dark theme (`#090a11`), Instagram radial gradient glow, Lucide icons, and smooth micro-interactions.
- **1-Click Clipboard Paste**: Instant URL insertion using the modern Web Clipboard API (`navigator.clipboard`).
- **Creator Voice + BGM Preservation**: Prioritizes Instagram's master rendered audio stream so spoken voice and synchronized background music are fully preserved.
- **Precision Clip Trimmer**: Interactive dual-range slider with 0.5s precision, preset buttons (Full, First 15s, First 30s, Last 15s), live clip playback auditioning, and trimmed MP4/MP3 downloads.
- **Full HD Video & Audio Muxing**: Automatic FFmpeg background muxing for 1080p/720p DASH video streams and high-bitrate (192kbps) MP3 extraction.
- **Same-Origin Avatar Proxy**: Built-in `/api/proxy-image` route to load creator profile photos cleanly without CORS or referrer restrictions, backed by gradient SVG fallbacks.
- **Direct Attachment Streaming**: Backend streams files directly with `Content-Disposition: attachment` headers, bypassing third-party redirection ads.
- **Instagram Authentication Support**: Optional session cookie support (`INSTAGRAM_COOKIE` / Settings Modal) to reliably unlock private or age-restricted Reels.
- **Interactive Sample Mode**: Includes a "Try sample Reel" button to immediately test the download pipeline.
- **Fully Responsive**: Seamlessly optimized for desktop, tablet, iOS Safari, and Android.

---

## 📁 Project Structure

```
ClipOwn/
├── app.py              # FastAPI server with media streaming & settings endpoints
├── extractor.py        # Multi-engine media extractor (yt-dlp + fallback)
├── requirements.txt    # Python dependencies (fastapi, uvicorn, yt-dlp, requests)
├── static/
│   ├── css/
│   │   └── styles.css  # Modern glassmorphism design tokens & responsive CSS
│   └── js/
│       └── app.js      # Client application logic, Clipboard API & UI states
├── templates/
│   └── index.html      # Semantic HTML5 single-page application
└── README.md           # Project documentation
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
Make sure Python 3.10+ is installed:
```bash
pip install -r requirements.txt
```

### 2. Run the Application Server
```bash
python app.py
```

### 3. Open in Browser
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 👨‍💻 Developer & Contact

- **Lead Developer**: **Aravind kumar k**
- **Location**: Tiruppur, Tamil Nadu, India 📍
- **Email Support**: [aravindvjm2004@gmail.com](mailto:aravindvjm2004@gmail.com) ✉️
- **Contact Number**: [+91 8807006909](tel:8807006909) 📞
- **GitHub**: [github.com/Aravind0511](https://github.com/Aravind0511) 🐙
- **LinkedIn**: [linkedin.com/in/aravind-k0504](https://www.linkedin.com/in/aravind-k0504/) 💼

---

## ⚙️ Optional: Instagram Session Cookie Configuration

Instagram frequently limits anonymous public requests. If an Instagram post requires authentication:
1. Open the web app and click **Settings** (top right) or the notice banner.
2. In your browser, log in to [instagram.com](https://www.instagram.com).
3. Press `F12` > **Application** > **Cookies** > copy the value of `sessionid`.
4. Paste the value in ClipOwn's Settings Modal and click **Save Settings**.
5. All restricted reels and posts can now be downloaded with full original audio and video streams!
