"""List the albums, EPs and singles of an artist, with their ids.

Reads the artist's discography from YouTube Music. Releases already selected in
ARTIST_RELEASES (.env) are marked with "*". Nothing is downloaded.

Usage:
    python artist_list_releases.py "https://music.youtube.com/channel/UCxxxxxxxx"
    python artist_list_releases.py "https://www.youtube.com/@ArtistName"
"""

import argparse
import sys
import time

from config import load_settings
from ytcommon import playlists_from_ids
from ytmusic import list_releases

TITLE_WIDTH = 45


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist_url", help="link to the artist page (YouTube Music or YouTube)")
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")  # titles with characters the console can't print

    settings = load_settings()
    selected_ids = {p.id for p in playlists_from_ids(settings.artist_releases, "ARTIST_RELEASES")}

    print("Reading the artist's discography from YouTube Music...")
    start = time.perf_counter()
    artist, releases = list_releases(args.artist_url)
    elapsed = time.perf_counter() - start
    if not releases:
        raise SystemExit(f"[error] YouTube Music lists no albums, EPs or singles for {artist}.")

    print(f"\nArtist: {artist}\n")
    print(f"{'#':>3}  {'Sel':^3}  {'Type':<6}  {'Year':<4}  {'Title':<{TITLE_WIDTH}}  {'Tracks':>6}  Id")
    print("-" * (TITLE_WIDTH + 80))
    for i, r in enumerate(releases, 1):
        title = r.title if len(r.title) <= TITLE_WIDTH else r.title[: TITLE_WIDTH - 1] + "…"
        mark = "*" if r.id in selected_ids else ""
        count = "ERROR" if r.error else (r.track_count if r.track_count is not None else "?")
        print(
            f"{i:>3}  {mark:^3}  {r.kind:<6}  {r.year:<4}  {title:<{TITLE_WIDTH}}  {count:>6}  "
            f"{r.id or '(no id)'}"
        )
    print("-" * (TITLE_WIDTH + 80))
    kinds = {k: sum(r.kind == k for r in releases) for k in ("Album", "EP", "Single")}
    print(
        f"{len(releases)} releases ({kinds['Album']} albums, {kinds['EP']} EPs, "
        f"{kinds['Single']} singles) - read in {elapsed:.1f}s"
    )

    for r in releases:
        if r.error:
            print(f"\n[error] {r.title}: {r.error}")

    found = {r.id for r in releases}
    missing = selected_ids - found
    if missing:
        print(f"\n[note] In ARTIST_RELEASES but not by this artist: {', '.join(sorted(missing))}")
    if not selected_ids & found:
        print(
            "\nNo release of this artist selected yet. Copy the ids you want from the 'Id' "
            "column into ARTIST_RELEASES in .env, e.g.\nARTIST_RELEASES=OLAK5uy_xxxx..., OLAK5uy_yyyy..."
        )


if __name__ == "__main__":
    main()
