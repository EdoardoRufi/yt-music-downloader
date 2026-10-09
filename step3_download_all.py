"""Step 3: download every playlist in PLAYLISTS (.env) into its own folder, with timings.

Each playlist goes into DOWNLOAD_DIR/<playlist title>/. MP3s already present
(same video id in the file name) are skipped, so an interrupted run can simply be
restarted. At the end a timing report is printed and saved in state/.

Usage:
    python step3_download_all.py                      # all playlists in PLAYLISTS
    python step3_download_all.py --only PLxxxx        # just one of them (repeatable)
    python step3_download_all.py --limit 5            # first 5 tracks per playlist (quick test)
    python step3_download_all.py --dest D:\\Music\\new  # different destination than DOWNLOAD_DIR
"""

import argparse
import dataclasses
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from config import STATE_DIR, load_settings
from downloader import FolderNamer, download_playlist, fmt_duration, new_stats
from ytcommon import check_dependencies, fetch_tracks, require_cookies, selected_playlists

# Above this total, re-downloading everything every time is not worth it: use step 4.
FULL_REDOWNLOAD_MAX_SECONDS = 20 * 60


def print_report(results: list[dict], total_seconds: float) -> None:
    width = 32
    print()
    print(
        f"{'Playlist':<{width}}  {'Tracks':>6}  {'New':>5}  {'Had':>5}  {'Unav.':>5}  "
        f"{'Fail':>4}  {'Time':>8}  {'s/track':>7}"
    )
    print("-" * (width + 58))
    for r in results:
        title = r["title"] if len(r["title"]) <= width else r["title"][: width - 1] + "…"
        if r["error"]:
            print(f"{title:<{width}}  ERROR (see below)")
            continue
        per_track = f"{r['seconds'] / r['downloaded']:.1f}" if r["downloaded"] else "-"
        print(
            f"{title:<{width}}  {r['tracks']:>6}  {r['downloaded']:>5}  {r['already_present']:>5}  "
            f"{r['unavailable']:>5}  {r['failed']:>4}  {fmt_duration(r['seconds']):>8}  {per_track:>7}"
        )
    print("-" * (width + 58))
    print("New = downloaded now, Had = already in the folder, Unav. = private/deleted on YouTube")

    downloaded = sum(r["downloaded"] for r in results)
    downloadable = sum(r["tracks"] - r["unavailable"] for r in results)
    print(f"\nTotal: {downloaded} tracks downloaded in {fmt_duration(total_seconds)}")
    if not downloaded:
        return

    # Estimate of a from-scratch download of every selected track, to decide on step 4.
    per_track = sum(r["seconds"] for r in results) / downloaded
    estimate = per_track * downloadable
    print(f"Average: {per_track:.1f}s per track (including the anti-bot pause)")
    print(f"Estimated full download of all {downloadable} tracks: {fmt_duration(estimate)}")
    if estimate <= FULL_REDOWNLOAD_MAX_SECONDS:
        print("=> Re-downloading everything into a new folder each time is acceptable.")
    else:
        print("=> Too slow to re-download everything each time: the step 4 sync is worth it.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", action="append", metavar="ID", help="only this playlist id (repeatable)")
    parser.add_argument("--limit", type=int, metavar="N", help="download at most N tracks per playlist")
    parser.add_argument("--dest", type=Path, help="destination folder (overrides DOWNLOAD_DIR)")
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")  # titles with characters the console can't print

    settings = load_settings()
    if args.dest:
        settings = dataclasses.replace(settings, download_dir=args.dest.expanduser().resolve())
    check_dependencies(settings)
    require_cookies(settings)

    playlists = selected_playlists(settings)  # exits if PLAYLISTS is empty
    if args.only:
        unknown = set(args.only) - {p.id for p in playlists}
        if unknown:
            raise SystemExit(f"[error] --only: not in PLAYLISTS: {', '.join(sorted(unknown))}")
        playlists = [p for p in playlists if p.id in args.only]

    print(f"Destination: {settings.download_dir}")
    print(f"Playlists:   {len(playlists)}\n")

    results: list[dict] = []
    namer = FolderNamer()
    total_start = time.perf_counter()
    try:
        for i, playlist in enumerate(playlists, 1):
            label = f"[{i}/{len(playlists)}]"
            print(f"{label} Reading playlist {playlist.id} ...")
            fetch_tracks(settings, playlist)
            if playlist.error:
                print(f"  [error] {playlist.error}\n")
                results.append(new_stats(playlist))
                continue

            folder = settings.download_dir / namer.name_for(playlist)

            print(f"  '{playlist.title}': {len(playlist.tracks)} tracks -> {folder}")
            stats = new_stats(playlist, folder)
            results.append(stats)
            download_playlist(settings, playlist, folder, label, stats, limit=args.limit)
            print(f"  Done in {fmt_duration(stats['seconds'])}\n")
    except KeyboardInterrupt:
        print("\n\nInterrupted. Run the script again to resume: existing MP3s are skipped.")
    total_seconds = time.perf_counter() - total_start

    print_report(results, total_seconds)

    STATE_DIR.mkdir(exist_ok=True)
    report_file = STATE_DIR / f"timings_{datetime.now():%Y%m%d_%H%M%S}.json"
    report = {
        "started_at": datetime.fromtimestamp(time.time() - total_seconds).isoformat(timespec="seconds"),
        "destination": str(settings.download_dir),
        "limit": args.limit,
        "sleep_seconds": [settings.sleep_min, settings.sleep_max],
        "total_seconds": round(total_seconds, 1),
        "playlists": results,
    }
    report_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport saved to {report_file}")

    for r in results:
        if r["error"]:
            print(f"\n[error] playlist {r['title']} ({r['id']}): {r['error']}")
    failures = [(r["title"], f) for r in results for f in r["failures"]]
    if failures:
        print(f"\n{len(failures)} failed tracks:")
        for playlist_title, f in failures:
            print(f"  - [{playlist_title}] {f['title']} ({f['id']}): {f['error']}")


if __name__ == "__main__":
    main()
