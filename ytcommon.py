"""yt-dlp helpers shared by every step."""

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp
from yt_dlp.utils import sanitize_filename

from config import Settings

# Video id in brackets lets later steps map files back to YouTube ids
# without relying on any database.
OUTPUT_TEMPLATE = "%(title)s [%(id)s].%(ext)s"

# Your library: playlists you created or saved, public and private (needs cookies).
FEED_PLAYLISTS_URL = "https://www.youtube.com/feed/playlists"
LIKED_PLAYLIST_ID = "LL"

# Cookies that only exist when you are logged in to a Google account.
_LOGIN_COOKIES = ("SAPISID", "__Secure-3PAPISID", "LOGIN_INFO")

# Placeholder titles YouTube uses for entries that can't be downloaded.
_UNAVAILABLE_TITLES = ("[Private video]", "[Deleted video]", "[Unavailable video]")


@dataclass
class Playlist:
    id: str
    title: str
    url: str
    tracks: list[dict] = field(default_factory=list)  # flat entries: id, title, duration...
    error: str | None = None


def playlist_url(playlist_id_or_url: str) -> str:
    if playlist_id_or_url.startswith(("http://", "https://")):
        return playlist_id_or_url
    return f"https://www.youtube.com/playlist?list={playlist_id_or_url}"


def playlist_id_from_url(url: str) -> str | None:
    return (parse_qs(urlparse(url).query).get("list") or [None])[0]


def is_unavailable(entry: dict) -> bool:
    return entry.get("title") in _UNAVAILABLE_TITLES


def track_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


# "Some title [dQw4w9WgXcQ].mp3" -> "dQw4w9WgXcQ" (see OUTPUT_TEMPLATE)
_TRACK_FILE_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]\.mp3$")

# Names Windows refuses as file/folder names, whatever the extension.
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{i}" for p in ("COM", "LPT") for i in range(1, 10)}


def existing_tracks(folder: Path) -> dict[str, Path]:
    """Video id -> MP3 file, for the MP3s already in a playlist folder."""
    if not folder.is_dir():
        return {}
    tracks = {}
    for file in folder.glob("*.mp3"):
        match = _TRACK_FILE_RE.search(file.name)
        if match:
            tracks[match.group(1)] = file
    return tracks


def safe_folder_name(title: str, fallback: str) -> str:
    """Playlist title turned into a valid Windows folder name."""
    name = sanitize_filename(title).strip().rstrip(". ")
    if not name:
        return fallback
    if name.split(".")[0].upper() in _WINDOWS_RESERVED:
        name += "_"
    return name


class CollectingLogger:
    """yt-dlp logger: hides the chatter, prints warnings, remembers the last error."""

    def __init__(self) -> None:
        self.last_error: str | None = None

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        print(f"      [warning] {msg.removeprefix('WARNING: ')}")

    def error(self, msg: str) -> None:
        self.last_error = msg.removeprefix("ERROR: ")


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
        "paths": {"home": str(dest_dir)},
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


def require_cookies(settings: Settings) -> Path:
    """Return the cookies file, or exit explaining how to create it."""
    path = settings.cookies_file
    if path is None:
        raise SystemExit(
            f"[error] Cookies file not found: {settings.cookies_path}\n"
            "Export it from your browser (see README, step 2) or fix YT_COOKIES in .env."
        )
    text = path.read_text(encoding="utf-8", errors="replace")
    if "youtube.com" not in text:
        raise SystemExit(
            f"[error] {path} contains no youtube.com cookies. Export them while on youtube.com."
        )
    if not any(name in text for name in _LOGIN_COOKIES):
        print(
            "[warning] The cookies file has no login cookies: were you logged in to YouTube "
            "when you exported it? Private playlists and Liked videos won't be visible."
        )
    return path


def _flat_opts(settings: Settings) -> dict:
    """Options to read lists (playlists, tracks) without downloading anything."""
    opts: dict = {
        "extract_flat": "in_playlist",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 10,
    }
    if settings.cookies_file:
        opts["cookiefile"] = str(settings.cookies_file)
    return opts


def list_my_playlists(settings: Settings) -> list[Playlist]:
    """All playlists of the logged-in account plus Liked videos (tracks not fetched)."""
    with yt_dlp.YoutubeDL(_flat_opts(settings)) as ydl:
        try:
            info = ydl.extract_info(FEED_PLAYLISTS_URL, download=False)
        except yt_dlp.utils.DownloadError as e:
            raise SystemExit(
                f"[error] Could not read your playlists: {e}\n"
                "Your cookies are probably expired: export them again (README, step 2)."
            )

    playlists: dict[str, Playlist] = {}
    for entry in (info or {}).get("entries") or []:
        if not entry:
            continue
        url = entry.get("url") or ""
        pl_id = playlist_id_from_url(url) or (
            entry.get("id") if entry.get("ie_key") == "YoutubeTab" else None
        )
        if not pl_id:
            continue  # not a playlist (e.g. a stray video in the feed)
        playlists[pl_id] = Playlist(
            id=pl_id, title=entry.get("title") or pl_id, url=playlist_url(pl_id)
        )

    if not playlists:
        print(
            "[warning] Your library returned no playlists. Either you have none, or the "
            "cookies are not logged in / expired (README, step 2)."
        )

    playlists.setdefault(
        LIKED_PLAYLIST_ID,
        Playlist(id=LIKED_PLAYLIST_ID, title="Liked videos", url=playlist_url(LIKED_PLAYLIST_ID)),
    )
    return list(playlists.values())


def selected_playlists(settings: Settings) -> list[Playlist]:
    """Playlists listed in PLAYLISTS (.env), in that order. Exits if the list is empty.

    Titles are just the ids until fetch_tracks() fills them in.
    """
    if not settings.playlists:
        raise SystemExit(
            "[error] No playlists selected: PLAYLISTS in .env is empty.\n"
            "Run 'python step2_list_playlists.py' to see your playlist ids, then set e.g.\n"
            "PLAYLISTS=PLxxxxxxxxxxxxxxxx, LL"
        )
    playlists: dict[str, Playlist] = {}
    for item in settings.playlists:
        pl_id = playlist_id_from_url(playlist_url(item))
        if not pl_id:
            raise SystemExit(f"[error] PLAYLISTS: '{item}' is not a playlist id or URL.")
        playlists.setdefault(pl_id, Playlist(id=pl_id, title=pl_id, url=playlist_url(pl_id)))
    return list(playlists.values())


def fetch_tracks(settings: Settings, playlist: Playlist) -> Playlist:
    """Fill playlist.tracks (flat entries, no download). Errors are stored, not raised."""
    with yt_dlp.YoutubeDL(_flat_opts(settings)) as ydl:
        try:
            info = ydl.extract_info(playlist.url, download=False)
        except yt_dlp.utils.DownloadError as e:
            playlist.error = str(e)
            return playlist
    info = info or {}
    if playlist.title == playlist.id and info.get("title"):
        playlist.title = info["title"]  # extra playlists only have their id as title
    playlist.tracks = [e for e in info.get("entries") or [] if e and e.get("id")]
    return playlist
