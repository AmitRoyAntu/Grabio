# Grabio

A fast, modern local web app to download videos and audio from **YouTube, Twitch, Twitter (X), TikTok, Instagram, Facebook**, and [1,000+ other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) — as **MP4, MP3, or M4A**. 

Runs 100% locally on your computer with zero cloud limits, ads, accounts, or tracking.

---

## ✨ Features

- 🎵 **MP3 / M4A / MP4** — High-quality audio (up to 320 kbps) and video formats (up to 4K / 2160p).
- 🖼 **Metadata & Cover Art** — Title, channel/uploader, and artwork automatically embedded into audio files.
- 📂 **Playlists & Feeds** — Parse whole playlists or user feeds, filter items by keyword, pick individual videos, or shift-click to select ranges.
- ⚡ **Parallel Downloads** — Downloads multiple items concurrently with real-time per-item progress indicators.
- 📁 **Save to Folder** — Save files directly into any local folder on your computer, or download via browser (with auto-zipped playlists).
- ✏️ **Custom Filenames & Numbering** — Rename output files and optionally serialize playlist filenames (`01 Title`, `02 Title`, etc.).
- ❌ **Instant Cancellation** — Stop ongoing downloads immediately with a single click.
- 🔄 **In-App yt-dlp Updater** — Automatic version check banner with a one-click update button inside the app.
- 🌗 **Light & Dark Theme** — Clean modern UI with playful geometric aesthetic and system/manual theme toggle.
- 🔋 **Zero-Config ffmpeg** — Ships a bundled static ffmpeg binary via `imageio-ffmpeg` (no Homebrew or manual binary setup required).

---

## 🌐 Supported Platforms

| Platform | Videos / Clips | Playlists / Feeds | Notes |
|---|---|---|---|
| **YouTube** | ✅ | ✅ | Videos, Shorts, full playlists |
| **Twitch** | ✅ | ✅ | Clips, VODs, highlights, and streams |
| **Twitter (X)** | ✅ | ⚠️ | Tweets and multi-video threads |
| **TikTok** | ✅ | ✅ | Individual videos, user feeds as playlists |
| **Instagram** | ✅ | ✅ | Reels, posts (public content; private requires cookies) |
| **Facebook** | ✅ | ⚠️ | Public videos and Reels |
| **+ 1,000 more** | ✅ | varies | [Any site supported by yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) |

---

## 🚀 Quick Start

### macOS & Linux
```bash
git clone https://github.com/yourname/grabio.git
cd grabio
./start.sh
```

### Windows
```cmd
git clone https://github.com/yourname/grabio.git
cd grabio
start.bat
```

`start.sh` and `start.bat` will automatically:
1. Detect a compatible Python 3.9+ runtime
2. Create a virtual environment (`.venv`) on first run
3. Install all required dependencies
4. Start the server and launch **http://127.0.0.1:5000** in your browser

---

## 🛠️ Manual Setup

If you prefer to run it manually without the helper scripts:

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the application
python app.py
```

Then open **http://127.0.0.1:5000** in your web browser.

---

## ☁️ Deploy to the Cloud (Public Web App)

You can host Grabio online on a free or low-cost cloud provider so anyone can access it from a public URL.

### Option A: Deploy on [Render.com](https://render.com) (Recommended Free Tier)
1. Push this repository to your GitHub account.
2. Sign in to **[dashboard.render.com](https://dashboard.render.com)**.
3. Click **New +** → **Web Service**.
4. Connect your GitHub repository.
5. Select **Docker** as the Runtime (or select Blueprint to use `render.yaml`).
6. Set the Instance Type to **Free** and click **Deploy Web Service**.
7. Render will build the Docker container and give you a public URL (e.g. `https://grabio.onrender.com`).

### Option B: Deploy on [Railway](https://railway.app)
1. In Railway, click **New Project** → **Deploy from GitHub repo**.
2. Railway will automatically detect the `Dockerfile`, build it, and assign a public domain.

### Option C: Run with Docker Anywhere (VPS / Server)
```bash
# Build the Docker image
docker build -t grabio .

# Run container mapping port 5000
docker run -d -p 5000:5000 --name grabio grabio
```

### ⚙️ Optional Cloud Environment Variables
| Variable | Description |
|---|---|
| `PORT` | Port number to bind (automatically provided by Render/Railway, defaults to `5000`). |
| `COOKIES_FILE` | Path to a Netscape-format `cookies.txt` file to allow access to age-restricted content or bypass platform bot challenges. |
| `PROXY_URL` | Optional HTTP/SOCKS5 proxy URL (e.g. `http://user:pass@proxy:port`) to route download traffic through residential proxies. |

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `flask` | Lightweight web framework serving the UI and REST API |
| `yt-dlp` | Video and audio extraction engine |
| `imageio-ffmpeg` | Bundled static ffmpeg binary — eliminates system ffmpeg setup |
| `waitress` | Production-grade WSGI server (macOS / Linux / Windows) |

Install or update all dependencies:
```bash
pip install -r requirements.txt
```

---

## 🔄 Keeping yt-dlp Updated

Platforms like YouTube, Twitter (X), and Twitch frequently change their APIs and web layouts, which can cause older download engines to fail. 

Grabio includes a built-in **update notification banner**: whenever a newer version of `yt-dlp` is published on GitHub, the banner appears with an **Update now** button to upgrade directly from your browser.

You can also update manually at any time:
```bash
pip install -U yt-dlp
```

---

## ⚖️ Legal & Disclaimer

Only download content you own, content licensed under Creative Commons or for reuse, or content you have explicit permission to save. Downloading copyrighted content may violate platform Terms of Service and applicable intellectual property laws.
