"""Loads settings from the .env file (or real environment variables)."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
STATE_DIR = PROJECT_DIR / "state"

load_dotenv(PROJECT_DIR / ".env")


def _path(value: str) -> Path:
    """Resolve a path from .env; relative paths are relative to the project folder."""
    p = Path(os.path.expandvars(value)).expanduser()
    return p if p.is_absolute() else (PROJECT_DIR / p).resolve()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"[config] {name} must be an integer, got '{raw}'")


@dataclass(frozen=True)
class Settings:
    download_dir: Path
    cookies_file: Path | None  # None when the file does not exist
    audio_quality: int
    sleep_min: int
    sleep_max: int
    ffmpeg_location: str | None


def load_settings() -> Settings:
    cookies = _path(os.getenv("YT_COOKIES", "./cookies.txt").strip() or "./cookies.txt")
    sleep_min = _int("SLEEP_MIN", 2)
    sleep_max = max(_int("SLEEP_MAX", 6), sleep_min)
    return Settings(
        download_dir=_path(os.getenv("DOWNLOAD_DIR", "./downloads").strip() or "./downloads"),
        cookies_file=cookies if cookies.is_file() else None,
        audio_quality=_int("AUDIO_QUALITY", 192),
        sleep_min=sleep_min,
        sleep_max=sleep_max,
        ffmpeg_location=os.getenv("FFMPEG_LOCATION", "").strip() or None,
    )
