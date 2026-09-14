"""
ClipOwn - Media Trimming Engine
Uses FFmpeg to cut and export Instagram video and audio clips with frame accuracy.
"""

import os
import subprocess
import tempfile
import uuid
import requests
from ffmpeg_utils import ensure_ffmpeg

def get_ffmpeg_path() -> str:
    """Returns the absolute path to the configured FFmpeg executable."""
    return ensure_ffmpeg()

def download_source_to_temp(url: str) -> str:
    """
    Downloads media from URL into a temporary file using Instagram-compatible headers.
    """
    if os.path.exists(url):
        return url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
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
    media_type: str = "video",
    audio_url: str = None
) -> str:
    """
    Trims media between start_time and end_time (in seconds).
    
    Args:
        source_url: Direct stream URL or local filepath
        start_time: Start timestamp in seconds
        end_time: End timestamp in seconds
        media_type: 'video' (outputs MP4 with audio) or 'audio' (outputs MP3)
        audio_url: Optional separate audio stream URL for DASH streams
        
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
    temp_input = None
    temp_audio = None
    
    temp_dir = tempfile.gettempdir()
    ext = "mp4" if media_type == "video" else "mp3"
    temp_output = os.path.join(temp_dir, f"clipown_trim_{uuid.uuid4().hex[:10]}.{ext}")

    try:
        if media_type == "video":
            temp_input = download_source_to_temp(source_url)
            
            if audio_url and audio_url.strip():
                temp_audio = download_source_to_temp(audio_url.strip())
                cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-ss", f"{start_time:.3f}",
                    "-i", temp_input,
                    "-ss", f"{start_time:.3f}",
                    "-i", temp_audio,
                    "-t", f"{duration:.3f}",
                    "-map", "0:v:0",
                    "-map", "1:a?",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "22",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    "-movflags", "+faststart",
                    temp_output
                ]
            else:
                # Video with embedded progressive audio (or video only if audio withheld)
                cmd = [
                    ffmpeg_bin,
                    "-y",
                    "-ss", f"{start_time:.3f}",
                    "-i", temp_input,
                    "-t", f"{duration:.3f}",
                    "-map", "0:v:0",
                    "-map", "0:a?",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "22",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-movflags", "+faststart",
                    temp_output
                ]
        else:
            # Audio only
            target_audio_url = audio_url.strip() if (audio_url and audio_url.strip()) else source_url
            temp_input = download_source_to_temp(target_audio_url)
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
            err = process.stderr if process.stderr else "Unknown error"
            if "does not contain any stream" in err.lower():
                raise RuntimeError("The source media does not contain an audio stream.")
            raise RuntimeError(f"FFmpeg processing error: {err[-400:]}")

        if not os.path.exists(temp_output) or os.path.getsize(temp_output) == 0:
            raise RuntimeError("FFmpeg generated an empty trimmed file.")

        return temp_output

    finally:
        # Clean up temporary input files
        if temp_input and temp_input != source_url and os.path.exists(temp_input):
            try:
                os.remove(temp_input)
            except OSError:
                pass
        if temp_audio and temp_audio != audio_url and os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except OSError:
                pass
