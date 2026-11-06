import json
import os
import re
import urllib.parse
import urllib.request

from flask import Flask, jsonify, request, send_from_directory
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

app = Flask(__name__, static_folder="static", static_url_path="/static")

# Urutan bahasa yang dicoba lebih dulu bila pengguna tidak memilih bahasa.
PREFERRED_LANGS = ["id", "en"]

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def build_api() -> YouTubeTranscriptApi:
    """Buat klien API. Opsional: pakai proxy lewat variabel PROXY_URL."""
    proxy_url = os.environ.get("PROXY_URL", "").strip()
    if proxy_url:
        from youtube_transcript_api.proxies import GenericProxyConfig

        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        )
    return YouTubeTranscriptApi()


def extract_video_id(value: str):
    """Ambil ID video dari berbagai bentuk tautan YouTube."""
    value = (value or "").strip()
    if VIDEO_ID_RE.match(value):
        return value

    if not re.match(r"^https?://", value):
        value = "https://" + value
    parsed = urllib.parse.urlparse(value)
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")

    if host == "youtu.be":
        candidate = parsed.path.strip("/").split("/")[0]
    elif host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        if parsed.path == "/watch":
            candidate = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        else:
            m = re.match(r"^/(?:shorts|embed|live|v)/([^/?]+)", parsed.path)
            candidate = m.group(1) if m else ""
    else:
        return None

    return candidate if VIDEO_ID_RE.match(candidate) else None


def fetch_title(video_id: str):
    """Judul video lewat oEmbed. Gagal diam-diam bila tidak tersedia."""
    try:
        target = f"https://www.youtube.com/watch?v={video_id}"
        url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(target)
        with urllib.request.urlopen(url, timeout=5) as resp:
            info = json.load(resp)
        return info.get("title"), info.get("author_name")
    except Exception:
        return None, None


def error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/transcript")
def get_transcript():
    video_id = extract_video_id(request.args.get("url", ""))
    if not video_id:
        return error("Tautan YouTube tidak dikenali. Tempel tautan video yang lengkap.")

    lang = request.args.get("lang", "").strip()
    api = build_api()

    try:
        transcript_list = api.list(video_id)
        available = [
            {
                "code": t.language_code,
                "name": t.language,
                "generated": t.is_generated,
            }
            for t in transcript_list
        ]

        if lang:
            transcript = transcript_list.find_transcript([lang])
        else:
            try:
                transcript = transcript_list.find_transcript(PREFERRED_LANGS)
            except NoTranscriptFound:
                transcript = next(iter(transcript_list))

        fetched = transcript.fetch()
    except TranscriptsDisabled:
        return error("Pemilik video menonaktifkan transkrip untuk video ini.", 404)
    except NoTranscriptFound:
        return error("Transkrip untuk bahasa yang dipilih tidak ditemukan.", 404)
    except VideoUnavailable:
        return error("Video tidak tersedia. Periksa tautannya atau coba video lain.", 404)
    except RequestBlocked:
        return error(
            "YouTube memblokir permintaan dari alamat IP server ini (umum terjadi di "
            "layanan cloud seperti Codespaces). Atur PROXY_URL lalu jalankan ulang; "
            "lihat README.",
            503,
        )
    except CouldNotRetrieveTranscript as exc:
        return error(f"Transkrip tidak bisa diambil: {exc.__class__.__name__}.", 502)
    except StopIteration:
        return error("Video ini tidak punya transkrip.", 404)

    title, author = fetch_title(video_id)

    return jsonify(
        {
            "video_id": video_id,
            "title": title or video_id,
            "author": author,
            "language": transcript.language,
            "language_code": transcript.language_code,
            "is_generated": transcript.is_generated,
            "available": available,
            "snippets": [
                {"text": s.text, "start": s.start, "duration": s.duration}
                for s in fetched
            ],
        }
    )


if __name__ == "__main__":
    # 0.0.0.0 diperlukan agar port bisa diteruskan oleh Codespaces.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
