"""Step 4: sync the playlists in PLAYLISTS (.env) with their local folders.

For each playlist:
  - if its folder doesn't exist yet, the whole playlist is downloaded;
  - if it exists, only the differences are applied: tracks added on YouTube are
    downloaded, tracks removed from the playlist are deleted locally.

What is on disk is the source of truth (the [video id] in each MP3 file name).
state/last_sync.json only remembers which folder belongs to which playlist, so a
playlist renamed on YouTube gets its folder renamed instead of downloaded again.

Usage:
    python step4_sync.py                  # show the plan, ask before deleting, then sync
    python step4_sync.py --dry-run        # only show what would change
    python step4_sync.py --yes            # don't ask before deleting
    python step4_sync.py --only PLxxxx    # just this playlist (repeatable)
    python step4_sync.py --dest D:\\Music  # different destination than DOWNLOAD_DIR
"""

import argparse
import dataclasses
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import STATE_DIR, load_settings
from downloader import FolderNamer, download_playlist, fmt_duration, new_stats
from ytcommon import (
    Playlist,
    check_dependencies,
    existing_tracks,
    fetch_tracks,
    is_unavailable,
    require_cookies,
    selected_playlists,
)

STATE_FILE = STATE_DIR / "last_sync.json"
LIST_PREVIEW = 10  # how many file names to show per playlist in the plan


@dataclass
class PlaylistPlan:
    playlist: Playlist
    folder: Path
    rename_from: Path | None = None  # old folder to rename into `folder`
    to_download: list[dict] = field(default_factory=list)  # flat entries
    to_delete: list[Path] = field(default_factory=list)
    unchanged: int = 0
    unavailable: int = 0
    warning: str | None = None


# ---------------------------------------------------------------- state file


def load_state(destination: Path) -> dict:
    """Playlist id -> {"title", "folder", "synced_at", "tracks"} for this destination."""
    if not STATE_FILE.is_file():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[warning] Ignoring unreadable {STATE_FILE}: {e}")
        return {}
    return data.get("destinations", {}).get(str(destination), {}).get("playlists", {})


def save_state(destination: Path, playlists: dict) -> None:
    data: dict = {"destinations": {}}
    if STATE_FILE.is_file():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass  # rewritten from scratch below
    data.setdefault("destinations", {})[str(destination)] = {
        "synced_at": datetime.now().isoformat(timespec="seconds"),
        "playlists": playlists,
    }
    STATE_DIR.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")  # write + rename: never a half-written file
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------- planning


def plan_playlist(playlist: Playlist, folder: Path, previous: dict | None) -> PlaylistPlan:
    plan = PlaylistPlan(playlist=playlist, folder=folder)

    # Renamed on YouTube since the last sync: reuse the old folder.
    old_folder = folder.parent / previous["folder"] if previous else None
    if old_folder and old_folder != folder and old_folder.is_dir():
        if folder.exists():
            plan.warning = (
                f"renamed from '{old_folder.name}', but '{folder.name}' already exists: "
                "using the new folder, the old one is left untouched"
            )
        else:
            plan.rename_from = old_folder

    local = existing_tracks(plan.rename_from or folder)
    remote_ids = {entry["id"] for entry in playlist.tracks}

    for entry in playlist.tracks:
        if entry["id"] in local:
            plan.unchanged += 1
        elif is_unavailable(entry):
            plan.unavailable += 1  # still in the playlist but can't be downloaded
        else:
            plan.to_download.append(entry)

    # Safety net: an empty answer from YouTube must not wipe a full folder.
    if not playlist.tracks and local:
        plan.warning = "YouTube returned no tracks: nothing will be deleted"
    else:
        plan.to_delete = sorted(path for vid, path in local.items() if vid not in remote_ids)
    return plan


def print_plan(plan: PlaylistPlan) -> None:
    def preview(items: list[str], sign: str) -> None:
        for item in items[:LIST_PREVIEW]:
            print(f"      {sign} {item}")
        if len(items) > LIST_PREVIEW:
            print(f"      {sign} ... and {len(items) - LIST_PREVIEW} more")

    if plan.rename_from:
        print(f"    folder renamed: '{plan.rename_from.name}' -> '{plan.folder.name}'")
    elif not plan.folder.exists():
        print(f"    new folder: {plan.folder}")
    print(
        f"    {len(plan.to_download)} to download, {len(plan.to_delete)} to delete, "
        f"{plan.unchanged} unchanged" + (f", {plan.unavailable} unavailable" if plan.unavailable else "")
    )
    preview([e.get("title") or e["id"] for e in plan.to_download], "+")
    preview([p.name for p in plan.to_delete], "-")
    if plan.warning:
        print(f"    [warning] {plan.warning}")


def confirm(question: str) -> bool:
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


# ---------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="show the plan, change nothing")
    parser.add_argument("--yes", action="store_true", help="delete without asking")
    parser.add_argument("--only", action="append", metavar="ID", help="only this playlist id (repeatable)")
    parser.add_argument("--dest", type=Path, help="destination folder (overrides DOWNLOAD_DIR)")
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")  # titles with characters the console can't print

    settings = load_settings()
    if args.dest:
        settings = dataclasses.replace(settings, download_dir=args.dest.expanduser().resolve())
    destination = settings.download_dir
    if not args.dry_run:
        check_dependencies(settings)
    require_cookies(settings)

    playlists = selected_playlists(settings)  # exits if PLAYLISTS is empty
    if args.only:
        unknown = set(args.only) - {p.id for p in playlists}
        if unknown:
            raise SystemExit(f"[error] --only: not in PLAYLISTS: {', '.join(sorted(unknown))}")
        playlists = [p for p in playlists if p.id in args.only]

    state = load_state(destination)
    print(f"Destination: {destination}")
    print(f"Playlists:   {len(playlists)}\n")

    # 1. Plan: read every playlist from YouTube and compare it with its folder.
    plans: list[PlaylistPlan] = []
    errors: list[Playlist] = []
    namer = FolderNamer()
    for i, playlist in enumerate(playlists, 1):
        print(f"[{i}/{len(playlists)}] Reading playlist {playlist.id} ...")
        fetch_tracks(settings, playlist)
        if playlist.error:
            print(f"    [error] {playlist.error} - skipped, nothing changes for it")
            errors.append(playlist)
            continue
        print(f"  '{playlist.title}' ({len(playlist.tracks)} tracks)")
        plan = plan_playlist(playlist, destination / namer.name_for(playlist), state.get(playlist.id))
        print_plan(plan)
        plans.append(plan)

    total_download = sum(len(p.to_download) for p in plans)
    total_delete = sum(len(p.to_delete) for p in plans)
    renames = sum(1 for p in plans if p.rename_from)
    print(f"\nPlan: {total_download} to download, {total_delete} to delete, {renames} folders to rename.")

    if args.dry_run:
        print("Dry run: nothing changed.")
        return
    if not (total_download or total_delete or renames):
        print("Everything is already in sync.")
        save_state(destination, _state_entries(plans, state))
        return

    delete = bool(total_delete) and (args.yes or confirm(f"\nDelete {total_delete} local files?"))
    if total_delete and not delete:
        print("Deletions skipped: only downloads and renames will be applied.")

    # 2. Apply: rename, delete, download.
    results: list[dict] = []
    total_start = time.perf_counter()
    try:
        for i, plan in enumerate(plans, 1):
            label = f"[{i}/{len(plans)}]"
            stats = new_stats(plan.playlist, plan.folder)
            stats["deleted"] = 0
            results.append(stats)
            if not (plan.to_download or plan.rename_from or (delete and plan.to_delete)):
                stats["already_present"] = plan.unchanged
                continue

            print(f"\n{label} {plan.playlist.title}")
            if plan.rename_from:
                plan.rename_from.rename(plan.folder)
                print(f"  renamed folder '{plan.rename_from.name}' -> '{plan.folder.name}'")
            if delete:
                for path in plan.to_delete:
                    # Planned paths may point to the folder's old name: it's been renamed by now.
                    (plan.folder / path.name).unlink(missing_ok=True)
                    stats["deleted"] += 1
                    print(f"  - deleted {path.name}")
            if plan.to_download:
                download_playlist(settings, plan.playlist, plan.folder, label, stats, quiet_skips=True)
            else:
                stats["already_present"] = plan.unchanged
    except KeyboardInterrupt:
        print("\n\nInterrupted. Run the sync again to finish: it only does what is still missing.")
    total_seconds = time.perf_counter() - total_start

    save_state(destination, _state_entries(plans, state))
    print_report(results, errors, total_seconds)


def _state_entries(plans: list[PlaylistPlan], previous: dict) -> dict:
    """New state: what is actually on disk now. Playlists not synced this time are kept."""
    entries = dict(previous)
    for plan in plans:
        folder = plan.folder if plan.folder.is_dir() else plan.rename_from
        if folder is None or not folder.is_dir():
            continue
        entries[plan.playlist.id] = {
            "title": plan.playlist.title,
            "folder": folder.name,
            "synced_at": datetime.now().isoformat(timespec="seconds"),
            "tracks": sorted(existing_tracks(folder)),
        }
    return entries


def print_report(results: list[dict], errors: list[Playlist], total_seconds: float) -> None:
    width = 32
    print()
    print(f"{'Playlist':<{width}}  {'Added':>5}  {'Deleted':>7}  {'Unchanged':>9}  {'Fail':>4}  {'Time':>8}")
    print("-" * (width + 46))
    for r in results:
        title = r["title"] if len(r["title"]) <= width else r["title"][: width - 1] + "…"
        print(
            f"{title:<{width}}  {r['downloaded']:>5}  {r['deleted']:>7}  {r['already_present']:>9}  "
            f"{r['failed']:>4}  {fmt_duration(r['seconds']):>8}"
        )
    for p in errors:
        print(f"{p.title[:width]:<{width}}  ERROR: {p.error}")
    print("-" * (width + 46))
    print(f"Sync finished in {fmt_duration(total_seconds)}. State saved to {STATE_FILE}")

    failures = [(r["title"], f) for r in results for f in r["failures"]]
    if failures:
        print(f"\n{len(failures)} failed tracks (they will be retried at the next sync):")
        for playlist_title, f in failures:
            print(f"  - [{playlist_title}] {f['title']} ({f['id']}): {f['error']}")


if __name__ == "__main__":
    main()
