"""Download the selected albums/EPs of an artist: one folder per release inside the artist's folder.

The releases to download are the ids in ARTIST_RELEASES (.env); the script stops
with an error if that list is empty. Result:

    DOWNLOAD_DIR/<Artist>/<Album>/01 - Song [id].mp3

Tracks already present are skipped, so an interrupted run can simply be restarted.

Usage:
    python artist_download.py "https://music.youtube.com/channel/UCxxxxxxxx"
    python artist_download.py <artist link> --dest D:\\Music\\Artists
    python artist_download.py <artist link> --only OLAK5uy_xxxx    # just this release (repeatable)
"""

import argparse
import dataclasses
import sys
import time
from pathlib import Path

from config import load_settings
from downloader import FolderNamer, download_playlist, fmt_duration, new_stats
from ytcommon import (
    check_dependencies,
    fetch_tracks,
    list_artist_releases,
    safe_folder_name,
    selected_releases,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("artist_url", help="link to the artist page (YouTube or YouTube Music)")
    parser.add_argument("--dest", type=Path, help="destination folder (overrides DOWNLOAD_DIR)")
    parser.add_argument("--only", action="append", metavar="ID", help="only this release id (repeatable)")
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")  # titles with characters the console can't print

    settings = load_settings()
    if args.dest:
        settings = dataclasses.replace(settings, download_dir=args.dest.expanduser().resolve())
    releases = selected_releases(settings)  # exits if ARTIST_RELEASES is empty
    if args.only:
        unknown = set(args.only) - {r.id for r in releases}
        if unknown:
            raise SystemExit(f"[error] --only: not in ARTIST_RELEASES: {', '.join(sorted(unknown))}")
        releases = [r for r in releases if r.id in args.only]
    check_dependencies(settings)

    print("Reading the artist's releases...")
    artist, artist_releases = list_artist_releases(settings, args.artist_url)
    titles = {r.id: r.title for r in artist_releases}
    not_by_artist = [r.id for r in releases if r.id not in titles]
    if not_by_artist:
        # Still downloaded (it may be a compilation or a collaboration), but worth knowing.
        print(f"[warning] Not in this artist's releases, downloaded anyway: {', '.join(not_by_artist)}")

    artist_dir = settings.download_dir / safe_folder_name(artist, "Unknown artist")
    print(f"Artist:      {artist}")
    print(f"Destination: {artist_dir}")
    print(f"Releases:    {len(releases)}")
    print(f"Cookies:     {settings.cookies_file or 'not used'}\n")

    results: list[dict] = []
    namer = FolderNamer()
    total_start = time.perf_counter()
    try:
        for i, release in enumerate(releases, 1):
            label = f"[{i}/{len(releases)}]"
            release.title = titles.get(release.id, release.title)
            print(f"{label} Reading release {release.id} ...")
            fetch_tracks(settings, release)
            if release.error:
                print(f"  [error] {release.error}\n")
                results.append(new_stats(release))
                continue

            folder = artist_dir / namer.name_for(release)
            print(f"  '{release.title}': {len(release.tracks)} tracks -> {folder}")
            stats = new_stats(release, folder)
            results.append(stats)
            download_playlist(settings, release, folder, label, stats, album_artist=artist)
            print(f"  Done in {fmt_duration(stats['seconds'])}\n")
    except KeyboardInterrupt:
        print("\n\nInterrupted. Run the script again to resume: existing MP3s are skipped.")
    total_seconds = time.perf_counter() - total_start

    width = 40
    print(f"\n{'Release':<{width}}  {'Tracks':>6}  {'New':>5}  {'Had':>5}  {'Fail':>4}  {'Time':>8}")
    print("-" * (width + 40))
    for r in results:
        title = r["title"] if len(r["title"]) <= width else r["title"][: width - 1] + "…"
        if r["error"]:
            print(f"{title:<{width}}  ERROR: {r['error']}")
            continue
        print(
            f"{title:<{width}}  {r['tracks']:>6}  {r['downloaded']:>5}  {r['already_present']:>5}  "
            f"{r['failed']:>4}  {fmt_duration(r['seconds']):>8}"
        )
    print("-" * (width + 40))
    print(f"Total: {sum(r['downloaded'] for r in results)} tracks downloaded in {fmt_duration(total_seconds)}")

    failures = [(r["title"], f) for r in results for f in r["failures"]]
    if failures:
        print(f"\n{len(failures)} failed tracks (run again to retry):")
        for release_title, f in failures:
            print(f"  - [{release_title}] {f['title']} ({f['id']}): {f['error']}")


if __name__ == "__main__":
    main()
