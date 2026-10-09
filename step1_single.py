"""Step 1: download a single hardcoded song as MP3 to check the whole toolchain.

Usage:
    python step1_single.py
"""

import time

import yt_dlp

from config import load_settings
from ytcommon import build_ydl_opts, check_dependencies, final_filepath

# Replace with any song you like. The default is "Me at the zoo" (19 seconds,
# the first video ever uploaded to YouTube): tiny and always available.
SONG_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"


def main() -> None:
    settings = load_settings()
    check_dependencies(settings)
    settings.download_dir.mkdir(parents=True, exist_ok=True)

    opts = build_ydl_opts(settings, settings.download_dir, ignore_errors=False)
    opts["noplaylist"] = True  # a watch?v=...&list=... URL downloads only the video
    opts["sleep_interval"] = 0  # no point waiting before a single download
    opts.pop("max_sleep_interval", None)

    print(f"Downloading: {SONG_URL}")
    print(f"Destination: {settings.download_dir}")
    print(f"Cookies:     {settings.cookies_file or 'not used'}\n")

    start = time.perf_counter()
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(SONG_URL, download=True)
    except yt_dlp.utils.DownloadError as e:
        raise SystemExit(f"\n[error] Download failed: {e}\nSee the README troubleshooting section.")
    elapsed = time.perf_counter() - start

    path = final_filepath(info)
    print(f"\nDone in {elapsed:.1f}s")
    if path and path.exists():
        size_mb = path.stat().st_size / 1_048_576
        print(f"File: {path} ({size_mb:.2f} MB)")
    else:
        print(f"Finished, but the output file could not be located. Check {settings.download_dir}")


if __name__ == "__main__":
    main()
