"""
ClipOwn - Modern Instagram Video Downloader
Backend Server (FastAPI)
"""

import os
import re
import requests
from fastapi import FastAPI, Query, HTTPException, Request, Response, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from extractor import extract_instagram_media, COOKIE_FILE_PATH, convert_to_netscape_content, get_media_meta
from trimmer import trim_media
from ffmpeg_utils import ensure_ffmpeg, mux_video_audio, extract_mp3_audio, NoAudioStreamError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Ensure FFmpeg is available and in PATH
ensure_ffmpeg()

app = FastAPI(
    title="ClipOwn API",
    description="Modern Instagram Video & Reel Downloader API",
    version="1.0.0"
)

# Enable CORS for all origins (supports GitHub Pages and custom domain deployments)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory or env-based cookie store (supports INSTAGRAM_COOKIE and INSTAGRAM_SESSIONID)
ACTIVE_COOKIE = (os.environ.get("INSTAGRAM_COOKIE", "") or os.environ.get("INSTAGRAM_SESSIONID", "")).strip()
if ACTIVE_COOKIE:
    try:
        netscape_data = convert_to_netscape_content(ACTIVE_COOKIE)
        with open(COOKIE_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(netscape_data)
        print("Loaded authenticated Instagram cookie from environment variable.")
    except Exception as e:
        print(f"Failed to initialize Instagram cookie from environment: {e}")

class CookiePayload(BaseModel):
    cookie: str

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the modern single-page web app with anti-cache headers."""
    index_file = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(index_file):
        index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_file):
        raise HTTPException(status_code=404, detail="Index template not found")
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(
        content=content,
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/api/fetch-info")
async def fetch_info(
    request: Request,
    url: str = Query(..., description="Instagram Reel, Video, or Post URL"),
    cookie: str = Query(None, description="Optional Instagram session cookie")
):
    """
    Fetch media information and available download streams for the given Instagram URL.
    Supports client-provided cookies for persistent authentication across container restarts.
    """
    global ACTIVE_COOKIE
    clean_url = url.strip()
    
    # Check client cookie or header or ACTIVE_COOKIE
    req_cookie = (cookie if isinstance(cookie, str) else None) or request.headers.get("X-IG-Cookie") or ACTIVE_COOKIE
    if req_cookie and isinstance(req_cookie, str) and req_cookie.strip():
        cookie_clean = req_cookie.strip()
        if not ACTIVE_COOKIE or ACTIVE_COOKIE != cookie_clean:
            ACTIVE_COOKIE = cookie_clean
            try:
                netscape_data = convert_to_netscape_content(ACTIVE_COOKIE)
                with open(COOKIE_FILE_PATH, "w", encoding="utf-8") as f:
                    f.write(netscape_data)
            except Exception:
                pass

    # Basic Instagram URL validation
    ig_pattern = r"(?:https?:\/\/)?(?:www\.)?(?:instagram\.com)\/(?:share\/)?(?:p|reels?|tv|stories)\/([A-Za-z0-9_-]+)"
    if not re.search(ig_pattern, clean_url) and "instagram.com" not in clean_url:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Invalid Instagram URL. Please enter a valid Instagram Reel, Video, or Post link."
            }
        )

    # Call extractor
    result = extract_instagram_media(clean_url, cookie_string=req_cookie or ACTIVE_COOKIE)
    return JSONResponse(content=result)

@app.api_route("/api/download", methods=["GET", "HEAD"])
async def download_media(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="Direct media URL to download"),
    filename: str = Query("clipown_video.mp4", description="Output filename"),
    audio_url: str = Query(None, description="Optional separate audio stream URL to mux"),
    media_type: str = Query("video", description="Download format type: video or audio"),
    audio_start: float = Query(0.0, description="Optional audio start offset in seconds"),
    duration: float = Query(None, description="Optional clip duration in seconds"),
    shortcode: str = Query(None, description="Optional Instagram shortcode or identifier to auto-resolve clip metadata")
):
    """
    Stream or transcode video/audio file directly to client with forced attachment header.
    Automatically muxes DASH video + audio streams, and converts audio streams to authentic MP3.
    Enforces exact clip offset and duration boundaries.
    """
    clean_url = url.strip()
    if not clean_url or clean_url == "#":
        raise HTTPException(status_code=400, detail="Invalid media download URL.")

    # Auto-resolve clip duration, offset, and separate audio stream from server registry
    meta = get_media_meta(shortcode) or get_media_meta(clean_url) or {}
    if (audio_start is None or float(audio_start) == 0.0) and meta.get('audio_start_offset'):
        try:
            audio_start = float(meta['audio_start_offset'])
        except (ValueError, TypeError):
            pass

    if (duration is None or float(duration) <= 0.0) and meta.get('duration_seconds'):
        try:
            duration = float(meta['duration_seconds'])
        except (ValueError, TypeError):
            pass

    if (not audio_url or audio_url.lower() in ["none", "null", "undefined"]) and meta.get('separate_audio_url'):
        audio_url = meta['separate_audio_url']

    # 1. Audio Download Request (extract authentic MP3)
    if media_type.lower() == "audio" or filename.lower().endswith(".mp3"):
        target_audio = clean_url
        if (not target_audio or target_audio.lower() in ["none", "null", "undefined", "#"]) and meta.get('download_url_audio'):
            target_audio = meta['download_url_audio']
        if not target_audio or target_audio.lower() in ["none", "null", "undefined", "#"]:
            raise HTTPException(
                status_code=400,
                detail="Instagram restricted the audio stream for this Reel on guest cloud requests. Please add your Instagram session cookie in Settings to download audio."
            )
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not safe_filename.endswith(".mp3"):
            safe_filename += ".mp3"
        try:
            mp3_path = extract_mp3_audio(target_audio, start_time=audio_start, duration=duration)
            background_tasks.add_task(os.remove, mp3_path)
            return FileResponse(
                mp3_path,
                media_type="audio/mpeg",
                filename=safe_filename,
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_filename}"',
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except NoAudioStreamError:
            raise HTTPException(
                status_code=400,
                detail="No audio stream detected in this Instagram Reel. On cloud servers, Instagram restricts audio streams for unauthenticated requests. Please add an Instagram session cookie in Settings to download MP3 audio."
            )
        except Exception as e:
            err_msg = str(e)
            if "does not contain any stream" in err_msg.lower() or "no audio stream" in err_msg.lower():
                raise HTTPException(
                    status_code=400,
                    detail="No audio stream detected in this Reel. Please add your Instagram session cookie in Settings to unlock audio extraction."
                )
            raise HTTPException(status_code=500, detail=f"Failed to generate MP3 audio: {err_msg}")

    # 2. Video Download with separate audio stream (mux DASH video + audio)
    valid_audio = audio_url.strip() if (isinstance(audio_url, str) and audio_url.strip()) else None
    if valid_audio and valid_audio.lower() not in ["none", "null", "undefined", clean_url.lower()]:
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not safe_filename.endswith(".mp4"):
            safe_filename += ".mp4"
        try:
            muxed_path = mux_video_audio(clean_url, valid_audio, audio_start=audio_start, duration=duration)
            background_tasks.add_task(os.remove, muxed_path)
            return FileResponse(
                muxed_path,
                media_type="video/mp4",
                filename=safe_filename,
                headers={
                    "Content-Disposition": f'attachment; filename="{safe_filename}"',
                    "Access-Control-Allow-Origin": "*"
                }
            )
        except Exception:
            # If audio muxing fails, gracefully fall back to direct video stream
            pass

    # 3. Progressive Video or Direct Streaming
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "*/*",
        }
        req = requests.get(clean_url, stream=True, timeout=30, headers=headers)
        
        if req.status_code != 200:
            raise HTTPException(status_code=req.status_code, detail="Media stream provider returned an error.")

        content_type = req.headers.get("Content-Type", "video/mp4")
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not safe_filename.endswith(('.mp4', '.mp3', '.m4a')):
            safe_filename += '.mp4'

        def iterfile():
            for chunk in req.iter_content(chunk_size=1024 * 64):
                if chunk:
                    yield chunk

        resp_headers = {
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Access-Control-Allow-Origin": "*"
        }
        if "Content-Length" in req.headers:
            resp_headers["Content-Length"] = req.headers["Content-Length"]

        return StreamingResponse(
            iterfile(),
            media_type=content_type,
            headers=resp_headers
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stream media: {str(e)}")

@app.get("/api/stream")
async def stream_media_for_preview(
    request: Request,
    url: str = Query(..., description="Direct media URL to stream"),
    audio_url: str = Query(None, description="Optional audio stream URL to mux for synchronized preview sound"),
    audio_start: float = Query(0.0, description="Optional audio start offset in seconds"),
    duration: float = Query(None, description="Optional clip duration in seconds"),
    shortcode: str = Query(None, description="Optional Instagram shortcode or identifier to auto-resolve clip metadata")
):
    """
    Proxy video streams with Range request support for smooth browser video preview & scrubbing.
    If audio_url is provided, automatically muxes video + audio into a synchronized preview MP4
    so the browser HTML5 player and trimmer audition with authentic sound.
    """
    clean_url = url.strip()
    if not clean_url or clean_url == "#":
        raise HTTPException(status_code=400, detail="Invalid media URL.")

    if os.path.exists(clean_url):
        return FileResponse(clean_url, media_type="video/mp4", headers={"Access-Control-Allow-Origin": "*"})

    # Auto-resolve clip duration, offset, and separate audio stream from server registry
    meta = get_media_meta(shortcode) or get_media_meta(clean_url) or {}
    if (audio_start is None or float(audio_start) == 0.0) and meta.get('audio_start_offset'):
        try:
            audio_start = float(meta['audio_start_offset'])
        except (ValueError, TypeError):
            pass

    if (duration is None or float(duration) <= 0.0) and meta.get('duration_seconds'):
        try:
            duration = float(meta['duration_seconds'])
        except (ValueError, TypeError):
            pass

    if (not audio_url or audio_url.lower() in ["none", "null", "undefined"]) and meta.get('separate_audio_url'):
        audio_url = meta['separate_audio_url']

    # Check if audio stream should be muxed for synchronized preview sound
    valid_audio = audio_url.strip() if (isinstance(audio_url, str) and audio_url.strip()) else None
    clean_audio = valid_audio if (valid_audio and valid_audio.lower() not in ["none", "null", "undefined", clean_url.lower()]) else None
    
    if clean_audio:
        import hashlib, shutil, tempfile
        cache_key = hashlib.md5((clean_url + clean_audio + str(audio_start) + str(duration)).encode()).hexdigest()[:16]
        temp_dir = tempfile.gettempdir()
        cached_preview = os.path.join(temp_dir, f"clipown_prev_{cache_key}.mp4")
        
        if os.path.exists(cached_preview) and os.path.getsize(cached_preview) > 1000:
            return FileResponse(cached_preview, media_type="video/mp4", headers={"Access-Control-Allow-Origin": "*"})
            
        try:
            muxed_file = mux_video_audio(clean_url, clean_audio, audio_start=audio_start, duration=duration)
            if os.path.exists(muxed_file) and os.path.getsize(muxed_file) > 1000:
                try:
                    shutil.move(muxed_file, cached_preview)
                except Exception:
                    cached_preview = muxed_file
                return FileResponse(cached_preview, media_type="video/mp4", headers={"Access-Control-Allow-Origin": "*"})
        except Exception as e:
            print(f"Preview mux failed, falling back to direct stream: {e}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    
    range_header = request.headers.get("Range")
    if range_header:
        headers["Range"] = range_header

    try:
        req = requests.get(clean_url, stream=True, timeout=25, headers=headers)
        
        response_headers = {
            "Content-Type": req.headers.get("Content-Type", "video/mp4"),
            "Accept-Ranges": "bytes",
            "Access-Control-Allow-Origin": "*",
        }
        for h in ["Content-Range", "Content-Length"]:
            if h in req.headers:
                response_headers[h] = req.headers[h]

        def iter_stream():
            for chunk in req.iter_content(chunk_size=1024 * 64):
                if chunk:
                    yield chunk

        return StreamingResponse(
            iter_stream(),
            status_code=req.status_code,
            headers=response_headers,
            media_type=response_headers["Content-Type"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")

@app.get("/api/trim-download")
async def trim_download_media(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="Media source URL to trim"),
    start: float = Query(0.0, description="Start timestamp in seconds"),
    end: float = Query(..., description="End timestamp in seconds"),
    media_type: str = Query("video", description="Trim output format: video or audio"),
    filename: str = Query("clipown_trimmed.mp4", description="Output filename"),
    audio_url: str = Query(None, description="Optional separate audio stream URL for DASH streams"),
    audio_start_offset: float = Query(0.0, description="Optional audio start offset in seconds for music tracks"),
    shortcode: str = Query(None, description="Optional Instagram shortcode or identifier to auto-resolve clip metadata")
):
    """
    Trims video or audio using FFmpeg and streams the cut file directly to the client.
    Guarantees synchronized audio + video for videos, or clean MP3 for audio.
    Cleans up temporary file upon completion.
    """
    clean_url = url.strip()
    if not clean_url or clean_url == "#":
        raise HTTPException(status_code=400, detail="Invalid media URL.")

    if start < 0 or end <= start:
        raise HTTPException(status_code=400, detail="Invalid start/end trim timestamps. End must be greater than start.")

    # Auto-resolve clip offset and separate audio stream from server registry
    meta = get_media_meta(shortcode) or get_media_meta(clean_url) or {}
    if (audio_start_offset is None or float(audio_start_offset) == 0.0) and meta.get('audio_start_offset'):
        try:
            audio_start_offset = float(meta['audio_start_offset'])
        except (ValueError, TypeError):
            pass

    if (not audio_url or audio_url.lower() in ["none", "null", "undefined"]) and meta.get('separate_audio_url'):
        audio_url = meta['separate_audio_url']

    valid_audio = audio_url.strip() if (isinstance(audio_url, str) and audio_url.strip()) else None

    try:
        trimmed_file = trim_media(
            source_url=clean_url,
            start_time=start,
            end_time=end,
            media_type=media_type,
            audio_url=valid_audio,
            audio_start_offset=audio_start_offset
        )

        # File cleanup task after streaming
        background_tasks.add_task(os.remove, trimmed_file)

        # Content type & extension
        is_video = (media_type.lower() == "video")
        ext = ".mp4" if is_video else ".mp3"
        content_type = "video/mp4" if is_video else "audio/mpeg"

        # Safe output filename
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not safe_filename.endswith(ext):
            safe_filename += ext

        return FileResponse(
            trimmed_file,
            media_type=content_type,
            filename=safe_filename,
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"',
                "Access-Control-Allow-Origin": "*"
            }
        )
    except Exception as e:
        err_msg = str(e)
        if "does not contain any stream" in err_msg.lower() or "no audio stream" in err_msg.lower():
            raise HTTPException(
                status_code=400,
                detail="Unable to trim audio: No audio stream detected in this Instagram Reel. On cloud servers, Instagram restricts audio for unauthenticated requests. Please add an Instagram session cookie in Settings to trim audio."
            )
        raise HTTPException(status_code=500, detail=f"Trim processing failed: {err_msg}")

@app.get("/api/settings/cookie")
async def get_cookie_status():
    """
    Returns whether an authenticated Instagram session cookie is active.
    """
    has_cookie = bool(ACTIVE_COOKIE or (os.path.exists(COOKIE_FILE_PATH) and os.path.getsize(COOKIE_FILE_PATH) > 10))
    return {"has_cookie": has_cookie}

@app.post("/api/settings/cookie")
async def save_cookie(payload: CookiePayload):
    """
    Save or clear the Instagram session cookie.
    Converts raw cookies or sessionid into Netscape format for yt-dlp.
    """
    global ACTIVE_COOKIE
    cookie_str = payload.cookie.strip()
    
    if not cookie_str:
        ACTIVE_COOKIE = ""
        if os.path.exists(COOKIE_FILE_PATH):
            try:
                os.remove(COOKIE_FILE_PATH)
            except OSError:
                pass
        return {"success": True, "message": "Cookie cleared successfully!"}
    
    ACTIVE_COOKIE = cookie_str
    try:
        netscape_data = convert_to_netscape_content(ACTIVE_COOKIE)
        with open(COOKIE_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(netscape_data)
        return {"success": True, "message": "Cookie saved successfully! Requests are now authenticated with Instagram."}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ClipOwn Downloader"}

@app.get("/api/proxy-image")
async def proxy_image(url: str = Query(..., description="Image URL to proxy")):
    """
    Proxies creator avatars and thumbnails to bypass cross-origin hotlinking restrictions,
    adblockers, and referrer blocking. Automatically serves an elegant SVG fallback if unavailable.
    """
    clean_url = url.strip()
    if not clean_url or not clean_url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid image URL.")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }
    try:
        req = requests.get(clean_url, headers=headers, timeout=8)
        if req.status_code == 200 and req.content and len(req.content) > 100:
            content_type = req.headers.get("Content-Type", "image/jpeg")
            return Response(
                content=req.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*"
                }
            )
    except Exception:
        pass
    
    # Graceful SVG avatar fallback (Instagram gradient with user silhouette)
    svg_fallback = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        '<defs>'
        '<linearGradient id="ig" x1="0%" y1="100%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#f09433"/>'
        '<stop offset="25%" stop-color="#e6683c"/>'
        '<stop offset="50%" stop-color="#dc2743"/>'
        '<stop offset="75%" stop-color="#cc2366"/>'
        '<stop offset="100%" stop-color="#bc1888"/>'
        '</linearGradient>'
        '</defs>'
        '<circle cx="64" cy="64" r="64" fill="url(#ig)"/>'
        '<path d="M64 60a18 18 0 1 0 0-36 18 18 0 0 0 0 36zm0 10c-20 0-40 10-40 22v8h80v-8c0-12-20-22-40-22z" fill="#ffffff" opacity="0.95"/>'
        '</svg>'
    )
    return Response(
        content=svg_fallback,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.get("/api/system-diag")
async def system_diag(url: str = Query("https://www.instagram.com/reel/DbUlcPTTb-l/")):
    """Diagnostic endpoint to inspect FFmpeg, direct API data, and yt-dlp formats for any Reel."""
    import subprocess, yt_dlp, imageio_ffmpeg, xml.etree.ElementTree as ET
    exe = ensure_ffmpeg()
    raw_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    try:
        ver_res = subprocess.run([exe, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        ffmpeg_ver = ver_res.stdout.splitlines()[0] if ver_res.returncode == 0 else f"Error: {ver_res.stderr}"
    except Exception as e:
        ffmpeg_ver = f"Exception: {str(e)}"

    formats_summary = []
    raw_manifest = ''
    has_audio_in_manifest = False
    manifest_len = 0
    try:
        ydl_opts = {'quiet': True, 'skip_download': True, 'no_warnings': True}
        if os.path.exists(COOKIE_FILE_PATH) and os.path.getsize(COOKIE_FILE_PATH) > 10:
            ydl_opts['cookiefile'] = COOKIE_FILE_PATH
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats_summary = [{
                'id': f.get('format_id'),
                'ext': f.get('ext'),
                'vcodec': f.get('vcodec'),
                'acodec': f.get('acodec'),
                'format_note': f.get('format_note'),
                'url_snippet': f.get('url', '').split('?')[0][-35:] if f.get('url') else None
            } for f in info.get('formats', [])]
            raw_manifest = info.get('video_dash_manifest') or ''
            has_audio_in_manifest = 'audio' in raw_manifest.lower()
            manifest_len = len(raw_manifest)
    except Exception as e:
        formats_summary = f"Error: {str(e)}"

    cookie_status = "Not configured"
    if os.path.exists(COOKIE_FILE_PATH):
        try:
            with open(COOKIE_FILE_PATH, "r", encoding="utf-8") as f:
                raw_c = f.read()
                has_sess = "sessionid" in raw_c
                has_uid = "ds_user_id" in raw_c
                cookie_status = f"Active Netscape file ({len(raw_c)} bytes, sessionid={has_sess}, ds_user_id={has_uid})"
        except Exception as e:
            cookie_status = f"Error reading: {e}"

    extract_diag = None
    try:
        extract_diag = extract_instagram_media(url, cookie_string=ACTIVE_COOKIE)
        for k in list(extract_diag.keys()):
            if 'url' in k and extract_diag[k]:
                extract_diag[k] = extract_diag[k][:90] + "..."
    except Exception as e:
        extract_diag = f"Extract exception: {str(e)}"

    direct_api_diag = {}
    try:
        import sys
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)
        import extractor
        _, sc = extractor.clean_instagram_url(url)
        mid = extractor.shortcode_to_media_id(sc)
        direct_api_diag['shortcode'] = sc
        direct_api_diag['media_id'] = mid
        cookies_map = {}
        if ACTIVE_COOKIE:
            for part in ACTIVE_COOKIE.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    cookies_map[k.strip()] = v.strip()
        h = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'X-IG-App-ID': '936619743392459',
            'X-ASBD-ID': '198387',
            'Accept': '*/*',
        }
        r_api = requests.get(f'https://i.instagram.com/api/v1/media/{mid}/info/', headers=h, cookies=cookies_map, timeout=10)
        direct_api_diag['http_status'] = r_api.status_code
        if r_api.status_code == 200:
            rj = r_api.json()
            items_list = rj.get('items', [])
            if items_list:
                it = items_list[0]
                direct_api_diag['item_keys'] = [k for k in it.keys() if any(x in k.lower() for x in ['video', 'dash', 'clip', 'music', 'audio'])]
                direct_api_diag['has_video_dash_manifest'] = 'video_dash_manifest' in it
                if 'video_dash_manifest' in it:
                    direct_api_diag['manifest_len'] = len(str(it['video_dash_manifest']))
                    direct_api_diag['manifest_snippet'] = str(it['video_dash_manifest'])[:600]
                direct_api_diag['has_dash_manifest'] = 'dash_manifest' in it
                direct_api_diag['video_versions_count'] = len(it.get('video_versions', []))
                direct_api_diag['clips_metadata_keys'] = list((it.get('clips_metadata') or {}).keys())
    except Exception as ex:
        direct_api_diag['error'] = str(ex)

    return {
        "os": os.name,
        "active_cookie_len": len(ACTIVE_COOKIE),
        "cookie_file_exists": os.path.exists(COOKIE_FILE_PATH),
        "cookie_status": cookie_status,
        "direct_api_diag": direct_api_diag,
        "extract_diag": extract_diag,
        "ffmpeg_bin": exe,
        "ffmpeg_exists": os.path.exists(exe),
        "raw_exe": raw_exe,
        "raw_exe_exists": os.path.exists(raw_exe),
        "ffmpeg_version": ffmpeg_ver,
        "manifest_len": manifest_len,
        "has_audio_in_manifest": has_audio_in_manifest,
        "manifest_snippet": raw_manifest[:300] if raw_manifest else None,
        "formats_count": len(formats_summary) if isinstance(formats_summary, list) else 0,
        "formats": formats_summary
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting ClipOwn server at http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
