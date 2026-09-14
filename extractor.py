"""
ClipOwn - Instagram Media Extraction Engine
Extracts real Instagram video/audio streams using yt-dlp.
"""

import os
import re
import tempfile
import uuid
import xml.etree.ElementTree as ET
import requests
import json
import yt_dlp
from ffmpeg_utils import ensure_ffmpeg

COOKIE_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")

# Global media metadata registry to auto-resolve clip offset and duration
MEDIA_REGISTRY = {}

def register_media_meta(shortcode: str, data: dict):
    """Registers media metadata so download, stream, and trim endpoints auto-resolve clip duration and offset."""
    if not data or not isinstance(data, dict):
        return
    sc = shortcode or data.get('shortcode') or ''
    meta = {
        'shortcode': sc,
        'audio_start_offset': float(data.get('audio_start_offset') or 0.0),
        'duration_seconds': float(data.get('duration_seconds') or 30.0),
        'download_url_audio': data.get('download_url_audio'),
        'download_url_hd': data.get('download_url_hd'),
        'download_url_sd': data.get('download_url_sd'),
        'separate_audio_url': data.get('separate_audio_url'),
    }
    if sc:
        MEDIA_REGISTRY[sc] = meta
    for key in ['download_url_audio', 'download_url_hd', 'download_url_sd', 'separate_audio_url']:
        u = data.get(key)
        if u and isinstance(u, str) and len(u) > 10:
            MEDIA_REGISTRY[u] = meta
            p = u.split('?')[0]
            if p:
                MEDIA_REGISTRY[p] = meta

def get_media_meta(identifier: str) -> dict:
    """Auto-resolves audio_start_offset, duration, and audio stream for a shortcode or media URL."""
    if not identifier:
        return {}
    clean_id = identifier.strip()
    if clean_id in MEDIA_REGISTRY:
        return MEDIA_REGISTRY[clean_id]
    p = clean_id.split('?')[0]
    if p in MEDIA_REGISTRY:
        return MEDIA_REGISTRY[p]
    for k, v in MEDIA_REGISTRY.items():
        if k and len(k) > 15 and (k in clean_id or clean_id in k):
            return v
    return {}

def convert_to_netscape_content(cookie_str: str) -> str:
    """
    Converts a raw cookie string, key-value pairs, or raw sessionid into standard Netscape format.
    Automatically extracts and attaches ds_user_id and fallback csrftoken if missing.
    """
    cleaned = cookie_str.strip()
    if "# Netscape" in cleaned:
        if "ds_user_id" not in cleaned and "sessionid" in cleaned:
            for line in cleaned.splitlines():
                if "sessionid" in line:
                    parts = line.strip().split()
                    if len(parts) >= 7:
                        sess_val = parts[6]
                        user_id = sess_val.split('%3A')[0].split(':')[0]
                        if user_id.isdigit():
                            cleaned += f"\n.instagram.com\tTRUE\t/\tTRUE\t2147483647\tds_user_id\t{user_id}\n"
        return cleaned

    if "=" not in cleaned and len(cleaned) > 10:
        cleaned = f"sessionid={cleaned}"

    cookie_dict = {}
    for item in cleaned.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        key, val = item.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key and val:
            cookie_dict[key] = val

    if "sessionid" in cookie_dict and "ds_user_id" not in cookie_dict:
        sess_val = cookie_dict["sessionid"]
        user_id = sess_val.split('%3A')[0].split(':')[0]
        if user_id.isdigit():
            cookie_dict["ds_user_id"] = user_id

    if "csrftoken" not in cookie_dict:
        cookie_dict["csrftoken"] = "missing_csrf"

    lines = ["# Netscape HTTP Cookie File\n"]
    for k, v in cookie_dict.items():
        lines.append(f".instagram.com\tTRUE\t/\tTRUE\t2147483647\t{k}\t{v}\n")
    return "".join(lines)

def create_netscape_cookiefile(cookie_str: str) -> str:
    """
    Writes a temporary Netscape-formatted cookie file for yt-dlp.
    """
    content = convert_to_netscape_content(cookie_str)
    temp_dir = tempfile.gettempdir()
    cookie_path = os.path.join(temp_dir, f"clipown_cookie_{uuid.uuid4().hex[:8]}.txt")
    with open(cookie_path, "w", encoding="utf-8") as f:
        f.write(content)
    return cookie_path

def shortcode_to_media_id(shortcode: str) -> str:
    """Converts an Instagram Base64-style shortcode to a numeric media ID."""
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_'
    pk = 0
    for char in shortcode:
        pk = pk * 64 + alphabet.index(char)
    return str(pk)

def extract_via_direct_api(url: str, cookie_string: str = None) -> dict:
    """
    Directly queries Instagram's authenticated media info API.
    Fast, reliable, and provides authentic DASH 1080p, dedicated AAC audio, and progressive streams.
    """
    match = re.search(r"/(?:share/)?(reels?|p|tv|stories)/([A-Za-z0-9_-]+)", url.strip())
    if not match:
        return None
    raw_type, shortcode = match.group(1), match.group(2)
    media_type = 'reel' if raw_type.startswith('reel') else raw_type
    media_id = shortcode_to_media_id(shortcode)

    raw_cookie = ""
    if cookie_string and len(cookie_string.strip()) > 10:
        raw_cookie = cookie_string.strip()
    elif os.path.exists(COOKIE_FILE_PATH) and os.path.getsize(COOKIE_FILE_PATH) > 10:
        try:
            with open(COOKIE_FILE_PATH, "r", encoding="utf-8") as f:
                raw_cookie = f.read().strip()
        except Exception:
            pass

    if not raw_cookie:
        return None

    sessionid = ""
    ds_user_id = ""
    csrftoken = ""

    if "# Netscape" in raw_cookie:
        for line in raw_cookie.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 7:
                k, v = parts[5], parts[6]
                if k == 'sessionid':
                    sessionid = v
                elif k == 'ds_user_id':
                    ds_user_id = v
                elif k == 'csrftoken':
                    csrftoken = v
    else:
        if "=" not in raw_cookie and len(raw_cookie) > 10:
            raw_cookie = f"sessionid={raw_cookie}"
        for part in raw_cookie.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            k, v = k.strip(), v.strip()
            if k == 'sessionid':
                sessionid = v
            elif k == 'ds_user_id':
                ds_user_id = v
            elif k == 'csrftoken':
                csrftoken = v

    if not sessionid:
        return None

    if not ds_user_id and sessionid:
        user_id = sessionid.split('%3A')[0].split(':')[0]
        if user_id.isdigit():
            ds_user_id = user_id

    cookies = {'sessionid': sessionid}
    if ds_user_id:
        cookies['ds_user_id'] = ds_user_id
    if csrftoken:
        cookies['csrftoken'] = csrftoken

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'X-IG-App-ID': '936619743392459',
        'X-ASBD-ID': '198387',
        'Accept': '*/*',
    }

    for base_url in ['https://i.instagram.com/api/v1', 'https://www.instagram.com/api/v1']:
        try:
            r = requests.get(f'{base_url}/media/{media_id}/info/', headers=headers, cookies=cookies, timeout=12)
            if r.status_code == 200:
                data = r.json()
                items = data.get('items', [])
                if not items:
                    continue
                item = items[0]

                video_hd = None
                hd_width = 1080
                hd_height = 1920
                dash_audio_url = None
                manifest = item.get('video_dash_manifest', '')
                if manifest:
                    try:
                        # 1. First attempt: yt-dlp's native, comprehensive MPD parser
                        ydl_inst = yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True})
                        ie = yt_dlp.extractor.common.InfoExtractor(ydl_inst)
                        mpd_doc = ie._parse_xml(manifest, shortcode)
                        dash_formats = ie._parse_mpd_formats(mpd_doc, mpd_id='dash')
                        
                        dash_a_list = [
                            f for f in dash_formats
                            if f.get('vcodec') == 'none'
                            or 'audio' in (f.get('format_note') or '').lower()
                            or f.get('ext') in ['m4a', 'aac']
                            or (f.get('acodec') and f.get('acodec') != 'none')
                        ]
                        dash_v_list = [
                            f for f in dash_formats
                            if (f.get('height') or 0) > 0
                            or 'video' in (f.get('format_note') or '').lower()
                        ]
                        
                        if dash_v_list:
                            dash_v_list.sort(key=lambda x: (x.get('height') or 0, x.get('tbr') or 0))
                            hd_width = dash_v_list[-1].get('width') or 1080
                            hd_height = dash_v_list[-1].get('height') or 1920
                            video_hd = dash_v_list[-1].get('url')
                            
                        if dash_a_list:
                            dash_a_list.sort(key=lambda x: (x.get('tbr') or 0, x.get('abr') or 0))
                            dash_audio_url = dash_a_list[-1].get('url')
                    except Exception:
                        pass

                    # 2. Robust XML Fallback if yt-dlp parser did not find dash_audio_url
                    if not dash_audio_url or not video_hd:
                        try:
                            root = ET.fromstring(manifest)
                            dash_v = []
                            dash_a = []
                            for rep in root.iter():
                                if not rep.tag.endswith('Representation'):
                                    continue
                                rep_id = rep.attrib.get('id', '')
                                mime = rep.attrib.get('mimeType', '')
                                w = int(rep.attrib.get('width', 0) or 0)
                                h = int(rep.attrib.get('height', 0) or 0)
                                bw = int(rep.attrib.get('bandwidth', 0) or 0)
                                for b_elem in rep.iter():
                                    if b_elem.tag.endswith('BaseURL') and b_elem.text:
                                        u = b_elem.text.strip()
                                        is_audio = (
                                            (w == 0 and h == 0)
                                            or 'audio' in mime.lower()
                                            or rep_id.endswith('a')
                                            or 'audio' in u.lower()
                                            or 'heaac' in u.lower()
                                            or 'a.mp4' in u.lower()
                                            or '.m4a' in u.lower()
                                        )
                                        if is_audio:
                                            dash_a.append((bw, u))
                                        else:
                                            dash_v.append((w, h, u))
                                        break
                            if dash_v and not video_hd:
                                dash_v.sort(key=lambda x: (x[1], x[0]))
                                hd_width = dash_v[-1][0] or 1080
                                hd_height = dash_v[-1][1] or 1920
                                video_hd = dash_v[-1][2]
                            if dash_a and not dash_audio_url:
                                dash_a.sort(key=lambda x: x[0])
                                dash_audio_url = dash_a[-1][1]
                        except Exception:
                            pass

                versions = item.get('video_versions', [])
                video_sd = versions[0].get('url') if versions else video_hd
                if not video_hd and versions:
                    video_hd = versions[0].get('url')
                    hd_width = versions[0].get('width') or 720
                    hd_height = versions[0].get('height') or 1280

                # Extract music track info for fallback if DASH audio is absent
                clips = item.get('clips_metadata') or {}
                music_info = clips.get('music_info') or {}
                music_asset = music_info.get('music_asset_info') or {}
                music_consumption = music_info.get('music_consumption_info') or {}
                music_url = music_asset.get('fast_start_progressive_download_url') or music_asset.get('progressive_download_url')
                start_ms = music_consumption.get('audio_asset_start_time_in_ms', 0) or 0

                # Also check original_sound_info for audio asset start time or stream URL
                orig_sound = clips.get('original_sound_info') or {}
                orig_consumption = orig_sound.get('consumption_info') or {}
                if not start_ms:
                    start_ms = (
                        orig_sound.get('audio_asset_start_time_in_ms')
                        or orig_consumption.get('audio_asset_start_time_in_ms')
                        or orig_sound.get('start_time_in_ms')
                        or 0
                    )
                if not music_url:
                    music_url = orig_sound.get('progressive_download_url')

                # Prioritize master DASH audio stream: contains voice + mixed background music!
                if dash_audio_url:
                    best_audio_url = dash_audio_url
                    separate_audio_url = dash_audio_url
                    audio_start_offset = 0.0
                elif music_url and start_ms:
                    best_audio_url = music_url
                    separate_audio_url = music_url
                    audio_start_offset = round(float(start_ms) / 1000.0, 3)
                elif music_url:
                    best_audio_url = music_url
                    separate_audio_url = music_url
                    audio_start_offset = 0.0
                else:
                    best_audio_url = video_sd
                    separate_audio_url = None
                    audio_start_offset = 0.0

                user = item.get('user', {})
                author = user.get('username') or user.get('full_name') or 'instagram_user'
                author_avatar = (
                    user.get('profile_pic_url')
                    or user.get('profile_pic_url_hd')
                    or (user.get('hd_profile_pic_url_info') or {}).get('url')
                    or (user.get('hd_profile_pic_versions') or [{}])[0].get('url')
                    or f"https://ui-avatars.com/api/?name={requests.utils.quote(author)}&background=e1306c&color=fff&size=128&bold=true"
                )

                caption = item.get('caption') or {}
                raw_title = caption.get('text', '') if isinstance(caption, dict) else ''
                clean_title = re.sub(r'[\r\n]+', ' ', raw_title).strip()[:100] if raw_title else f'Instagram Reel [{shortcode}]'

                imgs = item.get('image_versions2', {}).get('candidates', [])
                thumbnail = imgs[0].get('url') if imgs else 'https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800&auto=format&fit=crop&q=80'

                raw_duration = float(item.get('video_duration', 30.0) or 30.0)
                duration = format_duration(raw_duration)

                res = {
                    'success': True,
                    'is_mock': False,
                    'shortcode': shortcode,
                    'title': clean_title or f'Instagram Reel [{shortcode}]',
                    'author': author,
                    'author_avatar': author_avatar,
                    'thumbnail': thumbnail,
                    'duration': duration,
                    'duration_seconds': max(1.0, round(raw_duration, 1)),
                    'audio_start_offset': audio_start_offset,
                    'format': 'MP4 (H.264)',
                    'resolution': f'{hd_width} x {hd_height}',
                    'size': '~ 18.5 MB',
                    'has_audio': bool(best_audio_url),
                    'dash_audio_url': dash_audio_url,
                    'auth_required': False,
                    'download_url_hd': video_hd,
                    'download_url_sd': video_sd,
                    'download_url_audio': best_audio_url,
                    'separate_audio_url': separate_audio_url,
                    'sd_audio_url': None,
                    'preview_url': video_sd,
                    'direct_link': f'https://www.instagram.com/{media_type}/{shortcode}/',
                    'source': 'instagram_direct_api'
                }
                register_media_meta(shortcode, res)
                return res
        except Exception:
            continue
    return None

def clean_instagram_url(url: str) -> str:
    """
    Sanitizes and normalizes an Instagram URL by stripping tracking queries.
    e.g. https://www.instagram.com/reel/Dcp3JkzJTA6/?utm_source=... -> https://www.instagram.com/reel/Dcp3JkzJTA6/
    """
    clean = url.strip()
    match = re.search(r"/(?:share/)?(reels?|p|tv|stories)/([A-Za-z0-9_-]+)", clean)
    if match:
        raw_type = match.group(1)
        media_type = 'reel' if raw_type.startswith('reel') else raw_type
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

def extract_via_ytdlp(url: str, cookie_string: str = None) -> dict:
    """
    Extracts authentic Instagram media via yt-dlp by parsing the web DASH manifest.
    This extracts the complete master audio stream containing the creator's speaking voice + synchronized BGM!
    """
    normalized_url, shortcode = clean_instagram_url(url)
    effective_cookie = cookie_string
    if not effective_cookie and os.path.exists(COOKIE_FILE_PATH) and os.path.getsize(COOKIE_FILE_PATH) > 10:
        try:
            with open(COOKIE_FILE_PATH, "r", encoding="utf-8") as f:
                effective_cookie = f.read().strip()
        except Exception:
            pass

    ffmpeg_bin = ensure_ffmpeg()
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
        'ffmpeg_location': ffmpeg_bin,
    }

    cookie_temp_file = None
    if effective_cookie and len(effective_cookie.strip()) > 10:
        cookie_temp_file = create_netscape_cookiefile(effective_cookie.strip())
        ydl_opts['cookiefile'] = cookie_temp_file
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

            formats = info.get('formats', [])

            # 1. Dedicated audio streams (master audio with speaking voice + mixed BGM)
            audio_formats = [
                f for f in formats
                if f.get('url') and (
                    str(f.get('format_id', '')).endswith('a')
                    or (f.get('vcodec') == 'none' and f.get('acodec') and f.get('acodec') != 'none')
                )
            ]
            if audio_formats:
                audio_formats.sort(key=lambda x: (x.get('tbr') or 0, x.get('abr') or 0))

            # 2. Progressive streams (contains both video and audio in single MP4)
            progressive_formats = [
                f for f in formats
                if f.get('url') and (
                    str(f.get('format_id', '')) in ['0', '1', '2', '3']
                    or 'progressive' in f.get('url', '').lower()
                    or (f.get('format_note') != 'DASH video' and not str(f.get('format_id', '')).endswith(('v', 'a')))
                    or (f.get('vcodec') and f.get('vcodec') != 'none' and f.get('acodec') and f.get('acodec') != 'none')
                )
            ]

            # 3. DASH video-only streams (e.g. 1080p, requires audio track mux)
            dash_video_formats = [
                f for f in formats
                if f.get('url') and (
                    str(f.get('format_id', '')).endswith('v')
                    or f.get('format_note') == 'DASH video'
                    or (f.get('acodec') == 'none' and f.get('vcodec') and f.get('vcodec') != 'none' and str(f.get('format_id', '')) not in ['0', '1', '2', '3'])
                )
            ]
            if dash_video_formats:
                dash_video_formats.sort(key=lambda x: (x.get('height') or 0, x.get('tbr') or 0))

            # General video formats (fallback)
            any_video_formats = [
                f for f in formats
                if f.get('url') and (f.get('vcodec') != 'none' or 'v' in str(f.get('format_id', '')))
            ]

            # Determine best audio URL:
            # If dedicated master audio stream exists -> use it (contains voice + BGM!)
            # Else if progressive format exists -> use progressive stream URL (contains AAC audio!)
            if audio_formats:
                best_audio_url = audio_formats[-1]['url']
            elif progressive_formats:
                best_audio_url = progressive_formats[-1]['url']
            else:
                best_audio_url = None

            has_audio = (best_audio_url is not None)

            # Determine HD video stream
            if dash_video_formats:
                best_dash = dash_video_formats[-1]
                video_hd = best_dash['url']
                hd_height = best_dash.get('height') or 1080
                hd_width = best_dash.get('width') or 1920
                separate_audio_url = best_audio_url if audio_formats else None
            elif progressive_formats:
                video_hd = progressive_formats[-1]['url']
                hd_height = progressive_formats[-1].get('height') or 720
                hd_width = progressive_formats[-1].get('width') or 1280
                separate_audio_url = best_audio_url if audio_formats else None
            elif any_video_formats:
                video_hd = any_video_formats[-1]['url']
                hd_height = any_video_formats[-1].get('height') or 720
                hd_width = any_video_formats[-1].get('width') or 1280
                separate_audio_url = best_audio_url if audio_formats else None
            else:
                video_hd = info.get('url')
                hd_height = info.get('height') or 1080
                hd_width = info.get('width') or 1920
                separate_audio_url = best_audio_url if audio_formats else None

            # Determine SD video stream
            if progressive_formats:
                video_sd = progressive_formats[0]['url']
            elif dash_video_formats:
                video_sd = dash_video_formats[0]['url']
            else:
                video_sd = video_hd

            preview_url = video_sd or video_hd

            title = info.get('title') or info.get('description') or f"Instagram Reel [{shortcode}]"
            title = re.sub(r'[\r\n]+', ' ', title).strip()[:100]

            author = info.get('channel') or info.get('uploader') or 'instagram_user'
            thumbnail = info.get('thumbnail')

            raw_duration = info.get('duration')
            if not raw_duration or raw_duration <= 0:
                raw_duration = 30.0
            duration = format_duration(raw_duration)
            resolution = f"{hd_width} x {hd_height}"
            size = format_filesize(info.get('filesize') or info.get('filesize_approx'))

            res = {
                "success": True,
                "is_mock": False,
                "shortcode": shortcode,
                "title": title,
                "author": author,
                "author_avatar": f"https://ui-avatars.com/api/?name={requests.utils.quote(str(author))}&background=e1306c&color=fff&size=128&bold=true",
                "thumbnail": thumbnail,
                "duration": duration,
                "duration_seconds": max(1.0, round(raw_duration, 1)),
                "audio_start_offset": 0.0,
                "format": "MP4 (H.264)",
                "resolution": resolution,
                "size": size,
                "has_audio": has_audio,
                "auth_required": not has_audio,
                "download_url_hd": video_hd,
                "download_url_sd": video_sd,
                "download_url_audio": best_audio_url,
                "separate_audio_url": separate_audio_url,
                "sd_audio_url": None,
                "preview_url": preview_url,
                "direct_link": normalized_url,
                "source": "instagram_ytdlp"
            }
            register_media_meta(shortcode, res)
            return res
    except Exception as e:
        err_text = str(e)
        if "login" in err_text.lower() or "empty media response" in err_text.lower():
            msg = "This Instagram video is restricted or from a private account. Please add your session cookie in Settings to download."
        else:
            msg = f"Failed to extract video: {err_text.splitlines()[-1] if err_text else 'Unknown error'}"

        return {
            "success": False,
            "message": msg,
            "error_detail": err_text
        }
    finally:
        if cookie_temp_file and os.path.exists(cookie_temp_file):
            try:
                os.remove(cookie_temp_file)
            except OSError:
                pass


def extract_instagram_media(url: str, cookie_string: str = None) -> dict:
    """
    Extracts authentic Instagram media information and direct CDN video stream URLs.
    Prioritizes full master audio stream extraction (speaking voice + mixed BGM)
    via web manifest, with authenticated direct API fallback for gated/private posts.
    """
    normalized_url, shortcode = clean_instagram_url(url)

    effective_cookie = cookie_string
    if not effective_cookie and os.path.exists(COOKIE_FILE_PATH) and os.path.getsize(COOKIE_FILE_PATH) > 10:
        try:
            with open(COOKIE_FILE_PATH, "r", encoding="utf-8") as f:
                effective_cookie = f.read().strip()
        except Exception:
            pass

    # 1. First, check direct authenticated API if cookies are available (retrieves HD profile pic, caption, etc.)
    direct_res = None
    if effective_cookie and len(effective_cookie.strip()) > 10:
        try:
            direct_res = extract_via_direct_api(normalized_url, effective_cookie)
        except Exception as e:
            print(f"Direct API extraction attempt skipped: {e}")

    # If direct_res found an authentic master DASH audio stream (voice + mixed audio):
    if direct_res and direct_res.get('success') and direct_res.get('dash_audio_url'):
        register_media_meta(shortcode, direct_res)
        return direct_res

    # 2. Extract via yt-dlp:
    # yt-dlp extracts the web DASH manifest which contains the complete rendered master audio stream
    # with the creator's speaking voice + synchronized BGM!
    yt_res = extract_via_ytdlp(normalized_url, effective_cookie)
    if yt_res and yt_res.get('success') and yt_res.get('has_audio'):
        # If direct_res had the authentic creator avatar URL, attach it to yt_res
        if direct_res and direct_res.get('author_avatar') and direct_res['author_avatar'].startswith('http'):
            yt_res['author_avatar'] = direct_res['author_avatar']
        register_media_meta(shortcode, yt_res)
        return yt_res

    # 3. If yt-dlp failed (e.g. login required, rate limit, private reel) or lacked audio:
    # fall back to direct_res
    if direct_res and direct_res.get('success'):
        register_media_meta(shortcode, direct_res)
        return direct_res

    # 4. Fallback to yt_res even if audio was absent
    if yt_res and yt_res.get('success'):
        register_media_meta(shortcode, yt_res)
        return yt_res

    return yt_res or {
        "success": False,
        "message": "Could not retrieve media details from Instagram. Please ensure the post is public or add cookies."
    }
