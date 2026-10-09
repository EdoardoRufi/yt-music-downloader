"""Artist discography from YouTube Music (via ytmusicapi).

yt-dlp can't read YouTube Music artist pages: on YouTube, many artists only have an
auto-generated "- Topic" channel with no Releases/Playlists tab. ytmusicapi reads the
discography the way the YouTube Music website does, including the real release type
(Album / EP / Single). Downloading is still done by yt-dlp, through each release's
playlist id (OLAK5uy_...).
"""

from dataclasses import dataclass
from urllib.parse import urlparse

import yt_dlp
from ytmusicapi import YTMusic

# Discography sections of an artist page on YouTube Music.
_SECTIONS = ("albums", "singles")


@dataclass
class Release:
    browse_id: str  # YouTube Music album id (MPREb_...)
    title: str
    kind: str  # Album / EP / Single, as YouTube Music says
    year: str
    id: str | None = None  # playlist id (OLAK5uy_...), what ARTIST_RELEASES contains
    track_count: int | None = None
    error: str | None = None


def artist_channel_id(artist_url: str) -> str:
    """Channel id (UC...) from an artist link (YouTube Music or YouTube)."""
    parsed = urlparse(artist_url.strip())
    parts = [p for p in parsed.path.split("/") if p]
    if not parsed.netloc.endswith("youtube.com") or not parts:
        raise SystemExit(
            f"[error] '{artist_url}' is not an artist link. Use the artist page URL, e.g.\n"
            "  https://music.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"
        )
    if parts[0] in ("channel", "browse") and len(parts) >= 2 and parts[1].startswith("UC"):
        return parts[1]

    # @handle, /c/name, /user/name: ask YouTube which channel it is.
    opts = {"extract_flat": True, "playlistend": 1, "quiet": True, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(artist_url, download=False) or {}
    except yt_dlp.utils.DownloadError as e:
        raise SystemExit(f"[error] Could not open {artist_url}: {e}")
    channel_id = info.get("channel_id")
    if not channel_id:
        raise SystemExit(f"[error] Could not find the channel of {artist_url}.")
    return channel_id


def list_releases(
    artist_url: str, wanted_ids: set[str] | None = None, progress: bool = True
) -> tuple[str, list[Release]]:
    """(artist name, releases) newest first, albums before singles/EPs.

    Each release needs one extra request to get its playlist id. If wanted_ids is
    given, that stops as soon as all of them have been found (faster downloads).
    """
    channel_id = artist_channel_id(artist_url)
    yt = YTMusic()
    try:
        artist = yt.get_artist(channel_id)
    except Exception as e:  # ytmusicapi raises plain exceptions for unknown channels
        raise SystemExit(
            f"[error] YouTube Music has no artist page for channel {channel_id}: {e}\n"
            "Open the artist on https://music.youtube.com (search, then click the artist "
            "name) and use that link."
        )
    name = artist.get("name") or "Unknown artist"

    releases: list[Release] = []
    for section in _SECTIONS:
        info = artist.get(section) or {}
        items = info.get("results") or []
        # The artist page only previews ~10 releases per section; "params" fetches all.
        if info.get("browseId") and info.get("params"):
            try:
                items = yt.get_artist_albums(info["browseId"], info["params"], limit=None)
            except Exception as e:
                print(f"[warning] Could not read all {section}, showing the preview only: {e}")
        for item in items:
            if item.get("browseId"):
                releases.append(
                    Release(
                        browse_id=item["browseId"],
                        title=item.get("title") or item["browseId"],
                        kind=item.get("type") or ("Album" if section == "albums" else "Single"),
                        year=str(item.get("year") or ""),
                        id=item.get("audioPlaylistId"),
                    )
                )

    remaining = set(wanted_ids) if wanted_ids else None
    for i, release in enumerate(releases, 1):
        if remaining is not None and not remaining:
            break
        if progress:
            print(f"  [{i}/{len(releases)}] {release.title}", flush=True)
        try:
            album = yt.get_album(release.browse_id)
        except Exception as e:
            release.error = str(e)
            continue
        release.id = album.get("audioPlaylistId") or release.id
        release.track_count = album.get("trackCount")
        release.kind = album.get("type") or release.kind
        if remaining is not None:
            remaining.discard(release.id)
    return name, releases
