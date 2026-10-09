# yt-music-downloader

Download your YouTube playlists (public, private and *Liked videos*) as MP3 files
with metadata and cover art, one folder per playlist. Built on
[yt-dlp](https://github.com/yt-dlp/yt-dlp).

> For personal use only. Downloading content may violate YouTube's Terms of Service
> and copyright law in your country: only download what you are allowed to.

| Step | Script | What it does | Status |
|------|--------|--------------|--------|
| 0 | – | Installation | ready |
| 1 | `step1_single.py` | Download one hardcoded song | ready |
| 2 | `step2_list_playlists.py` | Connect your account, list playlists + Liked | ready |
| 3 | `step3_download_all.py` | Download every playlist into its own folder, with timings | ready |
| 4 | `step4_sync.py` | Incremental sync: download what's new, delete what's gone | ready |
| Artist | `artist_list_releases.py`, `artist_download.py` | List an artist's albums/EPs, download the selected ones | ready |

All commands below are for **Windows PowerShell**, run from the project folder.

---

## Step 0 – Installation

### 0.1 Python (3.10 or newer)

Check whether it is already installed:

```powershell
python --version
```

If you get an error, or the Microsoft Store opens, install it:

```powershell
winget install -e --id Python.Python.3.12
```

Close and reopen the terminal, then run `python --version` again.

> If `python` still opens the Microsoft Store: *Settings → Apps → Advanced app settings →
> App execution aliases* and turn off the two "python" aliases. If you install Python
> manually from python.org instead, tick **"Add python.exe to PATH"**.

### 0.2 FFmpeg (audio conversion and cover art)

```powershell
winget install -e --id Gyan.FFmpeg
```

Close and reopen the terminal, then check it:

```powershell
ffmpeg -version
```

> If you can't add ffmpeg to PATH, set `FFMPEG_LOCATION` in `.env` to the folder that
> contains `ffmpeg.exe`.

### 0.3 Deno (JavaScript runtime required by yt-dlp for YouTube)

Recent yt-dlp versions need an external JavaScript runtime to solve YouTube's
challenges. Without it, downloads fail or only a few formats are available.

```powershell
winget install -e --id DenoLand.Deno
```

Close and reopen the terminal, then check it:

```powershell
deno --version
```

### 0.4 Virtual environment and Python packages

From the project folder (`yt-music-downloader`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> If activation fails with *"running scripts is disabled on this system"*, run this once,
> then activate again:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

Activate the virtual environment (`.\.venv\Scripts\Activate.ps1`) **every time** you
open a new terminal. Your prompt then starts with `(.venv)`.

### 0.5 Configuration

```powershell
copy .env.example .env
notepad .env
```

| Variable | Default | Meaning |
|----------|---------|---------|
| `DOWNLOAD_DIR` | `./downloads` | Where the music is saved |
| `YT_COOKIES` | `./cookies.txt` | Browser cookies file (needed from step 2 on) |
| `AUDIO_QUALITY` | `192` | MP3 bitrate in kbps |
| `SLEEP_MIN` / `SLEEP_MAX` | `2` / `6` | Random pause in seconds between downloads |
| `FFMPEG_LOCATION` | *(empty)* | Folder containing `ffmpeg.exe`, only if it is not on PATH |
| `ARTIST_RELEASES` | *(empty)* | **Required by `artist_download.py`.** Comma-separated album/EP ids (`OLAK5uy_...`) or URLs. Get them with `artist_list_releases.py` |
| `PLAYLISTS` | *(empty)* | **Required from step 3 on.** Comma-separated ids (or URLs) of the playlists to download. Get them with step 2. `LL` = Liked videos, `LM` = YouTube Music Liked music |

> **OneDrive users:** if this project folder is inside OneDrive, set `DOWNLOAD_DIR` to a
> folder outside it (e.g. `C:\Music\youtube`), or OneDrive will sync every MP3.

### 0.6 Keep yt-dlp up to date

YouTube changes often. When something stops working, **update yt-dlp first**:

```powershell
pip install -U "yt-dlp[default]"
```

---

## Step 1 – Download a single song

`step1_single.py` downloads the URL in the `SONG_URL` constant at the top of the file.
The default is a 19-second video, so the test is quick. Change it to any song you like.

```powershell
.\.venv\Scripts\Activate.ps1
python step1_single.py
```

Expected output (roughly):

```
Downloading: https://www.youtube.com/watch?v=jNQXAC9IVRw
Destination: C:\...\yt-music-downloader\downloads
Cookies:     not used
...
Done in 6.3s
File: C:\...\downloads\Me at the zoo [jNQXAC9IVRw].mp3 (0.45 MB)
```

**Check:** open the MP3 and play it. In File Explorer, the file should show the cover
art as its thumbnail. Its *Properties → Details* should show title and artist.

The video id in brackets in the file name is intentional: the later steps use it to know
which files are already downloaded.

---

## Step 2 – Connect your YouTube account and list your playlists

yt-dlp logs in to YouTube with your browser's **cookies**. With a cookies file it can see
your private playlists and your *Liked videos* too. No API key or Google Cloud project is needed.

### 2.1 Export the cookies (Brave, Chrome or Edge)

> On Windows, yt-dlp can't reliably read Chromium-based browsers' cookies directly (`--cookies-from-browser`)
> because of their encryption, so you export them to a file with an extension.

1. Install the extension **"Get cookies.txt LOCALLY"** from the Chrome Web Store.
   Brave and Chrome install it directly. On Edge, click *"Allow extensions from other stores"* first.
2. Allow it in private windows:
   - Brave: `brave://extensions` → *Get cookies.txt LOCALLY* → *Details* → enable **Allow in Private**.
   - Chrome: `chrome://extensions` → *Get cookies.txt LOCALLY* → *Details* → enable **Allow in Incognito**.
   - Edge: `edge://extensions` → *Details* → enable **Allow in InPrivate**.
3. Open a **new private window** (Brave: *New private window*, `Ctrl+Shift+N`; *not* "private window with Tor") and log in to <https://www.youtube.com> with
   the account whose playlists you want.
   On Brave, if YouTube's login or page doesn't load properly, lower **Shields** for youtube.com
   (lion icon in the address bar) before logging in.
4. While on youtube.com, click the extension icon, choose **Netscape** format, then **Export**.
   Save the file as `cookies.txt`, either in the project folder or wherever `YT_COOKIES` in `.env` points.
5. **Close the private window without logging out.** Logging out would invalidate the cookies.
   The private window also stops the browser from rotating (and so invalidating) them.

Why a private window: YouTube keeps rotating the cookies of a session that stays open in a
browser. A session you close right after the export keeps its cookies valid much longer,
usually weeks or months.

> **Security:** `cookies.txt` gives **full access to your Google account**, like a
> password. Never share it or commit it (it is already in `.gitignore`). If this project is
> inside OneDrive, store the file outside it, e.g. `C:\Users\<you>\yt-secrets\cookies.txt`, and set
> `YT_COOKIES` to that path.

> **Account safety:** yt-dlp's documentation warns that heavy downloading while logged in
> *may* get the account flagged. The random pause between downloads (`SLEEP_MIN`/`SLEEP_MAX`)
> reduces this risk. Don't set it to 0 for large downloads.

**When to export again:** when the scripts say the cookies are expired, show no playlists, or
you get *"Sign in to confirm you're not a bot"*. Repeat steps 3–5 and overwrite the file.

### 2.2 List your playlists

```powershell
.\.venv\Scripts\Activate.ps1
python step2_list_playlists.py
```

The script reads your library (playlists you created or saved, public and private), adds
*Liked videos*, and counts the tracks in each one. Nothing is downloaded. The playlists already
listed in `PLAYLISTS` are marked with `*` in the **Sel** column.

```
  #  Sel  Title                                          Tracks  Unavail.  Id
------------------------------------------------------------------------------------------
  1   *   Road trip                                          84         2  PLxxxxxxxxxxxxxxxx
  2       Chill (private)                                    31         0  PLyyyyyyyyyyyyyyyy
  3   *   Liked videos                                      412         5  LL
------------------------------------------------------------------------------------------
3 playlists, 527 tracks (7 private/deleted, will be skipped) - read in 9.8s

2 playlists selected in PLAYLISTS (marked with *).
```

Options:

| Command | Effect |
|---------|--------|
| `python step2_list_playlists.py --selected` | Only the playlists in `PLAYLISTS` (error if it is empty) |
| `python step2_list_playlists.py --fast` | Only the list, no track counts (one request) |
| `python step2_list_playlists.py --json` | JSON output, e.g. `... --json > playlists.json` |

**Check:** one of your **private** playlists and **Liked videos** must be in the list.

### 2.3 Choose the playlists to download

Copy the ids you want from the **Id** column into `PLAYLISTS` in `.env`, separated by commas:

```
PLAYLISTS=PLxxxxxxxxxxxxxxxx, PLyyyyyyyyyyyyyyyy, LL
```

Only these playlists are downloaded, in this order. Full playlist URLs work too. If
`PLAYLISTS` is empty, the download scripts stop with an error. Check your selection with:

```powershell
python step2_list_playlists.py --selected
```

Notes:
- *Liked videos* (`LL`) contains everything you liked, music or not. Likes on YouTube Music are
  the same likes. To get only songs, try YouTube Music's *Liked music* with `LM` in `PLAYLISTS`.
- Playlists that are not in your library (e.g. someone else's public playlist) work too: put
  their id in `PLAYLISTS`. They show up at the bottom of the list.

---

## Step 3 – Download all the selected playlists

Requires `PLAYLISTS` in `.env` (step 2.3) and valid cookies (step 2.1).

```powershell
.\.venv\Scripts\Activate.ps1
python step3_download_all.py --limit 3     # quick test: first 3 tracks of each playlist
python step3_download_all.py               # everything
```

Each playlist gets its own sub-folder of `DOWNLOAD_DIR`, named after the playlist:

```
downloads\
├── Road trip\
│   ├── Song A [xxxxxxxxxxx].mp3
│   └── Song B [yyyyyyyyyyy].mp3
└── Liked videos\
    └── ...
```

Options:

| Command | Effect |
|---------|--------|
| `--limit N` | Download at most the first N tracks of each playlist (quick test) |
| `--only PLxxxx` | Only this playlist (must be in `PLAYLISTS`). Repeatable: `--only PLaaa --only LL` |
| `--dest D:\Music\2026-10` | Download into another folder instead of `DOWNLOAD_DIR` |

**Interrupting and resuming:** press `Ctrl+C` at any time. Run the same command again and the
MP3s already in the folder (matched by the video id in the file name) are skipped.
Private or deleted videos are skipped without trying.

### Timing report

Each track prints its download time. At the end you get a summary:

```
Playlist                          Tracks    New    Had  Unav.  Fail      Time  s/track
------------------------------------------------------------------------------------------
Road trip                             84     82      0      2     0     14:21     10.5
Liked videos                         412    401      0      5     6   1:12:40     10.9
------------------------------------------------------------------------------------------
New = downloaded now, Had = already in the folder, Unav. = private/deleted on YouTube

Total: 483 tracks downloaded in 1:27:01
Average: 10.8s per track (including the anti-bot pause)
Estimated full download of all 489 tracks: 1:28:03
=> Too slow to re-download everything each time: the step 4 sync is worth it.
```

The same data, including the list of failed tracks and their errors, is saved in
`state\timings_YYYYMMDD_HHMMSS.json`.

The estimate also works after a `--limit` test run: it multiplies the average time per track
by the number of tracks in all the selected playlists. Most of the time per track is the
random pause (`SLEEP_MIN`–`SLEEP_MAX`, 4 s on average with the defaults), the rest is download
and MP3 conversion.

**What to do with the result:** if the full download takes 20 minutes or less, you can simply
re-download everything into a new folder (`--dest`) whenever you want fresh playlists.
Otherwise step 4 (incremental sync) is worth building.

---

## Step 4 – Sync (download only what changed)

Keeps the local folders in line with your playlists without downloading everything again.
For each playlist in `PLAYLISTS`:

- **folder doesn't exist yet** → the whole playlist is downloaded (like step 3);
- **folder exists** → only the differences are applied:
  - tracks **added** to the playlist on YouTube are downloaded;
  - tracks **removed** from the playlist are deleted from the folder;
  - everything else is left untouched.

```powershell
.\.venv\Scripts\Activate.ps1
python step4_sync.py --dry-run    # first, look at what would change
python step4_sync.py              # then sync (asks before deleting anything)
```

Example of the plan it prints:

```
[1/2] Reading playlist PLxxxxxxxxxxxxxxxx ...
  'Road trip' (86 tracks)
    3 to download, 1 to delete, 81 unchanged, 2 unavailable
      + New song A
      + New song B
      + New song C
      - Old song [zzzzzzzzzzz].mp3

Plan: 3 to download, 1 to delete, 0 folders to rename.

Delete 1 local files? [y/N]
```

Options:

| Command | Effect |
|---------|--------|
| `--dry-run` | Only show the plan, change nothing |
| `--yes` | Delete without asking (e.g. for a scheduled task) |
| `--only PLxxxx` | Only this playlist (must be in `PLAYLISTS`). Repeatable |
| `--dest D:\Music` | Sync another folder instead of `DOWNLOAD_DIR` |

If you answer **N** to the delete question, downloads and renames still happen and nothing is deleted.

### How it knows what changed

- **No database:** the folder contents are the truth. Every MP3 has its YouTube video id in its
  name (`Title [id].mp3`), so the script compares those ids with the playlist's current ids.
  You can therefore run step 4 directly on a folder created by step 3.
- `state\last_sync.json` (in the project folder, ignored by git) remembers which folder belongs to
  which playlist, for each destination. If you **rename a playlist** on YouTube, its folder is
  renamed instead of downloaded again. If the file is lost, nothing breaks: a renamed playlist
  would just be downloaded into a new folder.

### Safety rules

- Tracks that are still in the playlist but became **private/deleted** on YouTube are **kept**
  locally, since you couldn't download them again.
- If YouTube returns an **empty** playlist (or an error) while the folder has tracks, **nothing is
  deleted** for that playlist.
- Folders of playlists you removed from `PLAYLISTS` are **never touched**: delete them by hand.
- Only MP3 files with an `[id]` in their name are managed. Other files you put in the folders are ignored.
- Failed downloads are retried automatically at the next sync. `Ctrl+C` is safe: run it again
  to finish.

---

## Artists – download albums and EPs

Two scripts to download whole releases of an artist, each into its own folder:

```
downloads\
└── Artist Name\
    ├── First Album\
    │   ├── 01 - Song A [xxxxxxxxxxx].mp3
    │   └── 02 - Song B [yyyyyyyyyyy].mp3
    └── Some EP\
        └── ...
```

Cookies are **not required** here (releases are public), but they are used if `YT_COOKIES` points to a valid file.

### 1. Find the artist link

Open the artist page and copy the address from the browser. Both forms work:

- YouTube Music: `https://music.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx`
- YouTube: `https://www.youtube.com/@ArtistName` or `https://www.youtube.com/channel/UC...`

> Use the **artist** page, the one with the *Albums* / *Singles & EPs* sections on YouTube
> Music. **The YouTube Music link is the most reliable.** Many bands' own YouTube channels
> have no *Releases* tab: the script then also looks in the *Playlists* and *Home* tabs, keeping
> only official album playlists (`OLAK5uy_...`). A fan or label channel won't work.

### 2. List the releases

```powershell
.\.venv\Scripts\Activate.ps1
python artist_list_releases.py "https://music.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"
```

```
Artist: Artist Name

  #  Sel  Type    Title                                               Tracks  Id
------------------------------------------------------------------------------------------------------------------------
  1       Album   First Album                                             12  OLAK5uy_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
  2   *   EP      Some EP                                                  5  OLAK5uy_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
  3       Single  A Single                                                 1  OLAK5uy_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz
------------------------------------------------------------------------------------------------------------------------
3 releases - read in 6.2s
Type is a guess from the track count: 1-3 Single, 4-6 EP, 7+ Album.
```

YouTube doesn't say whether a release is an album, an EP or a single, so **Type** is only a
guess from the number of tracks. `--fast` skips the track counts and only shows titles and ids.

### 3. Choose what to download

Copy the ids you want into `ARTIST_RELEASES` in `.env`, separated by commas:

```
ARTIST_RELEASES=OLAK5uy_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx, OLAK5uy_yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
```

Run the list again: the selected releases are marked with `*`. If `ARTIST_RELEASES` is
empty, `artist_download.py` stops with an error.

### 4. Download

```powershell
python artist_download.py "https://music.youtube.com/channel/UCxxxxxxxxxxxxxxxxxxxxxx"
```

| Option | Effect |
|--------|--------|
| `--dest D:\Music\Artists` | Create the artist folder there instead of in `DOWNLOAD_DIR` |
| `--only OLAK5uy_xxxx` | Only this release (must be in `ARTIST_RELEASES`). Repeatable |

- Files are numbered in album order (`01 - ...`). If YouTube doesn't provide them, album, artist
  and track number are also written into the MP3 tags, so phone players group them correctly.
- Already downloaded tracks are skipped: `Ctrl+C` and run again to resume or retry failures.
- `ARTIST_RELEASES` holds the releases of **one artist at a time**: when you move on to another
  artist, replace the ids.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `python`/`ffmpeg`/`deno` not found right after installing (even after restarting VS Code) | The terminal still has the old PATH. Quit **every** VS Code window (check Task Manager), or refresh PATH in the current terminal: `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')` |
| `ffmpeg not found` | Do step 0.2, then **reopen the terminal**. Or set `FFMPEG_LOCATION` in `.env`. |
| `deno not found` warning, or errors about *signature*, *n challenge* or *JS runtime* | Do step 0.3, reopen the terminal, then run `pip install -U "yt-dlp[default]"`. |
| `HTTP Error 403: Forbidden` | Update yt-dlp (step 0.6) and retry. |
| `Sign in to confirm you're not a bot` | YouTube is throttling your IP: wait a while, or use cookies (step 2). If you already use them, export them again. |
| `Cookies file not found` | Check `YT_COOKIES` in `.env` and the file name (Explorer may hide the `.txt` extension: `cookies.txt.txt`). |
| `Could not read your playlists` / no playlists found | Cookies expired or exported while logged out: export them again (step 2.1). |
| A playlist shows `ERROR` | Usually deleted, or private and owned by someone else: remove it from `PLAYLISTS`. |
| `No playlists selected: PLAYLISTS in .env is empty` | Set `PLAYLISTS` in `.env` (step 2.3). |
| `No albums/EPs selected: ARTIST_RELEASES in .env is empty` | Run `artist_list_releases.py` and set `ARTIST_RELEASES` in `.env`. |
| `No albums/EPs found` / `is not an artist link` | The script looks in the channel's *Releases*, *Playlists* and *Home* tabs and prints what it found in each. If all are empty, the link is the band's upload channel rather than its music channel: open the artist on <https://music.youtube.com> (search → click the artist name) and use that link. Update yt-dlp (step 0.6). |
| Many tracks `FAILED` in a row in step 3 | Probably rate-limited: stop (`Ctrl+C`), wait an hour, raise `SLEEP_MIN`/`SLEEP_MAX`, re-export the cookies, then resume. |
| A track fails with *"Video unavailable"* / *"not available in your country"* | Nothing to do: it is listed in the report and skipped. |
| Step 4 wants to re-download a whole playlist you already have | The folder name differs (playlist renamed, `--dest` changed, or `state\last_sync.json` deleted). Rename the folder to the playlist's current title and run `--dry-run` again. |
| `ModuleNotFoundError: No module named 'yt_dlp'` | The virtual environment is not active: `.\.venv\Scripts\Activate.ps1`. |
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `.env` changes are ignored | The file must be named exactly `.env` (not `.env.txt`): check with `dir -Force`. |
