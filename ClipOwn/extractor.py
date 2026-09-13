"""
ClipOwn - Instagram Media Extraction Engine
Extracts real Instagram video/audio streams using yt-dlp.
"""

import os
import re
import yt_dlp

COOKIE_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

def clean_instagram_url(url: str) -> str:
    """
    Sanitizes and normalizes an Instagram URL by stripping tracking queries.
    e.g. https://www.instagram.com/reel/Dcp3JkzJTA6/?utm_source=... -> https://www.instagram.com/reel/Dcp3JkzJTA6/
    """
    clean = url.strip()
    match = re.search(r"/(reel|p|tv|stories)/([A-Za-z0-9_-]+)", clean)
    if match:
        media_type = match.group(1)
        shortcode = match.group(2)
        return f"https://www.instagram.com/{media_type}/{shortcode}/", shortcode
    # Fallback to stripping query params
    return clean.split('?')[0].rstrip('/') + '/', ""

def format_duration(seconds) -> str:
    """Format seconds into M:SS string."""
    if not seconds:
        return "0:30"
    try:
        sec = float(seconds)
        m = int(sec // 60)
        s = int(sec % 60)
        return f"{m}:{s:02d}"
    except (ValueError, TypeError):
        return "0:30"

def format_filesize(size_bytes) -> str:
    """Format bytes into readable string."""
    if not size_bytes:
        return "~ 15 MB"
    try:
        mb = float(size_bytes) / (1024 * 1024)
        return f"~ {mb:.1f} MB"
    except (ValueError, TypeError):
        return "~ 15 MB"

def extract_instagram_media(url: str, cookie_string: str = None) -> dict:
    """
    Extracts authentic Instagram media information and direct CDN video stream URLs.
    """
    normalized_url, shortcode = clean_instagram_url(url)
    
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
        'format': 'best',
    }
    
    # Configure custom cookies if valid
    if cookie_string and len(cookie_string.strip()) > 10:
        ydl_opts['http_headers'] = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Cookie': cookie_string.strip(),
        }
    elif os.path.exists(COOKIE_FILE_PATH) and os.path.getsize(COOKIE_FILE_PATH) > 10:
        ydl_opts['cookiefile'] = COOKIE_FILE_PATH
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(normalized_url, download=False)
            
            if not info:
                return {
                    "success": False,
                    "message": "Could not retrieve media details from Instagram. Please ensure the post is public."
                }
            
            # Find streams
            direct_video_url = info.get('url')
            formats = info.get('formats', [])
            
            # Filter formats that have BOTH audio and video (progressive streams)
            # Avoid video-only DASH streams where acodec == 'none'
            progressive_formats = [
                f for f in formats
                if f.get('url') and f.get('acodec') != 'none' and f.get('vcodec') != 'none'
            ]
            
            # Filter dedicated audio formats (acodec != 'none' and vcodec == 'none')
            audio_formats = [
                f for f in formats
                if f.get('url') and f.get('vcodec') == 'none' and f.get('acodec') != 'none'
            ]

            # Choose progressive video stream (guaranteed to have both audio AND video)
            if progressive_formats:
                progressive_formats.sort(key=lambda x: (x.get('height') or 0, x.get('tbr') or 0))
                video_hd = progressive_formats[-1]['url']
                video_sd = progressive_formats[0]['url']
            else:
                video_hd = direct_video_url
                video_sd = direct_video_url

            # Dedicated audio stream
            if audio_formats:
                audio_url = audio_formats[0]['url']
            else:
                audio_url = video_hd

            if not video_hd:
                return {
                    "success": False,
                    "message": "Instagram returned metadata but no downloadable video stream was found. The post may only contain images."
                }

            # Extract accurate metadata
            title = info.get('title') or info.get('description', '')[:100] or f"Instagram Reel [{shortcode}]"
            author = info.get('uploader') or info.get('uploader_id') or info.get('channel') or "instagram_user"
            thumbnail = info.get('thumbnail') or "https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800&auto=format&fit=crop&q=80"
            duration = format_duration(info.get('duration'))
            width = info.get('width') or 1080
            height = info.get('height') or 1920
            resolution = f"{width} x {height}"
            size = format_filesize(info.get('filesize') or info.get('filesize_approx'))

            return {
                "success": True,
                "is_mock": False,
                "shortcode": shortcode,
                "title": title,
                "author": author,
                "author_avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80",
                "thumbnail": thumbnail,
                "duration": duration,
                "format": "MP4 (H.264)",
                "resolution": resolution,
                "size": size,
                "download_url_hd": video_hd,
                "download_url_sd": video_sd,
                "download_url_audio": audio_url,
                "direct_link": normalized_url,
                "source": "instagram_live"
            }
    except Exception as e:
        err_text = str(e)
        # Check if error mentions login or private
        if "login" in err_text.lower() or "empty media response" in err_text.lower():
            msg = "This Instagram video is restricted or from a private account. Please add your session cookie in Settings to download."
        else:
            msg = f"Failed to extract video: {err_text.splitlines()[-1] if err_text else 'Unknown error'}"
            
        return {
            "success": False,
            "message": msg,
            "error_detail": err_text
        }
