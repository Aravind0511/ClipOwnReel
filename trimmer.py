"""
ClipOwn - Media Trimming Engine
Uses FFmpeg to cut and export Instagram video and audio clips with frame accuracy.
"""

import os
import subprocess
import tempfile
import uuid
import requests
import imageio_ffmpeg

def get_ffmpeg_path() -> str:
    """Returns the absolute path to the bundled FFmpeg executable."""
    return imageio_ffmpeg.get_ffmpeg_exe()

def download_source_to_temp(url: str) -> str:
    """
    Downloads media from URL into a temporary file using Instagram-compatible headers.
    """
    if os.path.exists(url):
        return url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
        "Accept": "*/*",
    }
    
    resp = requests.get(url, stream=True, timeout=30, headers=headers)
    resp.raise_for_status()

    temp_dir = tempfile.gettempdir()
    temp_input_path = os.path.join(temp_dir, f"clipown_in_{uuid.uuid4().hex[:10]}.mp4")
    
    with open(temp_input_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=1024 * 128):
            if chunk:
                f.write(chunk)
                
    return temp_input_path

def trim_media(
    source_url: str,
    start_time: float,
    end_time: float,
    media_type: str = "video"
) -> str:
    """
    Trims media between start_time and end_time (in seconds).
    
    Args:
        source_url: Direct stream URL or local filepath
        start_time: Start timestamp in seconds
        end_time: End timestamp in seconds
        media_type: 'video' (outputs MP4 with audio) or 'audio' (outputs MP3)
        
    Returns:
        Absolute filepath to the generated temporary file.
    """
    ffmpeg_bin = get_ffmpeg_path()
    if not os.path.exists(ffmpeg_bin):
        raise FileNotFoundError(f"FFmpeg binary not found at: {ffmpeg_bin}")

    # Validate timestamps
    start_time = max(0.0, float(start_time))
    end_time = float(end_time)
    if end_time <= start_time:
        end_time = start_time + 1.0  # minimum 1 second
    
    duration = end_time - start_time

    # Download source to temp file
    temp_input = download_source_to_temp(source_url)
    
    temp_dir = tempfile.gettempdir()
    ext = "mp4" if media_type == "video" else "mp3"
    temp_output = os.path.join(temp_dir, f"clipown_trim_{uuid.uuid4().hex[:10]}.{ext}")

    try:
        if media_type == "video":
            # Trim both video and audio with ultrafast H.264 + AAC
            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss", f"{start_time:.3f}",
                "-i", temp_input,
                "-t", f"{duration:.3f}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                temp_output
            ]
        else:
            # Trim audio only and output high-bitrate MP3
            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss", f"{start_time:.3f}",
                "-i", temp_input,
                "-t", f"{duration:.3f}",
                "-vn",
                "-c:a", "libmp3lame",
                "-b:a", "192k",
                temp_output
            ]

        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if process.returncode != 0:
            raise RuntimeError(f"FFmpeg processing error: {process.stderr[-500:] if process.stderr else 'Unknown error'}")

        if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
            raise RuntimeError("FFmpeg generated an empty trimmed file.")

        return temp_output

    finally:
        # Clean up temporary input file if it was downloaded
        if temp_input != source_url and os.path.exists(temp_input):
            try:
                os.remove(temp_input)
            except OSError:
                pass
