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
| 2 | `step2_list_playlists.py` | Connect your account, list playlists + Liked | coming next |
| 3 | `step3_download_all.py` | Download every playlist into its own folder, with timings | coming next |
| 4 | `step4_sync.py` | Incremental sync (only if step 3 is slow) | to be decided |

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

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `python`/`ffmpeg`/`deno` not found right after installing (even after restarting VS Code) | The terminal still has the old PATH. Quit **every** VS Code window (check Task Manager), or refresh PATH in the current terminal: `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')` |
| `ffmpeg not found` | Do step 0.2, then **reopen the terminal**. Or set `FFMPEG_LOCATION` in `.env`. |
| `deno not found` warning, or errors about *signature*, *n challenge* or *JS runtime* | Do step 0.3, reopen the terminal, then run `pip install -U "yt-dlp[default]"`. |
| `HTTP Error 403: Forbidden` | Update yt-dlp (step 0.6) and retry. |
| `Sign in to confirm you're not a bot` | YouTube is throttling your IP: wait a while, or use cookies (step 2). |
| `ModuleNotFoundError: No module named 'yt_dlp'` | The virtual environment is not active: `.\.venv\Scripts\Activate.ps1`. |
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `.env` changes are ignored | The file must be named exactly `.env` (not `.env.txt`): check with `dir -Force`. |
