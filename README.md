# ClipOwn - Modern Instagram Video & Reel Downloader ⚡

A high-performance, modern web application designed to download Instagram Reels, Videos, and Posts in crystal-clear High Definition. Built with a sleek dark glassmorphism interface, real-time clipboard integration, server-accelerated video streaming, and zero third-party ads.

---

## 🌟 Key Features

- **Modern Glassmorphic UI**: Cosmic dark theme (`#090a11`), Instagram radial gradient glow, and smooth animations.
- **1-Click Clipboard Paste**: Instant URL insertion using the modern Web Clipboard API (`navigator.clipboard`).
- **Media Preview Card**: Displays creator avatar, username, video caption, duration, format, resolution, and estimated file size.
- **Multiple Download Options**:
  - **1080p Full HD Video** (MP4)
  - **720p HD Video** (MP4)
  - **MP3 Audio Extraction** (Audio-only track)
- **Direct Browser Streaming**: Backend proxy streams files directly with `Content-Disposition: attachment` headers, bypassing CORS and avoiding external redirect ads.
- **Instagram Authentication / Cookie Support**: Includes a built-in Settings Modal to configure an optional Instagram session cookie (`sessionid`) to unlock restricted or rate-limited videos.
- **Interactive Sample Mode**: Includes a "Try sample Reel" button to immediately demo and test the full download pipeline.
- **Responsive Design**: Flawless experience on desktop, tablet, iPhone (iOS Safari), and Android.

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
