import os
import shutil
import socket
import subprocess
import threading

from PySide6.QtCore import QThread, Signal

from core import storage
from core.downloader import (
    augment_album_tracks,
    download_track,
    ensure_album,
    load_playlist_file,
    resolve_tools,
    sanitize_name,
    write_m3u,
    write_m3u_copy,
)
from ytmusicapi import YTMusic


def _extract_cover_bytes(path):
    try:
        from mutagen.id3 import ID3

        tags = ID3(path)
        pics = tags.getall("APIC")
        if pics and pics[0].data:
            return bytes(pics[0].data)
    except Exception:
        pass
    return None


def _tool_version(tool):
    if not tool:
        return "brak"
    try:
        out = subprocess.run(
            [tool, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.decode("utf-8", "replace").strip().splitlines()
        return (out[0] if out else "?")[:120]
    except Exception:
        return "?"


class SpotifyLoadWorker(QThread):
    loaded = Signal(str, list)
    failed = Signal(str)

    def __init__(self, client_id, client_secret, url, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.client_secret = client_secret
        self.url = url

    def run(self):
        socket.setdefaulttimeout(30)
        try:
            from core.spotify import resolve_spotify_link

            name, tracks = resolve_spotify_link(
                self.client_id, self.client_secret, self.url
            )
            self.loaded.emit(name, tracks)
        except Exception as e:
            self.failed.emit(str(e))


class DownloadWorker(QThread):
    trackStarted = Signal(int, int, str)
    trackFinished = Signal(int, bool, str, str)
    progressChanged = Signal(int, int)
    finishedAll = Signal(dict)

    def __init__(self, playlist_file=None, dest_dir=None, options=None, parent=None,
                 tracks=None, playlist_name=None):
        super().__init__(parent)
        self.playlist_file = playlist_file
        self.dest_dir = dest_dir
        self.options = options or {}
        self._tracks = tracks
        self._playlist_name_override = playlist_name
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        socket.setdefaulttimeout(30)
        if self._tracks is not None:
            tracks = list(self._tracks)
            playlist_name = self._playlist_name_override or "Playlista"
        else:
            try:
                playlist_name, tracks = load_playlist_file(self.playlist_file)
            except Exception as e:
                self.finishedAll.emit({"error": f"Nie udało się wczytać pliku: {e}"})
                return

        tools = resolve_tools()
        if tools["missing"]:
            self.finishedAll.emit(
                {"error": "Brak narzędzi: " + ", ".join(tools["missing"])}
            )
            return

        self._log(
            "start: yt-dlp=%s | ffmpeg=%s | deno=%s"
            % (_tool_version(tools.get("yt_dlp")), _tool_version(tools.get("ffmpeg")),
               _tool_version(tools.get("deno")))
        )

        try:
            ytmusic = YTMusic()
        except Exception as e:
            self.finishedAll.emit({"error": f"Nie udało się połączyć z YouTube Music: {e}"})
            return

        options = self.options or {}
        mode = options.get("mode", "playlist")
        genre = options.get("genre", "")
        album_fallback = options.get("album", "") or ""

        if mode == "album":
            album_name = playlist_name
            for t in tracks:
                if t.get("album"):
                    album_name = t["album"]
                    break
            if not any(t.get("album") for t in tracks) and album_fallback:
                album_name = album_fallback
            tracks = augment_album_tracks(tracks, genre)
            tracks = ensure_album(tracks, album_name)
            out_root = os.path.join(self.dest_dir, sanitize_name(album_name))
            self._log("album: '%s' | utworow=%d" % (album_name, len(tracks)))
        else:
            if genre:
                for t in tracks:
                    t["genre"] = genre
            tracks = ensure_album(tracks, album_fallback)
            out_root = os.path.join(self.dest_dir, sanitize_name(playlist_name))

        ok_tracks = []
        errors = []
        total = len(tracks)
        album_cover = None
        for i, track in enumerate(tracks):
            if self._stop_event.is_set():
                break
            label = f"{track['artists']} - {track['title']}".strip(" -")
            self.trackStarted.emit(i, total, label)
            try:
                result = download_track(
                    ytmusic, track, out_root, tools, options=options,
                    stop_event=self._stop_event, track_timeout=300,
                    cover_bytes=album_cover,
                )
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.progressChanged.emit(i + 1, total)
            self._log("track[%d/%d] ok=%s %s" % (i + 1, total, result.get("ok"), label))
            if result.get("ok"):
                done_track = result.get("track") or track
                done_track["file"] = result["file"]
                ok_tracks.append(done_track)
                if mode == "album" and album_cover is None:
                    album_cover = _extract_cover_bytes(result["file"])
                self.trackFinished.emit(i, True, label, "")
            else:
                errors.append(label)
                self.trackFinished.emit(i, False, label, result.get("error", ""))

        m3u_path = None
        library_m3u = None
        if mode == "album":
            self._log("album: pobrano=%d/ %d (bez .m3u)" % (len(ok_tracks), total))
        elif ok_tracks:
            try:
                m3u_path = write_m3u(
                    self.dest_dir, playlist_name, ok_tracks, ext="mp3", suffix=".m3u"
                )
                library_m3u = write_m3u_copy(
                    storage.playlists_dir(), playlist_name, [t["file"] for t in ok_tracks]
                )
            except Exception as e:
                errors.append(f"Błąd zapisu playlisty: {e}")

        try:
            shutil.rmtree(os.path.join(out_root, ".tmp"), ignore_errors=True)
        except Exception:
            pass

        self.finishedAll.emit(
            {
                "playlist_name": album_name if mode == "album" else playlist_name,
                "album": mode == "album",
                "ok": len(ok_tracks),
                "total": total,
                "errors": errors,
                "m3u_path": m3u_path,
                "library_m3u": library_m3u,
            }
        )

    def _log(self, msg):
        try:
            target = os.path.join(storage.get_data_dir(), "musicbox_dl.log")
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass
