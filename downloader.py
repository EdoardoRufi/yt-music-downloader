"""Playlist download loop shared by step 3 (full download) and step 4 (sync)."""

import time
from pathlib import Path

import yt_dlp

from config import Settings
from ytcommon import (
    ALBUM_OUTPUT_TEMPLATE,
    CollectingLogger,
    Playlist,
    build_ydl_opts,
    existing_tracks,
    is_unavailable,
    safe_folder_name,
    track_url,
)


def fmt_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


class FolderNamer:
    """Gives each playlist a unique folder name (two playlists may share a title)."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def name_for(self, playlist: Playlist) -> str:
        name = safe_folder_name(playlist.title, playlist.id)
        if name.lower() in self._used:
            name = f"{name} [{playlist.id}]"
        self._used.add(name.lower())
        return name


def new_stats(playlist: Playlist, folder: Path | None = None) -> dict:
    return {
        "id": playlist.id,
        "title": playlist.title,
        "folder": str(folder) if folder else None,
        "tracks": len(playlist.tracks),
        "downloaded": 0,
        "already_present": 0,
        "unavailable": 0,
        "failed": 0,
        "seconds": 0.0,
        "error": playlist.error,
        "failures": [],
    }


def download_playlist(
    settings: Settings,
    playlist: Playlist,
    folder: Path,
    label: str,
    stats: dict,
    *,
    limit: int | None = None,
    quiet_skips: bool = False,
    album_artist: str | None = None,
) -> None:
    """Download the playlist tracks missing from folder, updating stats in place.

    stats is filled as we go so that it is still valid after a Ctrl+C.
    quiet_skips hides the "already present" lines (useful when syncing).
    album_artist set = the playlist is an album: files are numbered ("01 - ...") and
    album/artist/track number are written in the MP3 tags when YouTube doesn't give them.
    """
    folder.mkdir(parents=True, exist_ok=True)
    present = existing_tracks(folder)
    tracks = playlist.tracks[:limit] if limit else playlist.tracks

    logger = CollectingLogger()
    opts = build_ydl_opts(settings, folder)
    opts.update({"logger": logger, "noplaylist": True, "noprogress": True})
    if album_artist:
        opts["outtmpl"] = ALBUM_OUTPUT_TEMPLATE
    digits = max(2, len(str(len(playlist.tracks))))

    start = time.perf_counter()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            for n, entry in enumerate(tracks, 1):
                video_id, title = entry["id"], entry.get("title") or entry["id"]
                prefix = f"  {label}[{n}/{len(tracks)}]"
                if video_id in present:
                    stats["already_present"] += 1
                    if not quiet_skips:
                        print(f"{prefix} already present: {title}")
                    continue
                if is_unavailable(entry):
                    stats["unavailable"] += 1
                    if not quiet_skips:
                        print(f"{prefix} skip (unavailable): {title}")
                    continue

                print(f"{prefix} {title} ...", end="", flush=True)
                logger.last_error = None
                track_start = time.perf_counter()
                # extra_info only fills fields YouTube left empty (it never overwrites).
                extra = None
                if album_artist:
                    extra = {
                        "track_prefix": f"{n:0{digits}d} - ",
                        "track_number": n,
                        "album": playlist.title,
                        "artist": album_artist,
                    }
                try:
                    ydl.extract_info(track_url(video_id), download=True, extra_info=extra)
                except yt_dlp.utils.DownloadError as e:  # normally swallowed by ignoreerrors
                    logger.last_error = str(e)
                took = time.perf_counter() - track_start

                # Success = the MP3 really exists (post-processing errors don't raise).
                mp3 = existing_tracks(folder).get(video_id)
                if mp3:
                    present[video_id] = mp3
                    stats["downloaded"] += 1
                    print(f" ok ({took:.1f}s)")
                else:
                    stats["failed"] += 1
                    reason = logger.last_error or "MP3 not created"
                    stats["failures"].append({"id": video_id, "title": title, "error": reason})
                    print(f" FAILED ({took:.1f}s)")
                    print(f"      {reason}")
    finally:
        stats["seconds"] = round(time.perf_counter() - start, 1)
