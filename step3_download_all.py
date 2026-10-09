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

import yt_dlp

from config import STATE_DIR, Settings, load_settings
from ytcommon import (
    CollectingLogger,
    Playlist,
    build_ydl_opts,
    check_dependencies,
    existing_tracks,
    fetch_tracks,
    is_unavailable,
    require_cookies,
    safe_folder_name,
    selected_playlists,
    track_url,
)

# Above this total, re-downloading everything every time is not worth it: use step 4.
FULL_REDOWNLOAD_MAX_SECONDS = 20 * 60


def fmt_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


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
    settings: Settings, playlist: Playlist, folder: Path, limit: int | None, label: str, stats: dict
) -> None:
    """Download the playlist's tracks into folder, updating stats in place.

    stats is filled as we go so that it is still valid after a Ctrl+C.
    """
    folder.mkdir(parents=True, exist_ok=True)
    present = existing_tracks(folder)
    tracks = playlist.tracks[:limit] if limit else playlist.tracks

    logger = CollectingLogger()
    opts = build_ydl_opts(settings, folder)
    opts.update({"logger": logger, "noplaylist": True, "noprogress": True})

    start = time.perf_counter()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            for n, entry in enumerate(tracks, 1):
                video_id, title = entry["id"], entry.get("title") or entry["id"]
                prefix = f"  {label}[{n}/{len(tracks)}]"
                if is_unavailable(entry):
                    stats["unavailable"] += 1
                    print(f"{prefix} skip (unavailable): {title}")
                    continue
                if video_id in present:
                    stats["already_present"] += 1
                    print(f"{prefix} already present: {title}")
                    continue

                print(f"{prefix} {title} ...", end="", flush=True)
                logger.last_error = None
                track_start = time.perf_counter()
                try:
                    ydl.extract_info(track_url(video_id), download=True)
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
    used_folders: set[str] = set()
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

            folder_name = safe_folder_name(playlist.title, playlist.id)
            if folder_name.lower() in used_folders:  # two playlists with the same title
                folder_name = f"{folder_name} [{playlist.id}]"
            used_folders.add(folder_name.lower())
            folder = settings.download_dir / folder_name

            print(f"  '{playlist.title}': {len(playlist.tracks)} tracks -> {folder}")
            stats = new_stats(playlist, folder)
            results.append(stats)
            download_playlist(settings, playlist, folder, args.limit, label, stats)
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
