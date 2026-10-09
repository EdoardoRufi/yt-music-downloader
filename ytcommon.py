"""yt-dlp helpers shared by every step."""

import shutil
from pathlib import Path

from config import Settings

# Video id in brackets lets later steps map files back to YouTube ids
# without relying on any database.
OUTPUT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"


def check_dependencies(settings: Settings) -> None:
    """Fail fast with a readable message if external tools are missing."""
    ffmpeg_dir = settings.ffmpeg_location
    ffmpeg_found = (
        Path(ffmpeg_dir, "ffmpeg.exe").is_file() or Path(ffmpeg_dir, "ffmpeg").is_file()
        if ffmpeg_dir
        else shutil.which("ffmpeg") is not None
    )
    if not ffmpeg_found:
        raise SystemExit(
            "[error] ffmpeg not found. Install it (see README, step 0) and reopen the "
            "terminal, or set FFMPEG_LOCATION in .env."
        )
    if shutil.which("deno") is None:
        print(
            "[warning] deno not found on PATH. YouTube downloads may fail or offer fewer "
            "formats. Install it (see README, step 0) and reopen the terminal."
        )


def build_ydl_opts(
    settings: Settings,
    dest_dir: Path,
    *,
    use_cookies: bool = True,
    ignore_errors: bool = True,
) -> dict:
    """Options for downloading audio as MP3 with metadata and embedded cover art."""
    opts: dict = {
        "format": "bestaudio/best",
        "paths": {"home": str(dest_dir), "temp": str(dest_dir / ".tmp")},
        "outtmpl": OUTPUT_TEMPLATE,
        "windowsfilenames": True,
        "writethumbnail": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": str(settings.audio_quality),
            },
            # YouTube thumbnails are often WebP, which MP3 players don't show: convert first.
            {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False},
        ],
        "ignoreerrors": ignore_errors,
        "retries": 10,
        "fragment_retries": 10,
        "sleep_interval": settings.sleep_min,
        "max_sleep_interval": settings.sleep_max,
    }
    if settings.ffmpeg_location:
        opts["ffmpeg_location"] = settings.ffmpeg_location
    if use_cookies and settings.cookies_file:
        opts["cookiefile"] = str(settings.cookies_file)
    return opts


def final_filepath(info: dict | None) -> Path | None:
    """Path of the file produced by yt-dlp after post-processing (the .mp3)."""
    if not info:
        return None
    for download in info.get("requested_downloads") or []:
        if download.get("filepath"):
            return Path(download["filepath"])
    return Path(info["filepath"]) if info.get("filepath") else None
