"""
ClipOwn - FFmpeg Utilities
Ensures FFmpeg executable is located, added to PATH, and provides muxing/conversion helpers.
"""

import os
import shutil
import subprocess
import tempfile
import uuid
import requests
import imageio_ffmpeg

def ensure_ffmpeg() -> str:
    """
    Locates FFmpeg executable via imageio-ffmpeg, creates a standard 'ffmpeg' binary in bin/,
    and prepends it to PATH for yt-dlp and subprocesses.
    """
    try:
        raw_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raw_exe = "ffmpeg"

    base_dir = os.path.dirname(os.path.abspath(__file__))
    bin_dir = os.path.join(base_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    target_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    target_path = os.path.join(bin_dir, target_name)
    
    if os.path.exists(raw_exe) and not os.path.exists(target_path):
        try:
            shutil.copy2(raw_exe, target_path)
        except Exception:
            pass
            
    if os.name != "nt":
        for p in [raw_exe, target_path]:
            if p and os.path.exists(p):
                try:
                    os.chmod(p, 0o755)
                except Exception:
                    pass

    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        
    final_bin = target_path if (os.path.exists(target_path) and os.access(target_path, os.X_OK)) else raw_exe
    os.environ["FFMPEG_BINARY"] = final_bin
    return final_bin

def download_stream_chunked(url: str, ext: str = "mp4") -> str:
    """
    Downloads media from URL into a temporary file using Instagram-compatible headers.
    """
    if os.path.exists(url):
        return url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "*/*",
    }
    
    resp = requests.get(url, stream=True, timeout=35, headers=headers)
    resp.raise_for_status()

    temp_dir = tempfile.gettempdir()
    temp_file = os.path.join(temp_dir, f"clipown_dl_{uuid.uuid4().hex[:10]}.{ext}")
    
    with open(temp_file, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 128):
            if chunk:
                f.write(chunk)
                
    return temp_file

class NoAudioStreamError(RuntimeError):
    """Raised when source media does not contain any audio stream to extract."""
    pass

def mux_video_audio(video_url: str, audio_url: str) -> str:
    """
    Muxes a video stream and audio stream into a single MP4 with stream copy in ~1-2 seconds.
    First attempts direct URL streaming via FFmpeg. If that fails, downloads temp files and muxes.
    """
    ffmpeg_bin = ensure_ffmpeg()
    temp_dir = tempfile.gettempdir()
    out_file = os.path.join(temp_dir, f"clipown_mux_{uuid.uuid4().hex[:10]}.mp4")
    
    headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36\r\n"
    
    # Try direct URL mux first (fastest, stream copy)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-headers", headers,
        "-i", video_url,
        "-headers", headers,
        "-i", audio_url,
        "-map", "0:v:0",
        "-map", "1:a?",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        "-movflags", "+faststart",
        out_file
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
        return out_file
        
    # Fallback: Download both streams and mux locally
    temp_v = None
    temp_a = None
    try:
        temp_v = download_stream_chunked(video_url, "mp4")
        temp_a = download_stream_chunked(audio_url, "m4a")
        
        fallback_cmd = [
            ffmpeg_bin,
            "-y",
            "-i", temp_v,
            "-i", temp_a,
            "-map", "0:v:0",
            "-map", "1:a?",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            "-movflags", "+faststart",
            out_file
        ]
        res_fb = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_fb.returncode != 0 or not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
            err = res_fb.stderr if res_fb.stderr else 'Mux error'
            raise RuntimeError(f"FFmpeg muxing failed: {err[-400:]}")
        return out_file
    finally:
        if temp_v and temp_v != video_url and os.path.exists(temp_v):
            try:
                os.remove(temp_v)
            except OSError:
                pass
        if temp_a and temp_a != audio_url and os.path.exists(temp_a):
            try:
                os.remove(temp_a)
            except OSError:
                pass

def extract_mp3_audio(source_url: str) -> str:
    """
    Extracts audio from video or audio stream and encodes it to authentic high-bitrate MP3.
    """
    ffmpeg_bin = ensure_ffmpeg()
    temp_dir = tempfile.gettempdir()
    out_file = os.path.join(temp_dir, f"clipown_audio_{uuid.uuid4().hex[:10]}.mp3")
    
    headers = "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36\r\n"
    
    # Try direct URL conversion first
    cmd = [
        ffmpeg_bin,
        "-y",
        "-headers", headers,
        "-i", source_url,
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        out_file
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
        return out_file
        
    # Check if direct run failed specifically because input has no audio stream
    if res.stderr and "does not contain any stream" in res.stderr.lower():
        raise NoAudioStreamError("The source media does not contain an audio stream.")

    # Fallback: download source to temp file and extract MP3
    temp_src = None
    try:
        temp_src = download_stream_chunked(source_url, "mp4")
        fallback_cmd = [
            ffmpeg_bin,
            "-y",
            "-i", temp_src,
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            out_file
        ]
        res_fb = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res_fb.returncode != 0 or not os.path.exists(out_file) or os.path.getsize(out_file) == 0:
            err = res_fb.stderr if res_fb.stderr else 'Extract error'
            if "does not contain any stream" in err.lower():
                raise NoAudioStreamError("The source media does not contain an audio stream.")
            raise RuntimeError(f"FFmpeg MP3 extraction failed: {err[-400:]}")
        return out_file
    finally:
        if temp_src and temp_src != source_url and os.path.exists(temp_src):
            try:
                os.remove(temp_src)
            except OSError:
                pass
