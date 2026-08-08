import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.id3 import APIC, ID3, TALB, TCON, TDRC, TIT2, TPOS, TPE1, TRCK
from mutagen.mp3 import MP3

_FILENAME_CHAR_MAP = str.maketrans(
    {
        "\\": "＼",
        "/": "／",
        ":": "：",
        "*": "＊",
        "?": "？",
        '"': "＂",
        "<": "＜",
        ">": "＞",
        "|": "｜",
    }
)

_WIN_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _is_win_reserved(name):
    base = (name or "").split(".")[0].strip().upper()
    return base in _WIN_RESERVED_NAMES


def sanitize_name(name):
    text = unicodedata.normalize("NFC", name or "").translate(_FILENAME_CHAR_MAP)
    text = re.sub(r"[\x00-\x1f]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.rstrip(". ")
    if len(text) > 180:
        text = text[:180].rstrip(". ")
    if text and _is_win_reserved(text):
        text = "_" + text
    return text or "_"


def _duration_s(value):
    if value is None:
        return 0
    m = re.match(r"(\d+):(\d{1,2})(?::(\d{1,2}))?$", str(value))
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2))
        seconds = int(m.group(3) or 0)
        if m.group(3) is None:
            return hours * 60 + minutes
        return hours * 3600 + minutes * 60 + seconds
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _int_or_0(value):
    try:
        return int(float(str(value or "").strip().replace(",", ".")))
    except (TypeError, ValueError):
        return 0


# ---------- wyszukiwanie narzędzi ----------
def _mac_arch():
    if sys.platform != "darwin":
        return None
    try:
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            return "arm64"
        return "x86_64"
    except Exception:
        return None


def _candidate_dirs():
    dirs = []
    mac_arch = _mac_arch()
    mac_sub = ("macos", mac_arch) if mac_arch else None
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            dirs.append(meipass)
            if mac_sub:
                dirs.append(os.path.join(meipass, "bin", *mac_sub))
            dirs.append(os.path.join(meipass, "bin"))
        dirs.append(os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dirs.append(base)
        if mac_sub:
            dirs.append(os.path.join(base, "bin", *mac_sub))
        dirs.append(os.path.join(base, "bin"))
        dirs.append(os.path.join(base, "do_analizy"))
    return dirs


def find_tool(name, override=None):
    if override and os.path.isfile(override):
        return override
    for d in _candidate_dirs():
        path = os.path.join(d, name)
        if os.path.isfile(path):
            return path
    return shutil.which(name)


def resolve_tools(yt_dlp_path=None, ffmpeg_path=None, deno_path=None):
    yt_dlp = find_tool("yt-dlp.exe", yt_dlp_path) or find_tool("yt-dlp", yt_dlp_path)
    ffmpeg = find_tool("ffmpeg.exe", ffmpeg_path) or find_tool("ffmpeg", ffmpeg_path)
    deno = find_tool("deno.exe", deno_path) or find_tool("deno", deno_path)
    missing = []
    if not yt_dlp:
        missing.append("yt-dlp")
    if not ffmpeg:
        missing.append("ffmpeg")
    if not deno:
        missing.append("deno")
    return {"yt_dlp": yt_dlp, "ffmpeg": ffmpeg, "deno": deno, "missing": missing}


# ---------- parsowanie wejścia ----------
def parse_m3u(path):
    from core.playlist import _decode_m3u

    tracks = []
    name = os.path.splitext(os.path.basename(path))[0]
    current_title = None
    with open(path, "rb") as f:
        raw = f.read()
    text = _decode_m3u(raw)
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTPLAYLIST:"):
            name = line[len("#EXTPLAYLIST:") :].strip() or name
        elif line.startswith("#EXTINF:"):
            meta, _, label = line[len("#EXTINF:") :].partition(",")
            current_title = label.strip()
            tracks.append(
                {
                    "title": label.strip(),
                    "artists": "",
                    "album": "",
                    "playlist": name,
                    "isrc": "",
                    "sp_id": "",
                    "duration_ms": _duration_s(meta) * 1000,
                    "year": "",
                    "cover_url": "",
                    "track_no": 0,
                    "disc_no": 0,
                }
            )
        elif line.startswith("#"):
            continue
        elif tracks and current_title is not None:
            stem = os.path.splitext(os.path.basename(line))[0]
            artist, _, title = stem.partition(" - ")
            t = tracks[-1]
            if artist and title:
                t["artists"] = artist
                t["title"] = title
            else:
                t["artists"] = ""
                t["title"] = stem
        else:
            stem = os.path.splitext(os.path.basename(line))[0]
            artist, _, title = stem.partition(" - ")
            tracks.append(
                {
                    "title": title if title else stem,
                    "artists": artist if title else "",
                    "album": "",
                    "playlist": name,
                    "isrc": "",
                    "sp_id": "",
                    "duration_ms": 0,
                    "year": "",
                    "cover_url": "",
                    "track_no": 0,
                    "disc_no": 0,
                }
            )
    return name, [t for t in tracks if t["title"]]


def _csv_value(row, *keys):
    low = {k.strip().lower(): v for k, v in row.items()}
    for key in keys:
        for col, v in low.items():
            if key in col:
                return v.strip() if isinstance(v, str) else v
    return ""


_CSV_BAD_HEADER = (
    "Track URI,Track Name,Album Name,Artist Name(s),Release Date,Duration (ms),"
    "Popularity,Explicit,Added By,Added At,Genres,Record Label,Danceability,Energy,Key,"
    "Loudness,Mode,Speechiness,Acousticness,Instrumentalness,Liveness,Valence,Tempo,Time Signature"
)
_CSV_GOOD_HEADER = (
    "Track URI,Track Name,Playlist name,Artist name,Release Date,Duration (ms),"
    "Popularity,Explicit,Added By,Added At,Genres,Record Label,Danceability,Energy,Key,"
    "Loudness,Mode,Speechiness,Acousticness,Instrumentalness,Liveness,Valence,Tempo,Time Signature"
)


def _read_csv_text(path):
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "cp1250", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", errors="replace")


def _fix_csv_text(text):
    if _CSV_BAD_HEADER in text:
        return text.replace(_CSV_BAD_HEADER, _CSV_GOOD_HEADER)
    return text


def parse_csv(path):
    import csv as _csv
    from io import StringIO

    fallback_name = os.path.splitext(os.path.basename(path))[0]
    text = _fix_csv_text(_read_csv_text(path))
    tracks = []
    playlist_vals = set()
    reader = _csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        return fallback_name, tracks
    for row in reader:
        title = _csv_value(row, "track name", "title", "track")
        artists = _csv_value(row, "artist name", "artist", "artists")
        if not title:
            continue
        playlist = _csv_value(row, "playlist name")
        if playlist:
            playlist_vals.add(playlist)
        album = _csv_value(row, "album name", "album")
        dur_raw = _csv_value(row, "duration ms", "duration (ms)", "duration")
        duration_ms = 0
        try:
            duration_ms = int(float(dur_raw)) if dur_raw else 0
        except (TypeError, ValueError):
            duration_ms = _duration_s(dur_raw) * 1000
        track_no = _int_or_0(_csv_value(row, "track number", "track #", "track no", "disc track"))
        disc_no = _int_or_0(_csv_value(row, "disc number", "disc #", "disc no", "disc"))
        tracks.append(
            {
                "title": title,
                "artists": artists,
                "album": album,
                "playlist": playlist,
                "isrc": _csv_value(row, "isrc"),
                "sp_id": _csv_value(row, "track uri", "spotify - id", "spotify id"),
                "duration_ms": duration_ms,
                "year": _csv_value(row, "release date", "year"),
                "cover_url": "",
                "track_no": track_no,
                "disc_no": disc_no,
            }
        )
    name = fallback_name
    if len(playlist_vals) == 1:
        name = playlist_vals.pop()
    return name, tracks


def load_playlist_file(path):
    low = path.lower()
    if low.endswith((".m3u", ".m3u8")):
        return parse_m3u(path)
    if low.endswith(".csv"):
        return parse_csv(path)
    raise ValueError("Wybierz plik .m3u, .m3u8 lub .csv")


# ---------- wyszukiwanie w YouTube Music ----------
def _norm_text(s):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", s or "")).strip().lower()


def _overlap_ratio(a, b):
    ta = set(re.findall(r"\w+", _norm_text(a)))
    tb = set(re.findall(r"\w+", _norm_text(b)))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta)


def _score_result(track, res):
    if not isinstance(res, dict) or not res.get("videoId"):
        return -1.0
    title = res.get("title") or ""
    authors = res.get("artists") or []
    artist = ", ".join(a.get("name", "") for a in authors if isinstance(a, dict))
    dur = _duration_s(res.get("duration"))
    score = _overlap_ratio(track["title"], title) * 0.6
    score += _overlap_ratio(track["artists"], artist) * 0.4
    if track["duration_ms"] and dur:
        diff = abs(track["duration_ms"] / 1000 - dur) / max(1, track["duration_ms"] / 1000)
        score += max(0.0, 1.0 - diff) * 0.2
    return score


def search_candidates(ytmusic, track, n=3):
    """Zwraca najlepsze n kandydatów (videoId) dla utworu, posortowanych wg dopasowania."""
    query = f"{track['artists']} {track['title']}".strip()
    try:
        results = ytmusic.search(query, filter="songs", limit=10)
    except Exception:
        return []
    scored = [
        (res, _score_result(track, res))
        for res in (results or [])
        if isinstance(res, dict) and res.get("videoId")
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [res for res, score in scored[:n] if score >= 0.25]


def search_best(ytmusic, track):
    cands = search_candidates(ytmusic, track, n=1)
    return cands[0] if cands else None


# ---------- pobieranie ----------
class _ProcResult:
    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _kill_proc(proc):
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception:
        pass
    finally:
        try:
            proc.kill()
        except Exception:
            pass


def _cancelled(stop_event):
    return stop_event is not None and stop_event.is_set()


def _run(cmd, env=None, timeout=None, stop_event=None):
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
    popen_kwargs = {}
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        creationflags=creationflags,
        **popen_kwargs,
    )

    out_buf = []
    err_buf = []

    def _drain(stream, buf):
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                buf.append(chunk)
        except Exception:
            pass

    t_out = threading.Thread(target=_drain, args=(proc.stdout, out_buf), daemon=True)
    t_err = threading.Thread(target=_drain, args=(proc.stderr, err_buf), daemon=True)
    t_out.start()
    t_err.start()

    deadline = None if timeout is None else time.time() + timeout
    while True:
        if _cancelled(stop_event):
            _kill_proc(proc)
            break
        if proc.poll() is not None:
            break
        if deadline is not None and time.time() > deadline:
            _kill_proc(proc)
            break
        time.sleep(0.1)
    t_out.join(timeout=2)
    t_err.join(timeout=2)
    if proc.returncode is None:
        try:
            proc.poll()
        except Exception:
            pass
    return _ProcResult(proc.returncode, b"".join(out_buf), b"".join(err_buf))


def _yt_thumbnail_bytes(video_id, timeout=12):
    import urllib.request

    for size in ("maxresdefault", "sddefault", "hqdefault", "mqdefault", "default"):
        url = f"https://i.ytimg.com/vi/{video_id}/{size}.jpg"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                data = r.read()
            if len(data) > 1024:
                return data
        except Exception:
            continue
    return None


def _square_cover_bytes(data, size=600):
    try:
        from PySide6.QtCore import QBuffer, QByteArray, QIODevice
        from PySide6.QtGui import QImage

        img = QImage()
        if not img.loadFromData(QByteArray(data)):
            return None
        side = min(img.width(), img.height())
        x = (img.width() - side) // 2
        y = (img.height() - side) // 2
        img = img.copy(x, y, side, side)
        img = img.scaled(size, size)
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "JPEG", 90)
        return bytes(buf.data().data())
    except Exception:
        return None


_ARTIST_SPLIT_RE = re.compile(r",\s+|feat\.?\s+|ft\.?\s+|featuring\s+", re.IGNORECASE)


def single_artist(name):
    """Pierwszy artysta dla tagu TPE1 (iTunes nie rozbija albumu przy jednym).

    Pełna lista artystów zostaje w `track['artists']` (do wyszukiwania i nazwy
    pliku). Cięcie konserwatywne (opcja 1): po przecinku albo feat/ft/featuring;
    nazwy zespołów z ' & ' (np. „Earth, Wind & Fire", „Simon & Garfunkel")
    zostają nienaruszone.
    """
    text = str(name or "").strip()
    if not text:
        return ""
    m = _ARTIST_SPLIT_RE.search(text)
    if not m:
        return text
    if m.group(0).startswith(",") and " & " in text:
        return text
    return text[:m.start()].strip()


def _build_id3_tags(track, cover):
    tags = ID3()
    title = track.get("title") or ""
    artists = single_artist(track.get("artists") or "") or track.get("artists") or ""
    album = track.get("album") or ""
    year = track.get("year") or ""
    genre = track.get("genre") or ""
    track_no = int(track.get("track_no") or 0)
    disc_no = int(track.get("disc_no") or 0)
    total_tracks = int(track.get("total_tracks") or 0)
    if title:
        tags.add(TIT2(encoding=3, text=title))
    if artists:
        tags.add(TPE1(encoding=3, text=artists))
    if album:
        tags.add(TALB(encoding=3, text=album))
    if year:
        tags.add(TDRC(encoding=3, text=str(year)[:4]))
    if genre:
        tags.add(TCON(encoding=3, text=str(genre)))
    if track_no:
        trck = str(track_no)
        if total_tracks:
            trck += "/%d" % total_tracks
        tags.add(TRCK(encoding=3, text=trck))
        if disc_no:
            tags.add(TPOS(encoding=3, text=str(disc_no)))
    if cover:
        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=cover,
            )
        )
    return tags


def _tag_mp3(path, track, cover):
    try:
        audio = MP3(path)
        audio.tags = _build_id3_tags(track, cover)
        audio.save()
    except Exception:
        pass


def _find_downloaded(tmp_dir, base):
    return [
        p
        for p in tmp_dir.iterdir()
        if p.is_file()
        and p.name.startswith(base + ".")
        and p.suffix != ".part"
    ]


def _duration_ms_of_file(path):
    try:
        m = MutagenFile(path)
        if m is not None and m.info is not None and getattr(m.info, "length", 0):
            return int(m.info.length * 1000)
    except Exception:
        pass
    return 0


DEFAULT_DOWNLOAD_OPTIONS = {"mp3_bitrate": "320k", "cover_size": 600}
LEGACY_DOWNLOAD_OPTIONS = {"mp3_bitrate": "192k", "cover_size": 300}


def normalize_download_options(options=None):
    """Normalizuje opcje pobierania do bezpiecznego dictu z domyślnymi."""
    opts = dict(DEFAULT_DOWNLOAD_OPTIONS)
    if isinstance(options, dict):
        bit = options.get("mp3_bitrate")
        if isinstance(bit, str) and re.match(r"^\d{2,4}k$", bit.strip()):
            opts["mp3_bitrate"] = bit.strip()
        size = options.get("cover_size")
        if isinstance(size, int) and size > 0:
            opts["cover_size"] = size
    return opts


def _ffmpeg_cmd(ffmpeg, raw, final_path, bitrate="320k"):
    return [
        ffmpeg,
        "-y",
        "-i",
        str(raw),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(final_path),
    ]


def _track_base(track):
    base = f"{sanitize_name(track['artists'])} - {sanitize_name(track['title'])}"
    tn = int(track.get("track_no") or 0)
    if tn > 0:
        base = f"{tn:02d} - {base}"
    return base


def augment_album_tracks(tracks, genre=""):
    """Nadaje utworom numerację albumową + gatunek. Zachowuje istniejące
    track_no/disc_no (np. z metadanych albumu Spotify)."""
    total = len(tracks)
    out = []
    for i, t in enumerate(tracks):
        t = dict(t)
        if not t.get("track_no"):
            t["track_no"] = i + 1
        t["total_tracks"] = total
        if not t.get("disc_no"):
            t["disc_no"] = 1
        if genre:
            t["genre"] = genre
        out.append(t)
    return out


def ensure_album(tracks, fallback):
    """Uzupełnia TYLKO utwory bez albumu (z CSV). Realne albumy zostają."""
    out = []
    for t in tracks:
        t = dict(t)
        if not t.get("album") and fallback:
            t["album"] = fallback
        out.append(t)
    return out


def download_track(ytmusic, track, dest_dir, tools, options=None, stop_event=None, track_timeout=300, cover_bytes=None):
    track = dict(track)
    dest_dir = Path(dest_dir)
    options = normalize_download_options(options)
    mp3_bitrate = options["mp3_bitrate"]
    cover_size = options["cover_size"]
    track_timeout = max(1, int(track_timeout))
    deadline = time.time() + track_timeout

    yt_dlp = tools.get("yt_dlp")
    ffmpeg = tools.get("ffmpeg")
    deno = tools.get("deno")
    if not yt_dlp or not ffmpeg or not deno:
        return {"ok": False, "error": "Brak narzędzi: " + ", ".join(tools["missing"])}

    dest_dir.mkdir(parents=True, exist_ok=True)
    base = _track_base(track)
    final_path = dest_dir / f"{base}.mp3"
    if final_path.exists() and _duration_ms_of_file(final_path) > 0:
        return {"ok": True, "file": str(final_path), "video_id": ""}

    env = dict(os.environ)
    env["PATH"] = os.path.dirname(deno) + os.pathsep + env.get("PATH", "")

    def _remaining():
        return max(15, int(deadline - time.time()))

    if _cancelled(stop_event):
        return {"ok": False, "error": "Przerwano"}

    candidates = search_candidates(ytmusic, track, n=3)
    if not candidates:
        return {"ok": False, "error": "Nie znaleziono dopasowania"}

    last_err = "yt-dlp nie pobrał pliku"
    for candidate in candidates:
        if _cancelled(stop_event):
            return {"ok": False, "error": "Przerwano"}
        if time.time() >= deadline:
            return {"ok": False, "error": "Przekroczono czas pobierania utworu"}
        video_id = candidate.get("videoId")
        if not video_id:
            continue
        result = _download_one(
            ytmusic, track, dest_dir, tools, env, video_id, options,
            stop_event, _remaining, base, final_path, deadline, cover_bytes,
        )
        if result.get("ok"):
            return result
        last_err = result.get("error", last_err)
    return {"ok": False, "error": last_err}


def _download_one(ytmusic, track, dest_dir, tools, env, video_id, options,
                  stop_event, remaining, base, final_path, deadline, cover_bytes=None):
    mp3_bitrate = options["mp3_bitrate"]
    cover_size = options["cover_size"]
    url = f"https://music.youtube.com/watch?v={video_id}"
    tmp_dir = dest_dir / ".tmp" / video_id
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp = tmp_dir / (base.replace("%", "%%") + ".%(ext)s")

    yt_dlp = tools.get("yt_dlp")
    ffmpeg = tools.get("ffmpeg")

    cmd = [
        yt_dlp,
        "-f",
        "bestaudio",
        "--no-playlist",
        "--force-overwrites",
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "--socket-timeout",
        "30",
        "--js-runtimes",
        "deno",
        "-o",
        str(tmp),
        url,
    ]
    r = _run(cmd, env=env, timeout=remaining(), stop_event=stop_event)
    if r.returncode != 0 and not _cancelled(stop_event) and time.time() < deadline:
        time.sleep(2)
        r = _run(cmd, env=env, timeout=remaining(), stop_event=stop_event)
    used_video_id = video_id
    if r.returncode != 0 and not _cancelled(stop_event) and time.time() < deadline:
        query = f"{track['artists']} {track['title']}".strip()
        fallback = [yt_dlp, "-f", "bestaudio", "--no-playlist", "--force-overwrites",
                    "--js-runtimes", "deno", "--no-progress", "--print", "%(id)s",
                    "-o", str(tmp), f"ytsearch1:{query}"]
        r = _run(fallback, env=env, timeout=remaining(), stop_event=stop_event)
        if r.returncode == 0:
            m = re.search(r"([A-Za-z0-9_-]{11})", r.stdout.decode("utf-8", "replace"))
            if m:
                used_video_id = m.group(1)
    if r.returncode != 0:
        if _cancelled(stop_event):
            return {"ok": False, "error": "Przerwano"}
        return {"ok": False, "error": "yt-dlp: " + r.stderr.decode("utf-8", "replace")[-300:].strip()}

    downloaded = _find_downloaded(tmp_dir, base)
    if not downloaded:
        return {"ok": False, "error": "Brak pobranego pliku"}
    raw = downloaded[0]

    if time.time() >= deadline:
        return {"ok": False, "error": "Przekroczono czas pobierania utworu"}
    r = _run(
        _ffmpeg_cmd(ffmpeg, raw, final_path, mp3_bitrate),
        timeout=remaining(),
        stop_event=stop_event,
    )
    if r.returncode != 0:
        if _cancelled(stop_event):
            return {"ok": False, "error": "Przerwano"}
        return {"ok": False, "error": "ffmpeg: " + r.stderr.decode("utf-8", "replace")[-300:].strip()}
    if _cancelled(stop_event):
        return {"ok": False, "error": "Przerwano"}

    if cover_bytes:
        cover = _square_cover_bytes(cover_bytes, size=cover_size)
    else:
        cover = _yt_thumbnail_bytes(used_video_id)
        cover = _square_cover_bytes(cover, size=cover_size) if cover else None
    _tag_mp3(final_path, track, cover)

    try:
        shutil.rmtree(tmp_dir)
    except OSError:
        pass

    dur = _duration_ms_of_file(final_path)
    if dur:
        track["duration_ms"] = dur
    return {"ok": True, "file": str(final_path), "video_id": used_video_id, "track": track}


# ---------- zapis m3u ----------
def write_m3u(out_dir, playlist_name, tracks_done, ext="mp3", suffix=".m3u", encoding="utf-8"):
    playlist_dir = Path(out_dir) / sanitize_name(playlist_name)
    playlist_dir.mkdir(parents=True, exist_ok=True)
    fp = playlist_dir / f"{sanitize_name(playlist_name)}{suffix}"
    with open(fp, "w", encoding=encoding, errors="ignore") as f:
        f.write("#EXTM3U\n")
        f.write(f"#EXTPLAYLIST:{playlist_name}\n")
        for t in tracks_done:
            title = t.get("title") or ""
            artists = t.get("artists") or ""
            album = t.get("album") or ""
            rel = Path(f"{sanitize_name(artists)} - {sanitize_name(title)}.{ext}")
            dur = int(round((t.get("duration_ms") or 0) / 1000))
            label = f"{artists} - {title}".replace(",", "，")
            f.write(f"#EXTINF:{dur},{label}\n")
            if t.get("isrc"):
                f.write(f"#EXTISRC:{t['isrc']}\n")
            f.write(f"#EXTALBUM:{album}\n")
            f.write(str(rel.as_posix()) + "\n")
    return str(fp)


def write_m3u_copy(playlists_dir, playlist_name, files):
    os.makedirs(playlists_dir, exist_ok=True)
    base = sanitize_name(playlist_name)
    fp = os.path.join(playlists_dir, base + ".m3u")
    suffix = 2
    while os.path.exists(fp):
        fp = os.path.join(playlists_dir, f"{base} ({suffix}).m3u")
        suffix += 1
    with open(fp, "w", encoding="utf-8", errors="ignore") as f:
        f.write("#EXTM3U\n")
        f.write(f"#EXTPLAYLIST:{playlist_name}\n")
        for path in files:
            f.write(path + "\n")
    return fp
