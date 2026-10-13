"""Local YouTube downloader web app (Flask + yt-dlp).
Run:  python app.py   then open http://127.0.0.1:5000
Requires ffmpeg on PATH (needed for mp3 conversion and merging video+audio).
"""
import os, re, shutil, tempfile, threading, uuid, zipfile
from flask import Flask, jsonify, request, send_file, send_from_directory
import yt_dlp

app = Flask(__name__, static_folder="static")
WORK = os.path.join(tempfile.gettempdir(), "ytgrab")
os.makedirs(WORK, exist_ok=True)
JOBS = {}  # id -> dict(status, progress, message, file, name)


def safe(name):
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip()[:120] or "download"


def opts_for(fmt, quality, outtmpl, hook):
    base = {
        "outtmpl": outtmpl,
        "progress_hooks": [hook],
        "quiet": True,
        "noprogress": True,
        "ignoreerrors": True,
    }
    if fmt == "mp3":
        base.update(
            format="bestaudio/best",
            postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3",
                             "preferredquality": quality or "192"}],
        )
    elif fmt == "m4a":
        base.update(
            format="bestaudio[ext=m4a]/bestaudio/best",
            postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
        )
    else:  # mp4 video
        h = quality or "1080"
        base.update(
            format=f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best",
            merge_output_format="mp4",
        )
    return base


def run_job(job_id, urls, title, fmt, quality):
    job = JOBS[job_id]
    folder = os.path.join(WORK, job_id)
    os.makedirs(folder, exist_ok=True)
    n = len(urls)
    state = {"i": 0}

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                job["progress"] = round((state["i"] + d["downloaded_bytes"] / total) / n * 100, 1)
            job["message"] = f"({state['i'] + 1}/{n}) Downloading {os.path.basename(d.get('filename', ''))}"
        elif d["status"] == "finished":
            job["message"] = f"({state['i'] + 1}/{n}) Processing…"

    try:
        tmpl = os.path.join(folder, "%(title)s.%(ext)s")
        for i, u in enumerate(urls):
            state["i"] = i
            o = opts_for(fmt, quality, tmpl, hook)
            o["noplaylist"] = True
            with yt_dlp.YoutubeDL(o) as ydl:
                ydl.download([u])
        files = [f for f in os.listdir(folder)
                 if not f.endswith((".part", ".ytdl", ".webp", ".jpg", ".zip"))]
        if not files:
            raise RuntimeError("Nothing was downloaded. The video may be private or unavailable.")
        if len(files) == 1:
            job["file"] = os.path.join(folder, files[0])
            job["name"] = files[0]
        else:
            zname = safe(title or "playlist")
            zpath = os.path.join(folder, f"{zname}.zip")
            with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
                for f in sorted(files):
                    z.write(os.path.join(folder, f), f)
            job["file"], job["name"] = zpath, f"{zname}.zip"
        job["status"], job["progress"], job["message"] = "done", 100, "Ready"
    except Exception as e:
        job["status"], job["message"] = "error", str(e)[:300]


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
                {"id": e["id"], "title": e.get("title") or e["id"], "duration": e.get("duration")}
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
        )
    except Exception as e:
        return jsonify(error=f"Couldn't read that link: {str(e)[:200]}"), 400


@app.post("/api/download")
def download():
    d = request.json or {}
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = dict(status="running", progress=0, message="Starting…")
    ids = [i for i in (d.get("ids") or []) if re.fullmatch(r"[\w-]{6,20}", str(i))]
    urls = [f"https://www.youtube.com/watch?v={i}" for i in ids] or [d.get("url", "")]
    threading.Thread(target=run_job, daemon=True, args=(
        job_id, urls, d.get("title"), d.get("format", "mp4"), d.get("quality"))).start()
    return jsonify(id=job_id)


@app.get("/api/status/<job_id>")
def status(job_id):
    j = JOBS.get(job_id)
    if not j:
        return jsonify(error="Unknown job"), 404
    return jsonify({k: j.get(k) for k in ("status", "progress", "message", "name")})


@app.get("/api/file/<job_id>")
def file(job_id):
    j = JOBS.get(job_id)
    if not j or j.get("status") != "done":
        return "Not ready", 404
    return send_file(j["file"], as_attachment=True, download_name=j["name"])


if __name__ == "__main__":
    if not shutil.which("ffmpeg"):
        print("WARNING: ffmpeg not found on PATH. MP3 and 1080p+ downloads will fail.")
    app.run(host="127.0.0.1", port=5000, debug=False)
