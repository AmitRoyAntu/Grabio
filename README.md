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

## 🛡️ Fixing YouTube Bot-Detection on Cloud (HTTP 429)

YouTube blocks requests from cloud/datacenter IPs (Render, Railway, AWS, etc.) by default. You have two ways to solve this:

### Method 1: Use a Free Proxy via `PROXY_URL` (Recommended — Permanent & Zero Maintenance)

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

---

### Method 2: Set up `COOKIES_B64` on Render

If you prefer using your YouTube account cookies:

**Step 1 — Export your YouTube cookies**
1. In Chrome, install **[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)**
2. Go to **[youtube.com](https://youtube.com)** while **logged in**
3. Click the extension → **Export** → **youtube.com** → save as `cookies.txt`

**Step 2 — Encode the file**
```bash
# macOS / Linux — copies encoded value to clipboard
base64 -i ~/Downloads/cookies.txt | tr -d '\n' | pbcopy
```

**Step 3 — Add to Render**
1. Render Dashboard → your Grabio service → **Environment**
2. Add environment variable:
   - **Key:** `COOKIES_B64`
   - **Value:** paste from clipboard
3. Click **Save Changes** — Render auto-redeploys

**Confirmation:** You'll see this line in Render logs once cookies are loaded:
```text
[grabio] Loaded cookies from COOKIES_B64 → /tmp/xxx_cookies.txt
```

> **Note:** YouTube cookies expire after ~1–2 weeks. When downloads start failing again, export fresh cookies and update the `COOKIES_B64` value on Render.

### Environment Variables Reference

| Variable | Description |
|---|---|
| `PROXY_URL` | **(Recommended)** HTTP/SOCKS5 proxy URL to bypass cloud datacenter IP blocks |
| `COOKIES_B64` | Base64-encoded `cookies.txt` — alternative fix for YouTube bot-detection |
| `COOKIES_FILE` | Path to a local `cookies.txt` file (for self-hosted/VPS) |
| `PORT` | Port to bind (auto-set by Render/Railway, defaults to `5000`) |

---

## ⚖️ Legal & Disclaimer

Only download content you own, content licensed under Creative Commons or for reuse, or content you have explicit permission to save. Downloading copyrighted content may violate platform Terms of Service and applicable intellectual property laws.
