import os
import threading

from PySide6.QtCore import QThread, Signal

from core import storage
from core.downloader import (
    download_track,
    load_playlist_file,
    resolve_tools,
    sanitize_name,
    write_m3u,
    write_m3u_copy,
)
from ytmusicapi import YTMusic


class DownloadWorker(QThread):
    trackStarted = Signal(int, int, str)
    trackFinished = Signal(int, bool, str, str)
    progressChanged = Signal(int, int)
    finishedAll = Signal(dict)

    def __init__(self, playlist_file, dest_dir, parent=None):
        super().__init__(parent)
        self.playlist_file = playlist_file
        self.dest_dir = dest_dir
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
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

        try:
            ytmusic = YTMusic()
        except Exception as e:
            self.finishedAll.emit({"error": f"Nie udało się połączyć z YouTube Music: {e}"})
            return

        out_root = os.path.join(self.dest_dir, sanitize_name(playlist_name))
        ok_tracks = []
        errors = []
        total = len(tracks)
        for i, track in enumerate(tracks):
            if self._stop_event.is_set():
                break
            label = f"{track['artists']} - {track['title']}".strip(" -")
            self.trackStarted.emit(i, total, label)
            try:
                result = download_track(ytmusic, track, out_root, tools, stop_event=self._stop_event)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            self.progressChanged.emit(i + 1, total)
            if result.get("ok"):
                done_track = result.get("track") or track
                done_track["file"] = result["file"]
                ok_tracks.append(done_track)
                self.trackFinished.emit(i, True, label, "")
            else:
                errors.append(label)
                self.trackFinished.emit(i, False, label, result.get("error", ""))

        m3u_path = None
        library_m3u = None
        if ok_tracks:
            try:
                m3u_path = write_m3u(
                    self.dest_dir, playlist_name, ok_tracks, ext="mp3", suffix=".m3u"
                )
                library_m3u = write_m3u_copy(
                    storage.playlists_dir(), playlist_name, [t["file"] for t in ok_tracks]
                )
            except Exception as e:
                errors.append(f"Błąd zapisu playlisty: {e}")

        self.finishedAll.emit(
            {
                "playlist_name": playlist_name,
                "ok": len(ok_tracks),
                "total": total,
                "errors": errors,
                "m3u_path": m3u_path,
                "library_m3u": library_m3u,
            }
        )
