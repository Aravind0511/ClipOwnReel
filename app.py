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
from pydantic import BaseModel
from extractor import extract_instagram_media, COOKIE_FILE_PATH
from trimmer import trim_media
from ffmpeg_utils import ensure_ffmpeg, mux_video_audio, extract_mp3_audio

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

# Mount static files directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory or env-based cookie store
ACTIVE_COOKIE = os.environ.get("INSTAGRAM_COOKIE", "")

class CookiePayload(BaseModel):
    cookie: str

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the modern single-page web app."""
    index_file = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(index_file):
        index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_file):
        raise HTTPException(status_code=404, detail="Index template not found")
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

@app.get("/api/fetch-info")
async def fetch_info(url: str = Query(..., description="Instagram Reel, Video, or Post URL")):
    """
    Fetch media information and available download streams for the given Instagram URL.
    """
    clean_url = url.strip()
    
    # Basic Instagram URL validation
    ig_pattern = r"(?:https?:\/\/)?(?:www\.)?(?:instagram\.com)\/(?:p|reel|tv|stories)\/([A-Za-z0-9_-]+)"
    if not re.search(ig_pattern, clean_url) and "instagram.com" not in clean_url:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": "Invalid Instagram URL. Please enter a valid Instagram Reel, Video, or Post link."
            }
        )

    # Call extractor
    result = extract_instagram_media(clean_url, cookie_string=ACTIVE_COOKIE)
    return JSONResponse(content=result)

@app.api_route("/api/download", methods=["GET", "HEAD"])
async def download_media(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="Direct media URL to download"),
    filename: str = Query("clipown_video.mp4", description="Output filename"),
    audio_url: str = Query(None, description="Optional separate audio stream URL to mux"),
    media_type: str = Query("video", description="Download format type: video or audio")
):
    """
    Stream or transcode video/audio file directly to client with forced attachment header.
    Automatically muxes DASH video + audio streams, and converts audio streams to authentic MP3.
    """
    clean_url = url.strip()
    if not clean_url or clean_url == "#":
        raise HTTPException(status_code=400, detail="Invalid media download URL.")

    # 1. Audio Download Request (extract authentic MP3)
    if media_type.lower() == "audio" or filename.lower().endswith(".mp3"):
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not safe_filename.endswith(".mp3"):
            safe_filename += ".mp3"
        try:
            mp3_path = extract_mp3_audio(clean_url)
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to generate MP3 audio: {str(e)}")

    # 2. Video Download with separate audio stream (mux DASH video + audio)
    if audio_url and audio_url.strip() and audio_url.strip() != clean_url:
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not safe_filename.endswith(".mp4"):
            safe_filename += ".mp4"
        try:
            muxed_path = mux_video_audio(clean_url, audio_url.strip())
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to mux video and audio: {str(e)}")

    # 3. Progressive Video or Direct Streaming
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.instagram.com/",
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
async def stream_media_for_preview(request: Request, url: str = Query(..., description="Direct media URL to stream")):
    """
    Proxy video streams with Range request support for smooth browser video preview & scrubbing.
    """
    clean_url = url.strip()
    if not clean_url or clean_url == "#":
        raise HTTPException(status_code=400, detail="Invalid media URL.")

    if os.path.exists(clean_url):
        return FileResponse(clean_url, media_type="video/mp4", headers={"Access-Control-Allow-Origin": "*"})

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
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
    audio_url: str = Query(None, description="Optional separate audio stream URL for DASH streams")
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

    try:
        trimmed_file = trim_media(
            source_url=clean_url,
            start_time=start,
            end_time=end,
            media_type=media_type,
            audio_url=audio_url.strip() if audio_url else None
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
        raise HTTPException(status_code=500, detail=f"Trim processing failed: {str(e)}")

@app.post("/api/settings/cookie")
async def save_cookie(payload: CookiePayload):
    """
    Save or clear the Instagram session cookie.
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
        with open(COOKIE_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(ACTIVE_COOKIE)
        return {"success": True, "message": "Cookie saved successfully!"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ClipOwn Downloader"}

@app.get("/api/system-diag")
async def system_diag():
    """Diagnostic endpoint to inspect FFmpeg and yt-dlp formats."""
    import subprocess, yt_dlp, imageio_ffmpeg
    exe = ensure_ffmpeg()
    raw_exe = imageio_ffmpeg.get_ffmpeg_exe()
    
    try:
        ver_res = subprocess.run([exe, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        ffmpeg_ver = ver_res.stdout.splitlines()[0] if ver_res.returncode == 0 else f"Error: {ver_res.stderr}"
    except Exception as e:
        ffmpeg_ver = f"Exception: {str(e)}"

    try:
        ydl_opts = {'quiet': True, 'skip_download': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info("https://www.instagram.com/reel/Dcp3JkzJTA6/", download=False)
            formats_summary = [{
                'id': f.get('format_id'),
                'ext': f.get('ext'),
                'vcodec': f.get('vcodec'),
                'acodec': f.get('acodec'),
                'format_note': f.get('format_note'),
                'url_snippet': f.get('url', '').split('?')[0][-25:] if f.get('url') else None
            } for f in info.get('formats', [])]
            raw_manifest = info.get('video_dash_manifest') or ''
            has_audio_in_manifest = 'audio' in raw_manifest.lower()
            manifest_len = len(raw_manifest)
    except Exception as e:
        formats_summary = f"Error: {str(e)}"
        raw_manifest = ''
        has_audio_in_manifest = False
        manifest_len = 0

    return {
        "os": os.name,
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
