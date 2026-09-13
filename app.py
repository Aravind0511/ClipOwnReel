"""
ClipOwn - Modern Instagram Video Downloader
Backend Server (FastAPI)
"""

import os
import re
import requests
from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from extractor import extract_instagram_media, COOKIE_FILE_PATH

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

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
async def download_media(url: str = Query(..., description="Direct media URL to download"), filename: str = "clipown_video.mp4"):
    """
    Stream video or audio file directly to the client with forced attachment header.
    Bypasses CORS and triggers a true file download in browser.
    """
    clean_url = url.strip()
    if not clean_url or clean_url == "#":
        raise HTTPException(status_code=400, detail="Invalid media download URL.")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Referer": "https://www.instagram.com/",
            "Accept": "*/*",
        }
        req = requests.get(clean_url, stream=True, timeout=25, headers=headers)
        
        if req.status_code != 200:
            raise HTTPException(status_code=req.status_code, detail="Media stream provider returned an error.")

        # Determine content type
        content_type = req.headers.get("Content-Type", "video/mp4")
        
        # Safe filename
        safe_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
        if not safe_filename.endswith(('.mp4', '.mp3', '.m4a')):
            safe_filename += '.mp4'

        def iterfile():
            for chunk in req.iter_content(chunk_size=1024 * 64):
                if chunk:
                    yield chunk

        headers = {
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Access-Control-Allow-Origin": "*"
        }
        if "Content-Length" in req.headers:
            headers["Content-Length"] = req.headers["Content-Length"]

        return StreamingResponse(
            iterfile(),
            media_type=content_type,
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stream media: {str(e)}")

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

if __name__ == "__main__":
    import uvicorn
    print("Starting ClipOwn server at http://127.0.0.1:8000 ...")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
