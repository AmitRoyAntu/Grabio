# Grabio

A fast, modern web app to download videos and audio from **YouTube, Twitch, Twitter (X), TikTok, Instagram, and Facebook** — as **MP4, MP3, or M4A**. 

🌐 **Live Demo:** [https://grabio.onrender.com/](https://grabio.onrender.com/)

Runs 100% locally on your computer with zero cloud limits, ads, accounts, or tracking — or deploy it to the cloud with one click.

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

## ☁️ Cloud Deployment (Render / Railway / Docker)

Grabio is deployable to any cloud platform that supports Docker. The live instance runs on **[Render.com](https://render.com)** (free tier).

### Deploying to Render

1. Push this repo to GitHub
2. Sign in at **[dashboard.render.com](https://dashboard.render.com)** → **New +** → **Web Service**
3. Connect your GitHub repository
4. Select **Docker** as the Runtime (or use the included `render.yaml` Blueprint)
5. Set Instance Type to **Free** → **Deploy Web Service**

---

## 🛡️ Cloud Deployment & YouTube Bot-Detection (HTTP 429)

YouTube blocks requests from cloud/datacenter IPs (Render, Railway, AWS, etc.) by default. 

### Fix: Use a Free Proxy via `PROXY_URL` (Permanent & Zero Maintenance)

Routing yt-dlp traffic through a proxy bypasses YouTube's datacenter IP block without needing any Google account or cookies.

1. Sign up for free at **[Webshare.io](https://www.webshare.io)** (10 free proxies forever, no credit card required).
2. In your Webshare dashboard → **Proxy List**, copy your proxy credentials (or your rotating proxy endpoint).
3. On **[dashboard.render.com](https://dashboard.render.com)** → your Grabio service → **Environment**, add:
   - **Key:** `PROXY_URL`
   - **Value:** `http://username:password@ip:port` (or `socks5://...`)
4. Click **Save Changes** — Render will auto-redeploy.

**Confirmation in Render logs:**
```text
[grabio] Proxy enabled → http://***:***@p.webshare.io:80
```

### Environment Variables

| Variable | Description |
|---|---|
| `PROXY_URL` | HTTP/SOCKS5 proxy URL to bypass cloud datacenter IP blocks |
| `PORT` | Port to bind (auto-set by Render/Railway, defaults to `5000`) |

---

## ⚖️ Legal & Disclaimer

Only download content you own, content licensed under Creative Commons or for reuse, or content you have explicit permission to save. Downloading copyrighted content may violate platform Terms of Service and applicable intellectual property laws.
