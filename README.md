# YT Grab

Local web app to save YouTube videos/playlists as MP4, MP3 or M4A.

## Setup
1. Install Python 3.9+ and **ffmpeg** (https://ffmpeg.org/download.html; make sure `ffmpeg` is on your PATH).
2. `pip install -r requirements.txt`
3. `python app.py`
4. Open http://127.0.0.1:5000

Playlists download as a single .zip. Keep yt-dlp current (`pip install -U yt-dlp`) since YouTube changes often.

Only download content you own, that is licensed for reuse, or that you have permission to save.
