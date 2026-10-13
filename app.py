"""Local YouTube downloader web app (Flask + yt-dlp).
Run:  python app.py   then open http://127.0.0.1:5000
ffmpeg is bundled via imageio-ffmpeg (pip install imageio-ffmpeg).
Falls back to any ffmpeg found on PATH.
"""
import os, re, shutil, subprocess, sys, tempfile, threading, time, uuid, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, send_file, send_from_directory
import yt_dlp

app = Flask(__name__, static_folder="static")
WORK = os.path.join(tempfile.gettempdir(), "ytgrab")
os.makedirs(WORK, exist_ok=True)
JOBS = {}       # id -> dict(status, progress, message, file, name, songs, finished_at, _stop)
JOBS_LOCK = threading.Lock()

JOB_TTL    = 30 * 60   # seconds before a finished/errored job is reaped
REAP_EVERY = 10 * 60   # how often the reaper wakes up


# ── Resolve ffmpeg ──────────────────────────────────────────────────────────
def _resolve_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
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


# ── Helpers ─────────────────────────────────────────────────────────────────
def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()[:120] or "download"


def opts_for(fmt, quality, outtmpl, hook):
    base = {
        "outtmpl": outtmpl,
        "progress_hooks": [hook],
        "quiet": True,
        "noprogress": True,
        "ignoreerrors": True,
        "writethumbnail": True,   # needed by EmbedThumbnail
    }
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


def run_job(job_id, urls, titles, fmt, quality,
            custom_name=None, serialize=False, save_to=None):
    """
    urls     – list of video URLs
    titles   – parallel list of song titles
    save_to  – if set, write files directly to this directory (no zip/browser download)
    """
    job  = JOBS[job_id]
    stop: threading.Event = job["_stop"]

    folder = os.path.join(WORK, job_id)
    os.makedirs(folder, exist_ok=True)
    n = len(urls)

    songs = job.setdefault("songs", {})
    for i, u in enumerate(urls):
        vid = u.split("v=")[-1] if "v=" in u else u
        songs[vid] = {"status": "pending", "title": (titles[i] if titles else None) or vid}

    done_count = [0]
    lock        = threading.Lock()
    folder_lock = threading.Lock()

    def download_one(idx, url):
        if stop.is_set():
            vid = url.split("v=")[-1] if "v=" in url else url
            songs[vid]["status"] = "cancelled"
            return vid, False

        vid = url.split("v=")[-1] if "v=" in url else url
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

        o = opts_for(fmt, quality, os.path.join(folder, "%(title)s.%(ext)s"), hook)
        o["noplaylist"] = True
        with yt_dlp.YoutubeDL(o) as ydl:
            ydl.download([url])

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
            futs = {pool.submit(download_one, i, u): u for i, u in enumerate(urls)}
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    url = futs[fut]
                    vid = url.split("v=")[-1] if "v=" in url else url
                    songs[vid]["status"] = "failed"

        if stop.is_set():
            job["status"], job["message"] = "cancelled", "Download cancelled."
            job["finished_at"] = time.time()
            _delete_job_folder(job_id)
            return

        files = [f for f in os.listdir(folder)
                 if not f.endswith((".part", ".ytdl", ".webp", ".jpg", ".png", ".zip"))]
        if not files:
            raise RuntimeError("Nothing was downloaded. The video may be private or unavailable.")

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


@app.post("/api/info")
def info():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify(error="Paste a link first."), 400
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": "in_playlist",
                               "skip_download": True}) as ydl:
            i = ydl.extract_info(url, download=False)
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
        return jsonify(
            title=i.get("title"),
            is_playlist=items is not None,
            entries=items or [],
            count=len(items) if items is not None else 1,
            thumbnail=i.get("thumbnail"),
            channel=i.get("uploader") or i.get("channel"),
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
    # ids: legacy YouTube-only path — kept for backward compatibility.
    video_urls = [u for u in (d.get("video_urls") or []) if u]
    if not video_urls:
        ids = [i for i in (d.get("ids") or []) if re.fullmatch(r"[\w-]{6,20}", str(i))]
        video_urls = ([f"https://www.youtube.com/watch?v={i}" for i in ids]
                      or [d.get("url", "")])

    while len(song_titles) < len(video_urls):
        song_titles.append(None)

    # Validate save_to path if provided
    save_to = (d.get("save_to") or "").strip() or None
    if save_to:
        save_to = os.path.expanduser(save_to)
        if not os.path.isabs(save_to):
            return jsonify(error="save_to must be an absolute path."), 400

    threading.Thread(
        target=run_job, daemon=True,
        args=(job_id, video_urls, song_titles, d.get("format","mp4"), d.get("quality")),
        kwargs=dict(custom_name=d.get("custom_name") or None,
                    serialize=bool(d.get("serialize")),
                    save_to=save_to)
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
    _delete_job_folder(job_id, delay=3.0)
    with JOBS_LOCK:
        JOBS.pop(job_id, None)
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


if __name__ == "__main__":
    HOST, PORT = "127.0.0.1", 5000
    if FFMPEG_BIN:
        print(f"ffmpeg : {FFMPEG_BIN}")
    else:
        print("WARNING: ffmpeg not found. Install imageio-ffmpeg or add ffmpeg to PATH.")
    try:
        from waitress import serve
        print(f"Serving on http://{HOST}:{PORT}  (waitress)")
        serve(app, host=HOST, port=PORT, threads=8)
    except ImportError:
        print(f"waitress not installed — using Flask dev server on http://{HOST}:{PORT}")
        print("  Run:  pip install waitress   for a production-grade server.")
        app.run(host=HOST, port=PORT, debug=False)
