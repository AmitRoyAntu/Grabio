"""Grabio — Universal video & audio downloader web app (Flask + yt-dlp).
Run:  python app.py   then open http://127.0.0.1:5000
ffmpeg is bundled via imageio-ffmpeg or system PATH.
"""
import base64, os, re, shutil, subprocess, sys, tempfile, threading, time, urllib.parse, uuid, zipfile, atexit
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, send_file, send_from_directory
import yt_dlp

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("MAX_CONTENT_LENGTH", 2 * 1024 * 1024))
ALLOW_SAVE_TO = os.environ.get("ALLOW_SAVE_TO", "false").lower() in ("true", "1")
ADMIN_KEY = os.environ.get("ADMIN_KEY")

WORK = os.path.join(tempfile.gettempdir(), "ytgrab")
os.makedirs(WORK, exist_ok=True)
JOBS = {}       # id -> dict(status, progress, message, file, name, songs, finished_at, _stop)
JOBS_LOCK = threading.Lock()

JOB_TTL    = 30 * 60   # seconds before a finished/errored job is reaped
REAP_EVERY = 10 * 60   # how often the reaper wakes up


# ── Security & Caching headers ──────────────────────────────────────────────
@app.after_request
def _apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


# ── Resolve ffmpeg ──────────────────────────────────────────────────────────
def _resolve_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg  # type: ignore
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return shutil.which("ffmpeg")

FFMPEG_BIN = _resolve_ffmpeg()


# ── Cleanup helpers ─────────────────────────────────────────────────────────
def _delete_job_folder(job_id: str, delay: float = 0.0) -> None:
    def _do():
        if delay:
            time.sleep(delay)
        shutil.rmtree(os.path.join(WORK, job_id), ignore_errors=True)
    threading.Thread(target=_do, daemon=True).start()


def _reaper() -> None:
    while True:
        time.sleep(REAP_EVERY)
        now = time.time()
        with JOBS_LOCK:
            stale = [
                jid for jid, j in list(JOBS.items())
                if j.get("status") in ("done", "error", "cancelled")
                and now - j.get("finished_at", now) > JOB_TTL
            ]
        for jid in stale:
            _delete_job_folder(jid)
            with JOBS_LOCK:
                JOBS.pop(jid, None)


def _startup_cleanup() -> None:
    try:
        for name in os.listdir(WORK):
            folder = os.path.join(WORK, name)
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass


_startup_cleanup()
threading.Thread(target=_reaper, daemon=True, name="ytgrab-reaper").start()


# ── Resolve JS runtime for yt-dlp ──────────────────────────────────────────
def _resolve_js_runtimes() -> dict:
    """Detect available JavaScript runtimes (node, deno, bun, quickjs) for yt-dlp.
    Recent yt-dlp releases use a JS runtime for YouTube signature & n-challenge solving.
    """
    for p in ("/opt/homebrew/bin", "/usr/local/bin"):
        if os.path.isdir(p) and p not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{p}:{os.environ.get('PATH', '')}"

    runtimes = {}
    for rt in ("deno", "node", "bun", "quickjs"):
        if shutil.which(rt):
            runtimes[rt] = {}
    return runtimes or {"deno": {}}

JS_RUNTIMES = _resolve_js_runtimes()


# ── Helpers ─────────────────────────────────────────────────────────────────
def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()[:120] or "download"


def clean_and_validate_url(raw_url: str) -> tuple[str | None, str | None]:
    """Clean and validate input URL.
    Returns (cleaned_url, error_message).
    """
    if not raw_url or not str(raw_url).strip():
        return None, "Paste a link first."

    url = str(raw_url).strip().strip("'\"<>`")
    # Clean leading fetch/curl/wget if someone pasted a terminal command or snippet
    url = re.sub(r"^(?:fetch|curl|wget)\s+", "", url, flags=re.IGNORECASE).strip().strip("'\"<>`")

    # If scheme is missing, check if it looks like a domain name
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        if "." in url and " " not in url:
            url = "https://" + url
        else:
            return None, f"'{raw_url.strip()}' is not a valid URL. Please enter a valid video link."

    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return None, f"'{raw_url.strip()}' is not a valid URL."

    if parsed.scheme.lower() not in ("http", "https"):
        return None, "Only HTTP and HTTPS links are supported."

    if not parsed.netloc or " " in parsed.netloc:
        return None, f"'{raw_url.strip()}' is not a valid URL."

    if "." not in parsed.netloc and parsed.netloc.lower() not in ("localhost",):
        return None, f"'{raw_url.strip()}' is not a valid URL."

    return url, None


# Support COOKIES_B64: base64-encoded cookies.txt — useful for cloud deployments (Render, Railway)
# where you can't upload files but CAN set environment variables.
_COOKIES_TMP: str | None = None
_cookies_b64 = os.environ.get("COOKIES_B64", "").strip()
if _cookies_b64:
    try:
        _decoded = base64.b64decode(_cookies_b64)
        _tmp = tempfile.NamedTemporaryFile(delete=False, suffix="_cookies.txt", mode="wb")
        _tmp.write(_decoded)
        _tmp.close()
        _COOKIES_TMP = _tmp.name
        atexit.register(lambda: os.unlink(_COOKIES_TMP) if _COOKIES_TMP and os.path.exists(_COOKIES_TMP) else None)
        print(f"[grabio] Loaded cookies from COOKIES_B64 → {_COOKIES_TMP}", flush=True)
    except Exception as e:
        print(f"[grabio] WARNING: Failed to decode COOKIES_B64: {e}", flush=True)

COOKIES_FILE = _COOKIES_TMP or os.environ.get("COOKIES_FILE") or (
    "cookies.txt" if os.path.isfile("cookies.txt") else None
)
PROXY_URL = os.environ.get("PROXY_URL")

# YouTube's "web" player client is blocked by Render/AWS datacenter IPs.
# "ios" and "android" clients bypass this check since they use mobile APIs.
# NOTE: Use a desktop UA for tab/playlist extraction — mobile UA gets a
# different page layout that the youtube:tab extractor can't parse.
COMMON_YTDL_OPTS: dict = {
    "extractor_args": {
        "youtube": {
            "player_client": ["ios", "android", "web"],
            "skip": ["hls", "dash"],
        },
        # Prevent the youtube:tab extractor from requesting the
        # mobile variant of the playlist/channel page.
        "youtubetab": {
            "skip": ["webpage"],
        },
    },
    "http_headers": {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    },
    "js_runtimes": JS_RUNTIMES,
    "remote_components": ["ejs:github"],
    "sleep_interval": 1,
    "sleep_interval_requests": 1,
    "retries": 5,
    "fragment_retries": 5,
}
if COOKIES_FILE:
    COMMON_YTDL_OPTS["cookiefile"] = COOKIES_FILE
if PROXY_URL:
    COMMON_YTDL_OPTS["proxy"] = PROXY_URL


def opts_for(fmt, quality, outtmpl, hook):
    base = {
        "outtmpl": outtmpl,
        "progress_hooks": [hook],
        "quiet": True,
        "noprogress": True,
        # NOTE: ignoreerrors intentionally omitted — we catch exceptions
        # in download_one() so we can surface the real error message.
        "writethumbnail": True,   # needed by EmbedThumbnail
    }
    base.update(COMMON_YTDL_OPTS)
    if FFMPEG_BIN:
        base["ffmpeg_location"] = FFMPEG_BIN
    if fmt == "mp3":
        base.update(
            format="bestaudio/best",
            postprocessors=[
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                 "preferredquality": quality or "192"},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ],
        )
    elif fmt == "m4a":
        base.update(
            format="bestaudio[ext=m4a]/bestaudio/best",
            postprocessors=[
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ],
        )
    else:  # mp4 video
        h = quality or "1080"
        base.update(
            format=f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best",
            merge_output_format="mp4",
        )
        base["writethumbnail"] = False
    return base


PARALLEL_WORKERS = 3
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", 3))
JOB_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT_JOBS)
MAX_PLAYLIST_ITEMS = int(os.environ.get("MAX_PLAYLIST_ITEMS", 25))


def _item_id(url: str, entry_id: str | None = None) -> str:
    if entry_id:
        return str(entry_id)
    if "v=" in url:
        return url.split("v=")[-1].split("&")[0]
    clean = url.split("?")[0].rstrip("/")
    if "/" in clean:
        return clean.split("/")[-1]
    return url


def run_job(job_id, urls, titles, fmt, quality,
            custom_name=None, serialize=False, save_to=None, entry_ids=None):
    """
    urls       – list of video URLs
    titles     – parallel list of song titles
    save_to    – if set, write files directly to this directory (no zip/browser download)
    entry_ids  – optional parallel list of IDs matching the frontend list items
    """
    job  = JOBS[job_id]
    stop: threading.Event = job["_stop"]

    job["message"] = "Queued…" if JOB_SEMAPHORE._value == 0 else "Starting…"
    with JOB_SEMAPHORE:
        folder = os.path.join(WORK, job_id)
        os.makedirs(folder, exist_ok=True)
        n = len(urls)

        songs = job.setdefault("songs", {})
        for i, u in enumerate(urls):
            eid = entry_ids[i] if (entry_ids and i < len(entry_ids)) else None
            vid = _item_id(u, eid)
            songs[vid] = {"status": "pending", "title": (titles[i] if titles else None) or vid}

        done_count = [0]
        lock        = threading.Lock()
        folder_lock = threading.Lock()

    def download_one(idx, url):
        eid = entry_ids[idx] if (entry_ids and idx < len(entry_ids)) else None
        vid = _item_id(url, eid)
        if stop.is_set():
            songs[vid]["status"] = "cancelled"
            return vid, False

        songs[vid]["status"] = "downloading"

        def hook(d):
            if stop.is_set():
                raise yt_dlp.utils.DownloadError("cancelled")
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                frac  = (d["downloaded_bytes"] / total) if total else 0
                with lock:
                    pct = (done_count[0] + frac) / n * 100
                    job["progress"] = round(pct, 1)
                job["message"] = f"Downloading {os.path.basename(d.get('filename', ''))}"
            elif d["status"] == "finished":
                job["message"] = "Processing…"

        with folder_lock:
            before = set(f for f in os.listdir(folder)
                         if not f.endswith((".part", ".ytdl", ".webp", ".jpg", ".png", ".zip")))

        last_error: list[str] = []

        def error_hook(d):
            if d.get("status") == "error":
                last_error.append(d.get("error", ""))

        o = opts_for(fmt, quality, os.path.join(folder, "%(title)s.%(ext)s"), hook)
        o["noplaylist"] = True
        # Attach a second hook to capture error details
        o["progress_hooks"].append(error_hook)
        try:
            with yt_dlp.YoutubeDL(o) as ydl:
                ydl.download([url])
        except yt_dlp.utils.DownloadError as exc:
            err_text = str(exc).lower()
            if "cancelled" in err_text:
                songs[vid]["status"] = "cancelled"
                return vid, False
            if "429" in err_text or "sign in" in err_text or "bot" in err_text:
                songs[vid]["status"] = "failed"
                songs[vid]["error"] = "bot_block"
                job["_bot_blocked"] = True
            else:
                songs[vid]["status"] = "failed"
                songs[vid]["error"] = str(exc)[:200]
            with lock:
                done_count[0] += 1
                job["progress"] = round(done_count[0] / n * 100, 1)
            return vid, False
        except Exception as exc:
            songs[vid]["status"] = "failed"
            songs[vid]["error"] = str(exc)[:200]
            with lock:
                done_count[0] += 1
                job["progress"] = round(done_count[0] / n * 100, 1)
            return vid, False

        with folder_lock:
            after = set(f for f in os.listdir(folder)
                        if not f.endswith((".part", ".ytdl", ".webp", ".jpg", ".png", ".zip")))

        success = bool(after - before)
        songs[vid]["status"] = "done" if success else "failed"
        with lock:
            done_count[0] += 1
            job["progress"] = round(done_count[0] / n * 100, 1)
        return vid, success

    try:
        workers = min(PARALLEL_WORKERS, n)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(download_one, i, u): (i, u) for i, u in enumerate(urls)}
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    i, url = futs[fut]
                    eid = entry_ids[i] if (entry_ids and i < len(entry_ids)) else None
                    vid = _item_id(url, eid)
                    songs[vid]["status"] = "failed"

        if stop.is_set():
            job["status"], job["message"] = "cancelled", "Download cancelled."
            job["finished_at"] = time.time()
            _delete_job_folder(job_id)
            return

        files = [f for f in os.listdir(folder)
                 if not f.endswith((".part", ".ytdl", ".webp", ".jpg", ".png", ".zip"))]
        if not files:
            if job.get("_bot_blocked"):
                raise RuntimeError(
                    "YouTube blocked this server's IP (HTTP 429 / bot detection). "
                    "To fix this, set up the COOKIES_B64 environment variable on Render with your YouTube cookies. "
                    "See the README for instructions."
                )
            raise RuntimeError("Nothing was downloaded. The video may be private, region-locked, or unavailable.")

        # ── Save-to-folder mode ─────────────────────────────────────────────
        if save_to:
            os.makedirs(save_to, exist_ok=True)
            moved = []
            for f in files:
                src  = os.path.join(folder, f)
                dest = os.path.join(save_to, f)
                # avoid overwriting: append (2), (3) … on collision
                stem, ext = os.path.splitext(f)
                counter = 2
                while os.path.exists(dest):
                    dest = os.path.join(save_to, f"{stem} ({counter}){ext}")
                    counter += 1
                shutil.move(src, dest)
                moved.append(os.path.basename(dest))
            job["status"]     = "saved"
            job["progress"]   = 100
            job["message"]    = f"Saved {len(moved)} file(s) to {save_to}"
            job["save_to"]    = save_to
            job["saved_files"]= moved
            job["finished_at"]= time.time()
            _delete_job_folder(job_id)
            return

        # ── Browser-download mode ───────────────────────────────────────────
        if len(files) == 1:
            fpath = os.path.join(folder, files[0])
            ext   = os.path.splitext(files[0])[1]
            final_name = (safe(custom_name) + ext) if custom_name else files[0]
            job["file"] = fpath
            job["name"] = final_name
        else:
            zname = safe(custom_name or "playlist")
            zpath = os.path.join(folder, f"{zname}.zip")
            sorted_files = sorted(files)
            pad  = len(str(len(sorted_files)))
            base = safe(custom_name) if custom_name else None
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
                for idx, f in enumerate(sorted_files, start=1):
                    ext      = os.path.splitext(f)[1]
                    orig_stem= os.path.splitext(f)[0]
                    if base and serialize:
                        arc_name = f"{str(idx).zfill(pad)} {base}{ext}"
                    elif base:
                        arc_name = f"{base} - {orig_stem}{ext}"
                    else:
                        arc_name = f
                    z.write(os.path.join(folder, f), arc_name)
            job["file"], job["name"] = zpath, f"{zname}.zip"

        job["status"], job["progress"], job["message"] = "done", 100, "Ready"
        job["finished_at"] = time.time()

    except Exception as e:
        job["status"], job["message"] = "error", str(e)[:300]
        job["finished_at"] = time.time()
        _delete_job_folder(job_id)


# ── Routes ──────────────────────────────────────────────────────────────────
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/robots.txt")
def robots():
    return send_from_directory("static", "robots.txt")


@app.get("/favicon.ico")
def favicon():
    return send_from_directory("static", "favicon.ico", mimetype="image/x-icon")


@app.get("/sitemap.xml")
def sitemap():
    return send_from_directory("static", "sitemap.xml", mimetype="application/xml")


@app.get("/health")
@app.get("/api/health")
def health():
    return jsonify(
        status="ok",
        timestamp=int(time.time()),
        version=yt_dlp.version.__version__,
        js_runtimes=list(JS_RUNTIMES.keys())
    )


@app.post("/api/info")
def info():
    raw_url = (request.json or {}).get("url", "")
    url, err = clean_and_validate_url(raw_url)
    if err:
        return jsonify(error=err), 400
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
        }
        ydl_opts.update(COMMON_YTDL_OPTS)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            i = ydl.extract_info(url, download=False)
        # If extract_flat returned nothing useful, retry without it
        # (some playlist pages require a full fetch to be recognized)
        if not i:
            ydl_opts2 = {"quiet": True, "skip_download": True}
            ydl_opts2.update(COMMON_YTDL_OPTS)
            with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
                i = ydl.extract_info(url, download=False)
        if not i:
            return jsonify(error="Couldn't read that link. The video or playlist may be private, unavailable, or blocked in the server region."), 400
        entries = i.get("entries")
        items = None
        if entries is not None:
            items = [
                {
                    "id":             e["id"],
                    # Full URL so the downloader works for any platform,
                    # not just YouTube (where we'd reconstruct watch?v=ID)
                    "webpage_url":    (e.get("webpage_url") or e.get("url")
                                       or f"https://www.youtube.com/watch?v={e['id']}"),
                    "title":          e.get("title") or e["id"],
                    "duration":       e.get("duration"),
                    "filesize_approx":e.get("filesize_approx"),
                }
                for e in entries
                if e and e.get("id") and not str(e.get("title","")).startswith(("[Private","[Deleted"))
            ]
        thumb = i.get("thumbnail")
        if not thumb and i.get("thumbnails"):
            thumb = i["thumbnails"][-1].get("url")
        channel = i.get("uploader") or i.get("channel") or i.get("uploader_id") or i.get("creator")
        title = i.get("title") or (i.get("description", "").split("\n")[0][:80] if i.get("description") else None)

        return jsonify(
            title=title,
            is_playlist=items is not None,
            entries=items or [],
            count=len(items) if items is not None else 1,
            thumbnail=thumb,
            channel=channel,
            duration=i.get("duration"),
            filesize_approx=i.get("filesize_approx"),
        )
    except Exception as e:
        return jsonify(error=f"Couldn't read that link: {str(e)[:200]}"), 400


@app.post("/api/download")
def download():
    d = request.json or {}
    job_id = uuid.uuid4().hex[:12]
    stop   = threading.Event()
    JOBS[job_id] = dict(status="running", progress=0, message="Starting…",
                        songs={}, _stop=stop)
    song_titles = d.get("titles") or []

    # video_urls: list of full URLs sent by the frontend (works for all platforms).
    # ids: list of item IDs (YouTube IDs, tweet IDs, Twitch VOD/clip IDs).
    entry_ids = [str(i) for i in (d.get("ids") or []) if i]
    raw_video_urls = [u for u in (d.get("video_urls") or []) if u]
    video_urls = []
    for u in raw_video_urls:
        cu, _ = clean_and_validate_url(u)
        if cu:
            video_urls.append(cu)

    if not video_urls:
        if entry_ids and all(re.fullmatch(r"[\w-]{6,20}", i) for i in entry_ids):
            video_urls = [f"https://www.youtube.com/watch?v={i}" for i in entry_ids]
        else:
            raw_url = d.get("url", "")
            clean_url, err = clean_and_validate_url(raw_url)
            if err:
                return jsonify(error=err), 400
            video_urls = [clean_url]
            if not entry_ids:
                entry_ids = [_item_id(clean_url)]

    if not video_urls:
        return jsonify(error="No valid URLs provided to download."), 400

    if len(video_urls) > MAX_PLAYLIST_ITEMS:
        return jsonify(error=f"Maximum {MAX_PLAYLIST_ITEMS} items per batch allowed on public server."), 400

    while len(song_titles) < len(video_urls):
        song_titles.append(None)

    # Validate save_to path if provided
    save_to = (d.get("save_to") or "").strip() or None
    if save_to:
        if not ALLOW_SAVE_TO:
            return jsonify(error="Server folder saving is disabled in production mode."), 403
        save_to = os.path.expanduser(save_to)
        if not os.path.isabs(save_to):
            return jsonify(error="save_to must be an absolute path."), 400

    threading.Thread(
        target=run_job, daemon=True,
        args=(job_id, video_urls, song_titles, d.get("format","mp4"), d.get("quality")),
        kwargs=dict(custom_name=d.get("custom_name") or None,
                    serialize=bool(d.get("serialize")),
                    save_to=save_to,
                    entry_ids=entry_ids or None)
    ).start()
    return jsonify(id=job_id)


@app.post("/api/cancel/<job_id>")
def cancel(job_id):
    j = JOBS.get(job_id)
    if not j:
        return jsonify(error="Unknown job"), 404
    if j.get("status") != "running":
        return jsonify(error="Job is not running"), 400
    j["_stop"].set()
    j["message"] = "Cancelling…"
    return jsonify(ok=True)


@app.get("/api/status/<job_id>")
def status(job_id):
    j = JOBS.get(job_id)
    if not j:
        return jsonify(error="Unknown job"), 404
    return jsonify({k: j.get(k) for k in
                    ("status", "progress", "message", "name", "songs", "save_to", "saved_files")})


@app.get("/api/file/<job_id>")
def file(job_id):
    j = JOBS.get(job_id)
    if not j or j.get("status") != "done":
        return "Not ready", 404
    resp = send_file(j["file"], as_attachment=True, download_name=j["name"])
    # Generous delay (10 min) so large files stream fully over slow connections
    _delete_job_folder(job_id, delay=600.0)
    return resp


@app.get("/api/ytdlp-version")
def ytdlp_version():
    """Return installed and latest yt-dlp versions."""
    installed = yt_dlp.version.__version__
    try:
        import urllib.request, json as _json
        with urllib.request.urlopen(
            "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest",
            timeout=5
        ) as r:
            latest = _json.loads(r.read())["tag_name"]
    except Exception:
        latest = None
    return jsonify(installed=installed, latest=latest,
                   outdated=bool(latest and latest != installed))


@app.post("/api/ytdlp-update")
def ytdlp_update():
    """Run yt-dlp --update via subprocess."""
    if ADMIN_KEY and request.headers.get("X-Admin-Key") != ADMIN_KEY:
        return jsonify(ok=False, error="Unauthorized: valid X-Admin-Key required"), 401
    try:
        result = subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--update"],
            capture_output=True, text=True, timeout=60
        )
        output = (result.stdout + result.stderr).strip()
        new_ver = yt_dlp.version.__version__
        return jsonify(ok=True, output=output[:500], version=new_ver)
    except Exception as e:
        return jsonify(ok=False, error=str(e)[:200]), 500


# ── Production Error Handlers ───────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify(error="Endpoint not found"), 404
    return send_from_directory("static", "index.html")


@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify(error="Request payload too large (max 2MB)"), 413


@app.errorhandler(500)
def server_error(e):
    return jsonify(error="Internal server error"), 500


if __name__ == "__main__":
    HOST = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    PORT = int(os.environ.get("PORT", 5000))
    if FFMPEG_BIN:
        print(f"ffmpeg     : {FFMPEG_BIN}")
    else:
        print("WARNING: ffmpeg not found. Install imageio-ffmpeg or add ffmpeg to PATH.")
    if JS_RUNTIMES:
        print(f"js runtime : {', '.join(JS_RUNTIMES.keys())}")
    else:
        print("WARNING: No JS runtime found. Install Node.js or Deno for YouTube challenge solving.")
    try:
        from waitress import serve
        threads = int(os.environ.get("THREADS", 16))
        print(f"Serving on http://{HOST}:{PORT}  (waitress, {threads} threads)")
        serve(app, host=HOST, port=PORT, threads=threads)
    except ImportError:
        print(f"waitress not installed — using Flask dev server on http://{HOST}:{PORT}")
        print("  Run:  pip install waitress   for a production-grade server.")
        app.run(host=HOST, port=PORT, debug=False)
