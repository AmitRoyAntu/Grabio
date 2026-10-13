"""Local YouTube downloader web app (Flask + yt-dlp).
Run:  python app.py   then open http://127.0.0.1:5000
ffmpeg is bundled via imageio-ffmpeg (pip install imageio-ffmpeg).
Falls back to any ffmpeg found on PATH.
"""
import os, re, shutil, tempfile, threading, time, uuid, zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request, send_file, send_from_directory
import yt_dlp

app = Flask(__name__, static_folder="static")
WORK = os.path.join(tempfile.gettempdir(), "ytgrab")
os.makedirs(WORK, exist_ok=True)
JOBS = {}  # id -> dict(status, progress, message, file, name, songs, finished_at)
JOBS_LOCK = threading.Lock()

JOB_TTL   = 30 * 60   # seconds before a finished/errored job is reaped
REAP_EVERY = 10 * 60  # how often the reaper wakes up

# ── Resolve ffmpeg ─────────────────────────────────────────────────────────
# Prefer the static binary bundled with imageio-ffmpeg so users don't need
# Homebrew. Falls back to whatever is on PATH.
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


# ── Cleanup helpers ────────────────────────────────────────────────────────
def _delete_job_folder(job_id: str, delay: float = 0.0) -> None:
    """Delete the temp folder for a job, optionally after a short delay."""
    def _do():
        if delay:
            time.sleep(delay)
        folder = os.path.join(WORK, job_id)
        try:
            shutil.rmtree(folder, ignore_errors=True)
        except Exception:
            pass
    threading.Thread(target=_do, daemon=True).start()


def _reaper() -> None:
    """Background thread: every REAP_EVERY seconds, remove old jobs."""
    while True:
        time.sleep(REAP_EVERY)
        now = time.time()
        with JOBS_LOCK:
            stale = [
                jid for jid, j in list(JOBS.items())
                if j.get("status") in ("done", "error")
                and now - j.get("finished_at", now) > JOB_TTL
            ]
        for jid in stale:
            _delete_job_folder(jid)
            with JOBS_LOCK:
                JOBS.pop(jid, None)


def _startup_cleanup() -> None:
    """Wipe any temp folders left over from a previous server run."""
    try:
        for name in os.listdir(WORK):
            folder = os.path.join(WORK, name)
            if os.path.isdir(folder):
                shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        pass


_startup_cleanup()
threading.Thread(target=_reaper, daemon=True, name="ytgrab-reaper").start()


def safe(name):
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
        # No writethumbnail for video — it's already inside the container
        base["writethumbnail"] = False
    return base


PARALLEL_WORKERS = 3   # songs downloaded simultaneously


def run_job(job_id, urls, titles, fmt, quality, custom_name=None, serialize=False):
    """
    urls   – list of video URLs (one per song)
    titles – parallel list of song titles (same length, may be None entries)
    """
    job = JOBS[job_id]
    folder = os.path.join(WORK, job_id)
    os.makedirs(folder, exist_ok=True)
    n = len(urls)

    # Initialise per-song state
    songs = job.setdefault("songs", {})
    for i, u in enumerate(urls):
        vid = u.split("v=")[-1] if "v=" in u else u
        songs[vid] = {"status": "pending", "title": (titles[i] if titles else None) or vid}

    # Thread-safe progress: track bytes downloaded per song slot
    done_count = [0]          # finished songs
    lock = threading.Lock()
    folder_lock = threading.Lock()  # serialize listdir snapshots

    def download_one(idx, url):
        """Download a single URL; updates job state. Returns (vid, success)."""
        vid = url.split("v=")[-1] if "v=" in url else url
        songs[vid]["status"] = "downloading"

        def hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                frac  = (d["downloaded_bytes"] / total) if total else 0
                with lock:
                    pct = (done_count[0] + frac) / n * 100
                    job["progress"] = round(pct, 1)
                job["message"] = f"Downloading {os.path.basename(d.get('filename', ''))}"
            elif d["status"] == "finished":
                job["message"] = f"Processing…"

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
                except Exception as exc:
                    url = futs[fut]
                    vid = url.split("v=")[-1] if "v=" in url else url
                    songs[vid]["status"] = "failed"

        files = [f for f in os.listdir(folder)
                 if not f.endswith((".part", ".ytdl", ".webp", ".jpg", ".png", ".zip"))]
        if not files:
            raise RuntimeError("Nothing was downloaded. The video may be private or unavailable.")
        if len(files) == 1:
            fpath = os.path.join(folder, files[0])
            ext = os.path.splitext(files[0])[1]
            final_name = (safe(custom_name) + ext) if custom_name else files[0]
            job["file"] = fpath
            job["name"] = final_name
        else:
            zname = safe(custom_name or "playlist")
            zpath = os.path.join(folder, f"{zname}.zip")
            sorted_files = sorted(files)
            pad = len(str(len(sorted_files)))
            base = safe(custom_name) if custom_name else None
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
                for idx, f in enumerate(sorted_files, start=1):
                    ext = os.path.splitext(f)[1]
                    orig_stem = os.path.splitext(f)[0]
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


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.post("/api/info")
def info():
    url = (request.json or {}).get("url", "").strip()
    if not url:
        return jsonify(error="Paste a YouTube link first."), 400
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": "in_playlist",
                               "skip_download": True}) as ydl:
            i = ydl.extract_info(url, download=False)
        entries = i.get("entries")
        items = None
        if entries is not None:
            items = [
                {
                    "id": e["id"],
                    "title": e.get("title") or e["id"],
                    "duration": e.get("duration"),
                    "filesize_approx": e.get("filesize_approx"),
                }
                for e in entries
                if e and e.get("id") and not str(e.get("title", "")).startswith(("[Private", "[Deleted"))
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
    JOBS[job_id] = dict(status="running", progress=0, message="Starting…", songs={})
    ids = [i for i in (d.get("ids") or []) if re.fullmatch(r"[\w-]{6,20}", str(i))]
    song_titles = d.get("titles") or []
    urls = [f"https://www.youtube.com/watch?v={i}" for i in ids] or [d.get("url", "")]
    while len(song_titles) < len(urls):
        song_titles.append(None)
    threading.Thread(target=run_job, daemon=True, args=(
        job_id, urls, song_titles, d.get("format", "mp4"), d.get("quality"),
        d.get("custom_name") or None), kwargs={"serialize": bool(d.get("serialize"))}).start()
    return jsonify(id=job_id)


@app.get("/api/status/<job_id>")
def status(job_id):
    j = JOBS.get(job_id)
    if not j:
        return jsonify(error="Unknown job"), 404
    return jsonify({k: j.get(k) for k in ("status", "progress", "message", "name", "songs")})


@app.get("/api/file/<job_id>")
def file(job_id):
    j = JOBS.get(job_id)
    if not j or j.get("status") != "done":
        return "Not ready", 404
    resp = send_file(j["file"], as_attachment=True, download_name=j["name"])
    # Delete the temp folder a couple of seconds after the response is sent
    # so Flask finishes streaming before we remove the file.
    _delete_job_folder(job_id, delay=3.0)
    with JOBS_LOCK:
        JOBS.pop(job_id, None)
    return resp


if __name__ == "__main__":
    if FFMPEG_BIN:
        print(f"ffmpeg: {FFMPEG_BIN}")
    else:
        print("WARNING: ffmpeg not found. Install imageio-ffmpeg (`uv pip install imageio-ffmpeg`) "
              "or add ffmpeg to PATH. MP3/M4A conversion and 1080p+ merging will fail without it.")
    app.run(host="127.0.0.1", port=5000, debug=False)
