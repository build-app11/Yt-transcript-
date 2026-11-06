import json
import os
import re
import urllib.parse
import urllib.request

import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
)

st.set_page_config(page_title="Transkrip YouTube", page_icon="📝", layout="wide")

PREFERRED_LANGS = ["id", "en"]
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


# ---------- Helper ----------
def extract_video_id(value: str):
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


def build_api() -> YouTubeTranscriptApi:
    proxy_url = os.environ.get("PROXY_URL", "").strip()
    if proxy_url:
        from youtube_transcript_api.proxies import GenericProxyConfig

        return YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        )
    return YouTubeTranscriptApi()


def fetch_title(video_id: str):
    try:
        target = f"https://www.youtube.com/watch?v={video_id}"
        url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(target)
        with urllib.request.urlopen(url, timeout=5) as resp:
            info = json.load(resp)
        return info.get("title"), info.get("author_name")
    except Exception:
        return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def load_transcript(video_id: str, lang: str = ""):
    """Ambil transkrip. Hasil di-cache 1 jam; error tidak di-cache."""
    api = build_api()
    tlist = api.list(video_id)
    available = [
        {"code": t.language_code, "name": t.language, "generated": t.is_generated}
        for t in tlist
    ]
    if lang:
        transcript = tlist.find_transcript([lang])
    else:
        try:
            transcript = tlist.find_transcript(PREFERRED_LANGS)
        except NoTranscriptFound:
            transcript = next(iter(tlist))

    fetched = transcript.fetch()
    title, author = fetch_title(video_id)
    return {
        "video_id": video_id,
        "title": title or video_id,
        "author": author,
        "language_code": transcript.language_code,
        "is_generated": transcript.is_generated,
        "available": available,
        "snippets": [
            {"text": s.text.replace("\n", " "), "start": s.start, "duration": s.duration}
            for s in fetched
        ],
    }


def clock(sec: float) -> str:
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def srt_clock(sec: float) -> str:
    ms = round(sec * 1000)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, r = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{r:03d}"


def to_srt(snippets) -> str:
    blocks = []
    for i, s in enumerate(snippets, 1):
        end = s["start"] + s["duration"]
        blocks.append(f"{i}\n{srt_clock(s['start'])} --> {srt_clock(end)}\n{s['text']}\n")
    return "\n".join(blocks)


def md_escape(text: str) -> str:
    return re.sub(r"([\\`*_{}\[\]()#+!|~$<>])", r"\\\1", text)


def highlight(text: str, query: str) -> str:
    if not query:
        return md_escape(text)
    parts = re.split(f"({re.escape(query)})", text, flags=re.IGNORECASE)
    out = []
    for p in parts:
        if p and p.lower() == query.lower():
            out.append(f":orange-background[{md_escape(p)}]")
        else:
            out.append(md_escape(p))
    return "".join(out)


# ---------- UI ----------
st.title("Transkrip YouTube")
st.write("Tempel tautan video YouTube untuk mengambil transkripnya.")

url = st.text_input("Tautan video", placeholder="https://www.youtube.com/watch?v=...")

if not url:
    st.stop()

video_id = extract_video_id(url)
if not video_id:
    st.error("Tautan YouTube tidak dikenali. Tempel tautan video yang lengkap.")
    st.stop()

try:
    with st.spinner("Mengambil transkrip…"):
        data = load_transcript(video_id)
        # Bahasa pilihan pengguna (bila beda dari bahasa default)
        codes = [a["code"] for a in data["available"]]
        labels = {
            a["code"]: a["name"] + (" (otomatis)" if a["generated"] else "")
            for a in data["available"]
        }
        default_idx = codes.index(data["language_code"]) if data["language_code"] in codes else 0

    col_lang, col_time, col_q = st.columns([2, 1, 2])
    with col_lang:
        chosen = st.selectbox(
            "Bahasa transkrip", codes, index=default_idx, format_func=lambda c: labels[c]
        )
    with col_time:
        show_time = st.toggle("Tampilkan waktu", value=True)
    with col_q:
        query = st.text_input("Cari di transkrip", placeholder="Kata kunci").strip()

    if chosen != data["language_code"]:
        with st.spinner("Mengganti bahasa…"):
            data = load_transcript(video_id, chosen)

except TranscriptsDisabled:
    st.error("Pemilik video menonaktifkan transkrip untuk video ini.")
    st.stop()
except NoTranscriptFound:
    st.error("Transkrip untuk bahasa yang dipilih tidak ditemukan.")
    st.stop()
except VideoUnavailable:
    st.error("Video tidak tersedia. Periksa tautannya atau coba video lain.")
    st.stop()
except RequestBlocked:
    st.error(
        "YouTube memblokir permintaan dari IP server ini (umum di layanan cloud seperti "
        "Codespaces). Atur variabel PROXY_URL lalu jalankan ulang. Lihat README."
    )
    st.stop()
except (CouldNotRetrieveTranscript, StopIteration) as exc:
    st.error(f"Transkrip tidak bisa diambil ({exc.__class__.__name__}).")
    st.stop()

snippets = data["snippets"]

st.subheader(data["title"])
st.caption(
    " · ".join(
        filter(
            None,
            [
                data["author"],
                f"{len(snippets)} baris",
                "dibuat otomatis" if data["is_generated"] else "dibuat manual",
            ],
        )
    )
)

with st.container():
    if query:
        matches = [s for s in snippets if query.lower() in s["text"].lower()]
        only_matches = st.checkbox(f"Hanya tampilkan baris yang cocok ({len(matches)} baris)", value=True)
        view = matches if only_matches else snippets
    else:
        view = snippets

    lines = []
    for s in view:
        body = highlight(s["text"], query)
        if show_time:
            link = f"https://www.youtube.com/watch?v={video_id}&t={int(s['start'])}s"
            lines.append(f"[`{clock(s['start'])}`]({link}) &nbsp; {body}")
        else:
            lines.append(body)

    with st.container(height=560, border=True):
        if lines:
            st.markdown("\n\n".join(lines))
        else:
            st.info("Tidak ada baris yang cocok.")

plain = "\n".join(
    (f"[{clock(s['start'])}] " if show_time else "") + s["text"] for s in snippets
)
safe = re.sub(r"[^\w\- ]+", "", data["title"]).strip()[:80] or video_id

c1, c2, _ = st.columns([1, 1, 3])
c1.download_button("Unduh .txt", plain, file_name=f"{safe}.txt", mime="text/plain")
c2.download_button("Unduh .srt", to_srt(snippets), file_name=f"{safe}.srt", mime="application/x-subrip")

with st.expander("Teks polos (pakai ikon salin di pojok kanan atas kotak)"):
    st.code(plain, language=None, wrap_lines=True)
