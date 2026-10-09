"""Step 2: connect to your YouTube account (via cookies) and list your playlists.

Lists the playlists in your library (created or saved, public and private) plus
"Liked videos", with the number of tracks in each. Nothing is downloaded.

Usage:
    python step2_list_playlists.py            # table with track counts
    python step2_list_playlists.py --fast     # skip track counts (one request only)
    python step2_list_playlists.py --json     # machine-readable output
"""

import argparse
import json
import sys
import time

from config import load_settings
from ytcommon import fetch_tracks, is_unavailable, list_my_playlists, require_cookies

TITLE_WIDTH = 45


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fast", action="store_true", help="don't count tracks")
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args()

    # Playlist titles may contain characters the Windows console can't print.
    sys.stdout.reconfigure(errors="replace")

    settings = load_settings()
    cookies = require_cookies(settings)
    if not args.json:
        print(f"Cookies: {cookies}")
        print("Reading your playlists...")

    start = time.perf_counter()
    playlists = list_my_playlists(settings)
    if not args.fast:
        for i, playlist in enumerate(playlists, 1):
            if not args.json:
                print(f"  [{i}/{len(playlists)}] counting tracks: {playlist.title}", flush=True)
            fetch_tracks(settings, playlist)
    elapsed = time.perf_counter() - start

    if args.json:
        output = [
            {
                "id": p.id,
                "title": p.title,
                "url": p.url,
                "track_count": None if args.fast or p.error else len(p.tracks),
                "unavailable_count": sum(map(is_unavailable, p.tracks)),
                "error": p.error,
            }
            for p in playlists
        ]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    print()
    print(f"{'#':>3}  {'Title':<{TITLE_WIDTH}}  {'Tracks':>6}  {'Unavail.':>8}  Id")
    print("-" * (TITLE_WIDTH + 40))
    total = unavailable_total = 0
    for i, p in enumerate(playlists, 1):
        title = p.title if len(p.title) <= TITLE_WIDTH else p.title[: TITLE_WIDTH - 1] + "…"
        if args.fast:
            count = unavailable = "-"
        elif p.error:
            count, unavailable = "ERROR", "-"
        else:
            unavailable_n = sum(map(is_unavailable, p.tracks))
            total += len(p.tracks)
            unavailable_total += unavailable_n
            count, unavailable = len(p.tracks), unavailable_n
        print(f"{i:>3}  {title:<{TITLE_WIDTH}}  {count:>6}  {unavailable:>8}  {p.id}")
    print("-" * (TITLE_WIDTH + 40))

    print(f"{len(playlists)} playlists", end="")
    if not args.fast:
        print(f", {total} tracks ({unavailable_total} private/deleted, will be skipped)", end="")
    print(f" - read in {elapsed:.1f}s")

    for p in playlists:
        if p.error:
            print(f"\n[error] {p.title} ({p.id}): {p.error}")


if __name__ == "__main__":
    main()
