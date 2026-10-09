"""List the albums, EPs and singles of an artist, with their ids.

Reads the artist's "Releases" tab. Releases already selected in ARTIST_RELEASES
(.env) are marked with "*". Nothing is downloaded.

Usage:
    python artist_list_releases.py "https://music.youtube.com/channel/UCxxxxxxxx"
    python artist_list_releases.py "https://www.youtube.com/@ArtistName"
    python artist_list_releases.py <artist link> --fast    # skip track counts
"""

import argparse
import sys
import time

from config import load_settings
from ytcommon import fetch_tracks, list_artist_releases, playlists_from_ids, release_kind

TITLE_WIDTH = 50


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist_url", help="link to the artist page (YouTube or YouTube Music)")
    parser.add_argument("--fast", action="store_true", help="don't count tracks (one request only)")
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")  # titles with characters the console can't print

    settings = load_settings()
    selected_ids = {p.id for p in playlists_from_ids(settings.artist_releases, "ARTIST_RELEASES")}

    print("Reading the artist's releases...")
    start = time.perf_counter()
    artist, releases = list_artist_releases(settings, args.artist_url)
    if not releases:
        raise SystemExit(f"[error] No releases found for {artist}. Is this the artist's page?")

    if not args.fast:
        for i, release in enumerate(releases, 1):
            print(f"  [{i}/{len(releases)}] counting tracks: {release.title}", flush=True)
            fetch_tracks(settings, release)
    elapsed = time.perf_counter() - start

    print(f"\nArtist: {artist}\n")
    print(f"{'#':>3}  {'Sel':^3}  {'Type':<6}  {'Title':<{TITLE_WIDTH}}  {'Tracks':>6}  Id")
    print("-" * (TITLE_WIDTH + 70))
    for i, r in enumerate(releases, 1):
        title = r.title if len(r.title) <= TITLE_WIDTH else r.title[: TITLE_WIDTH - 1] + "…"
        mark = "*" if r.id in selected_ids else ""
        if args.fast:
            kind, count = "?", "-"
        elif r.error:
            kind, count = "?", "ERROR"
        else:
            kind, count = release_kind(len(r.tracks)), len(r.tracks)
        print(f"{i:>3}  {mark:^3}  {kind:<6}  {title:<{TITLE_WIDTH}}  {count:>6}  {r.id}")
    print("-" * (TITLE_WIDTH + 70))
    print(f"{len(releases)} releases - read in {elapsed:.1f}s")
    if not args.fast:
        print("Type is a guess from the track count: 1-3 Single, 4-6 EP, 7+ Album.")

    for r in releases:
        if r.error:
            print(f"\n[error] {r.title} ({r.id}): {r.error}")

    missing = selected_ids - {r.id for r in releases}
    if missing:
        print(f"\n[note] In ARTIST_RELEASES but not by this artist: {', '.join(sorted(missing))}")
    if not selected_ids & {r.id for r in releases}:
        print(
            "\nNo release of this artist selected yet. Copy the ids you want from the 'Id' "
            "column into ARTIST_RELEASES in .env, e.g.\nARTIST_RELEASES=OLAK5uy_xxxx..., OLAK5uy_yyyy..."
        )


if __name__ == "__main__":
    main()
