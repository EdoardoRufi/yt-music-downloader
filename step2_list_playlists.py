"""Step 2: connect to your YouTube account (via cookies) and list your playlists.

Lists the playlists in your library (created or saved, public and private) plus
"Liked videos", with the number of tracks in each. Playlists selected in PLAYLISTS
(.env) are marked with "*". Nothing is downloaded.

Usage:
    python step2_list_playlists.py              # whole library, with track counts
    python step2_list_playlists.py --selected   # only the playlists in PLAYLISTS
    python step2_list_playlists.py --fast       # skip track counts (one request only)
    python step2_list_playlists.py --json       # machine-readable output
"""

import argparse
import json
import sys
import time

from config import load_settings
from ytcommon import (
    fetch_tracks,
    is_unavailable,
    list_my_playlists,
    require_cookies,
    selected_playlists,
)

TITLE_WIDTH = 45


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--selected", action="store_true", help="only playlists in PLAYLISTS")
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
    if args.selected:
        playlists = selected_playlists(settings)  # exits if PLAYLISTS is empty
    else:
        playlists = list_my_playlists(settings)
        # Selected playlists that are not in your library (e.g. someone else's) go last.
        known = {p.id for p in playlists}
        if settings.playlists:
            playlists += [p for p in selected_playlists(settings) if p.id not in known]
    selected_ids = {p.id for p in selected_playlists(settings)} if settings.playlists else set()

    # Titles of selected playlists outside the library are only known after fetching.
    for i, playlist in enumerate(playlists, 1):
        if args.fast and playlist.title != playlist.id:
            continue
        if not args.json:
            print(f"  [{i}/{len(playlists)}] reading: {playlist.title}", flush=True)
        fetch_tracks(settings, playlist)
    elapsed = time.perf_counter() - start

    if args.json:
        output = [
            {
                "id": p.id,
                "title": p.title,
                "url": p.url,
                "selected": p.id in selected_ids,
                "track_count": None if args.fast or p.error else len(p.tracks),
                "unavailable_count": sum(map(is_unavailable, p.tracks)),
                "error": p.error,
            }
            for p in playlists
        ]
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return

    print()
    print(f"{'#':>3}  {'Sel':^3}  {'Title':<{TITLE_WIDTH}}  {'Tracks':>6}  {'Unavail.':>8}  Id")
    print("-" * (TITLE_WIDTH + 45))
    total = unavailable_total = 0
    for i, p in enumerate(playlists, 1):
        title = p.title if len(p.title) <= TITLE_WIDTH else p.title[: TITLE_WIDTH - 1] + "…"
        mark = "*" if p.id in selected_ids else ""
        if p.error:
            count, unavailable = "ERROR", "-"
        elif args.fast:
            count = unavailable = "-"
        else:
            unavailable_n = sum(map(is_unavailable, p.tracks))
            total += len(p.tracks)
            unavailable_total += unavailable_n
            count, unavailable = len(p.tracks), unavailable_n
        print(f"{i:>3}  {mark:^3}  {title:<{TITLE_WIDTH}}  {count:>6}  {unavailable:>8}  {p.id}")
    print("-" * (TITLE_WIDTH + 45))

    print(f"{len(playlists)} playlists", end="")
    if not args.fast:
        print(f", {total} tracks ({unavailable_total} private/deleted, will be skipped)", end="")
    print(f" - read in {elapsed:.1f}s")

    for p in playlists:
        if p.error:
            print(f"\n[error] {p.title} ({p.id}): {p.error}")

    if not selected_ids:
        print(
            "\nNo playlists selected yet. Copy the ids you want from the 'Id' column into "
            "PLAYLISTS in .env, e.g.\nPLAYLISTS=PLxxxxxxxxxxxxxxxx, LL"
        )
    else:
        print(f"\n{len(selected_ids)} playlists selected in PLAYLISTS (marked with *).")


if __name__ == "__main__":
    main()
