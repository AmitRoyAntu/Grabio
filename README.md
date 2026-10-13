# VidGrab (YT Grab)

A local web app to download videos from **YouTube, Facebook, Instagram, TikTok** and [any other yt-dlp-supported site](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) — as **MP4, MP3, or M4A**. Runs entirely on your own computer. No ads, no accounts, no cloud.

---

## Features

- 🎵 **MP3 / M4A / MP4** — audio and video formats with quality selection
- 🖼 **Metadata & cover art** — title, artist, and thumbnail embedded in audio files
- 📂 **Playlist support** — pick individual songs, filter, shift-click to select ranges
- ⚡ **Parallel downloads** — up to 3 songs at once
- 📁 **Save to folder** — write files directly to a local path, or download via browser
- ❌ **Cancel button** — stop a download mid-way
- 🔄 **yt-dlp auto-update** — in-app notice and one-click update when yt-dlp is out of date
- 🌗 **Dark / light mode**
- 🔋 **No system ffmpeg needed** — ships a bundled static binary via `imageio-ffmpeg`

### Supported platforms

| Platform | Videos | Playlists | Notes |
|---|---|---|---|
| YouTube | ✅ | ✅ | Full support |
| TikTok | ✅ | ✅ | User feeds work as playlists |
| Instagram | ✅ | ✅ | Reels, posts; private content needs cookies |
| Facebook | ✅ | ⚠️ | Public videos/Reels; some require login |
| + [1000 more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) | ✅ | varies | Anything yt-dlp supports |

---

## Quick Start

### macOS & Linux
```bash
git clone https://github.com/yourname/ytgrab.git
cd ytgrab
./start.sh
```

### Windows
```
git clone https://github.com/yourname/ytgrab.git
cd ytgrab
start.bat
```

`start.sh` / `start.bat` will:
1. Find a compatible Python 3.9+ installation
2. Create a `.venv` virtual environment (first run only)
3. Install all dependencies automatically
4. Start the server and open **http://127.0.0.1:5000** in your browser

---

## Manual Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open **http://127.0.0.1:5000**.

---

## Dependencies

| Package | Purpose |
|---|---|
| `flask` | Web framework |
| `yt-dlp` | YouTube downloader |
| `imageio-ffmpeg` | Bundled static ffmpeg binary — no Homebrew or system install needed |
| `waitress` | Production-grade WSGI server (macOS / Linux / Windows) |

Install / update all at once:
```bash
pip install -r requirements.txt
```

---

## Keeping yt-dlp Current

YouTube frequently changes its internals and breaks older versions of yt-dlp. The app shows an **update banner** automatically when a newer version is available. Click **Update now** to upgrade without leaving the browser.

You can also update manually:
```bash
pip install -U yt-dlp
```

---

## Legal

Only download content you own, that is licensed for reuse, or that you have explicit permission to save. Downloading copyrighted material may violate YouTube's Terms of Service and applicable laws.
