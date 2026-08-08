import os

from PySide6.QtCore import QStandardPaths, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import storage
from ui.download_worker import DownloadWorker, SpotifyLoadWorker

_QUALITY_PRESETS = [
    ("Standard — MP3 320 kbps", {"mp3_bitrate": "320k", "cover_size": 600}),
    ("MP3 192 kbps", {"mp3_bitrate": "192k", "cover_size": 600}),
    ("MP3 128 kbps", {"mp3_bitrate": "128k", "cover_size": 600}),
    ("Legacy iPod — 192k + okładka 300px", {"mp3_bitrate": "192k", "cover_size": 300}),
]


def _default_dir():
    d = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DocumentsLocation
    )
    return d or os.path.expanduser("~")


class DownloadView(QWidget):
    backRequested = Signal()
    playlistSaved = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("downloadView")
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        top = QHBoxLayout()
        self.back_btn = QPushButton("← Strona główna")
        self.back_btn.setObjectName("homeBtn")
        self.back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_btn.clicked.connect(self.backRequested)
        top.addWidget(self.back_btn)
        top.addStretch(1)
        layout.addLayout(top)

        header = QLabel("Pobierz playlistę z YouTube Music")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        layout.addWidget(header)

        sub = QLabel(
            "Wczytaj utwory z pliku CSV (eksport playlisty ze Spotify) albo z linku "
            "Spotify i pobierz je do wybranego folderu. Na końcu powstanie plik "
            ".m3u i playlista trafi do Twojej biblioteki."
        )
        sub.setObjectName("addSubtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        source_row = QHBoxLayout()
        source_label = QLabel("Źródło:")
        source_label.setObjectName("addSubtitle")
        source_row.addWidget(source_label)
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("searchBox")
        self.source_combo.addItem("Plik CSV", "csv")
        self.source_combo.addItem("Link Spotify", "spotify")
        source_row.addWidget(self.source_combo)
        source_row.addStretch(1)
        layout.addLayout(source_row)

        self.file_edit = QLineEdit()
        self.file_edit.setObjectName("searchBox")
        self.file_edit.setPlaceholderText("Plik CSV (eksport playlisty ze Spotify)…")
        self.file_edit.setReadOnly(True)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_edit, 1)
        self.browse_file_btn = QPushButton("Przeglądaj…")
        self.browse_file_btn.setObjectName("homeBtn")
        self.browse_file_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self.browse_file_btn)
        layout.addLayout(file_row)

        self.link_edit = QLineEdit()
        self.link_edit.setObjectName("searchBox")
        self.link_edit.setPlaceholderText("Link Spotify (playlista/album/utwór)…")
        link_row = QHBoxLayout()
        link_row.addWidget(self.link_edit, 1)
        layout.addLayout(link_row)

        self._cid_label = QLabel("Client ID:")
        self._cid_label.setObjectName("addSubtitle")
        self.spotify_cid = QLineEdit()
        self.spotify_cid.setObjectName("searchBox")
        self.spotify_cid.setPlaceholderText("Spotify Client ID…")
        self._sec_label = QLabel("Secret:")
        self._sec_label.setObjectName("addSubtitle")
        self.spotify_secret = QLineEdit()
        self.spotify_secret.setObjectName("searchBox")
        self.spotify_secret.setPlaceholderText("Spotify Client Secret…")
        self.spotify_secret.setEchoMode(QLineEdit.EchoMode.Password)
        creds_row = QHBoxLayout()
        creds_row.addWidget(self._cid_label)
        creds_row.addWidget(self.spotify_cid, 1)
        creds_row.addWidget(self._sec_label)
        creds_row.addWidget(self.spotify_secret, 1)
        layout.addLayout(creds_row)

        self._csv_widgets = [self.file_edit, self.browse_file_btn]
        self._spotify_widgets = [
            self.link_edit, self.spotify_cid, self.spotify_secret,
            self._cid_label, self._sec_label,
        ]
        for w in self._spotify_widgets:
            w.setVisible(False)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        self.spotify_cid.textChanged.connect(self._persist_spotify_creds)
        self.spotify_secret.textChanged.connect(self._persist_spotify_creds)

        self.out_edit = QLineEdit()
        self.out_edit.setObjectName("searchBox")
        self.out_edit.setPlaceholderText("Folder docelowy…")
        self.out_edit.setReadOnly(True)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, 1)
        self.browse_out_btn = QPushButton("Przeglądaj…")
        self.browse_out_btn.setObjectName("homeBtn")
        self.browse_out_btn.clicked.connect(self._browse_out)
        out_row.addWidget(self.browse_out_btn)
        layout.addLayout(out_row)

        quality_row = QHBoxLayout()
        quality_label = QLabel("Jakość pobierania:")
        quality_label.setObjectName("addSubtitle")
        quality_row.addWidget(quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("searchBox")
        self.quality_combo.setMinimumWidth(240)
        for name, opts in _QUALITY_PRESETS:
            self.quality_combo.addItem(name, opts)
        self.quality_combo.setToolTip(
            "Jakość plików MP3 i rozmiar okładki. „Legacy iPod” to tryb dla "
            "starszych odtwarzaczy (CBR 192 kbps + mała okładka 300×300)."
        )
        quality_row.addWidget(self.quality_combo)
        quality_row.addStretch(1)
        layout.addLayout(quality_row)
        self._load_quality_preset()

        mode_genre_row = QHBoxLayout()
        mode_label = QLabel("Pobierz jako:")
        mode_label.setObjectName("addSubtitle")
        mode_genre_row.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("searchBox")
        self.mode_combo.addItem("Playlista (CSV)", "playlist")
        self.mode_combo.addItem("Album (CSV)", "album")
        self.mode_combo.setToolTip(
            "„Playlista” — folder z plikiem .m3u.\n"
            "„Album” — folder albumu z tagami (TALB, TRCK 1/12, TCON), bez .m3u."
        )
        mode_genre_row.addWidget(self.mode_combo)
        genre_label = QLabel("Gatunek:")
        genre_label.setObjectName("addSubtitle")
        mode_genre_row.addWidget(genre_label)
        self.genre_edit = QLineEdit()
        self.genre_edit.setObjectName("searchBox")
        self.genre_edit.setPlaceholderText("np. Hip-Hop (opcjonalnie)…")
        self.genre_edit.setMinimumWidth(160)
        mode_genre_row.addWidget(self.genre_edit, 1)
        album_label = QLabel("Album:")
        album_label.setObjectName("addSubtitle")
        mode_genre_row.addWidget(album_label)
        self.album_edit = QLineEdit()
        self.album_edit.setObjectName("searchBox")
        self.album_edit.setPlaceholderText("Album (z CSV jeśli jest)…")
        self.album_edit.setMinimumWidth(160)
        mode_genre_row.addWidget(self.album_edit)
        layout.addLayout(mode_genre_row)
        self._load_mode_genre()
        self._album_from_csv = False
        self.album_edit.textChanged.connect(self._update_download_enabled)

        self.load_btn = QPushButton("Wczytaj utwory")
        self.load_btn.setObjectName("homeBtn")
        self.load_btn.clicked.connect(self._load_tracks)
        self.download_btn = QPushButton("Pobierz wszystko")
        self.download_btn.setObjectName("confirmAddBtn")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.download_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        self.track_list = QListWidget()
        self.track_list.setObjectName("trackList")
        layout.addWidget(self.track_list, 1)

        self.progress = QProgressBar()
        self.progress.setObjectName("downloadProgress")
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setObjectName("addSubtitle")
        layout.addWidget(self.status_label)

        self._tracks = []
        self._playlist_name = ""
        saved = storage.get_download_settings()
        idx = self.source_combo.findData(saved.get("source"))
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)
        self._source_changed()

    def _browse_file(self):
        start = storage.get_last_dir("download_csv", _default_dir())
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz plik CSV",
            start,
            "CSV (*.csv);;Wszystkie pliki (*)",
        )
        if path:
            self.file_edit.setText(path)
            storage.set_last_dir("download_csv", os.path.dirname(path))
            self._load_tracks()

    def load_csv(self, path):
        if self._worker is not None and self._worker.isRunning():
            self._set_status("Pobieranie w trakcie — zaczekaj, aż się zakończy.")
            return False
        self.file_edit.setText(path)
        self._load_tracks()
        return bool(self._tracks)

    def _browse_out(self):
        start = storage.get_last_dir("download_out", _default_dir())
        path = QFileDialog.getExistingDirectory(self, "Wybierz folder docelowy", start)
        if path:
            self.out_edit.setText(path)
            storage.set_last_dir("download_out", path)

    def _load_quality_preset(self):
        saved = storage.get_download_settings()
        for i in range(self.quality_combo.count()):
            d = self.quality_combo.itemData(i)
            if d and d.get("mp3_bitrate") == saved.get("mp3_bitrate") \
                    and d.get("cover_size") == saved.get("cover_size"):
                self.quality_combo.setCurrentIndex(i)
                break
        self.quality_combo.currentIndexChanged.connect(self._persist_quality)

    def _persist_quality(self, *_):
        cur = storage.get_download_settings()
        opts = self.quality_combo.currentData() or {}
        cur["mp3_bitrate"] = opts.get("mp3_bitrate", cur.get("mp3_bitrate"))
        cur["cover_size"] = opts.get("cover_size", cur.get("cover_size"))
        storage.set_download_settings(cur)

    def _load_mode_genre(self):
        saved = storage.get_download_settings()
        idx = self.mode_combo.findData(saved.get("mode"))
        if idx >= 0:
            self.mode_combo.setCurrentIndex(idx)
        self.genre_edit.setText(saved.get("genre", ""))
        self.mode_combo.currentIndexChanged.connect(self._persist_mode_genre)
        self.genre_edit.textChanged.connect(self._persist_mode_genre)

    def _persist_mode_genre(self, *_):
        cur = storage.get_download_settings()
        cur["mode"] = self.mode_combo.currentData() or "playlist"
        cur["genre"] = self.genre_edit.text().strip()
        storage.set_download_settings(cur)

    def _current_download_options(self):
        opts = storage.get_download_settings()
        q = self.quality_combo.currentData() or {}
        opts["mp3_bitrate"] = q.get("mp3_bitrate", opts.get("mp3_bitrate"))
        opts["cover_size"] = q.get("cover_size", opts.get("cover_size"))
        opts["mode"] = self.mode_combo.currentData() or opts.get("mode", "playlist")
        opts["genre"] = self.genre_edit.text().strip()
        opts["album"] = self.album_edit.text().strip()
        return opts

    def _source_changed(self, *_):
        source = self.source_combo.currentData() or "csv"
        cur = storage.get_download_settings()
        cur["source"] = source
        storage.set_download_settings(cur)
        is_spot = source == "spotify"
        for w in self._csv_widgets:
            w.setVisible(not is_spot)
        for w in self._spotify_widgets:
            w.setVisible(is_spot)
        self.load_btn.setText("Wczytaj link" if is_spot else "Wczytaj utwory")
        creds = storage.get_spotify_credentials()
        self.spotify_cid.setText(creds["client_id"])
        self.spotify_secret.setText(creds["client_secret"])
        self._tracks = []
        self._playlist_name = ""
        self._album_from_csv = False
        self._update_download_enabled()

    def _persist_spotify_creds(self, *_):
        cur = storage.get_spotify_credentials()
        cid = self.spotify_cid.text().strip() or cur["client_id"]
        sec = self.spotify_secret.text().strip() or cur["client_secret"]
        if not cid and not sec:
            return
        storage.set_spotify_credentials(cid, sec)

    def _load_tracks(self):
        if self.source_combo.currentData() == "spotify":
            self._load_spotify()
            return
        path = self.file_edit.text()
        if not path:
            self._set_status("Wybierz plik CSV.")
            return
        from core.downloader import parse_csv

        try:
            playlist_name, tracks = parse_csv(path)
        except Exception as e:
            self._set_status(f"Błąd wczytywania: {e}")
            return
        self._apply_tracks(tracks, playlist_name, "CSV")

    def _load_spotify(self):
        link = self.link_edit.text().strip()
        if not link:
            self._set_status("Wklej link Spotify.")
            return
        cid = self.spotify_cid.text().strip()
        sec = self.spotify_secret.text().strip()
        if not cid or not sec:
            self._set_status("Wpisz Spotify Client ID i Client Secret.")
            return
        if getattr(self, "_spotify_worker", None) and self._spotify_worker.isRunning():
            return
        self._set_controls_enabled(False)
        self._set_status("Wczytywanie linku Spotify…")
        self._spotify_worker = SpotifyLoadWorker(cid, sec, link, self)
        self._spotify_worker.loaded.connect(self._on_spotify_loaded)
        self._spotify_worker.failed.connect(self._on_spotify_failed)
        self._spotify_worker.finished.connect(self._on_spotify_worker_finished)
        self._spotify_worker.start()

    def _on_spotify_worker_finished(self):
        worker = self._spotify_worker
        self._spotify_worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_spotify_loaded(self, name, tracks):
        self._set_controls_enabled(True)
        self._apply_tracks(tracks, name, "Spotify")

    def _on_spotify_failed(self, error):
        self._set_controls_enabled(True)
        self._set_status(f"Nie udało się wczytać linku Spotify: {error}")

    def _apply_tracks(self, tracks, name, source_label):
        self._tracks = tracks
        self._playlist_name = name
        self._album_from_csv = any(t.get("album") for t in tracks)
        self.track_list.clear()
        for t in tracks:
            label = f"{t['artists']} - {t['title']}".strip(" -")
            item = QListWidgetItem(label)
            item.setToolTip(label)
            self.track_list.addItem(item)
        if not self._album_from_csv:
            self.album_edit.setText(name)
            self.album_edit.setPlaceholderText("Album (edytuj — wzięty z nazwy źródła)…")
        else:
            self.album_edit.setPlaceholderText("Album (z CSV jeśli jest)…")
        self._update_download_enabled()
        suffix = "" if self._album_from_csv else "  Album wzięty z nazwy źródła — możesz edytować."
        self._set_status(
            f"Wczytano {len(tracks)} utworów ze źródła {source_label} „{name}”." + suffix
        )

    def _update_download_enabled(self, *_):
        if not self._tracks:
            self.download_btn.setEnabled(False)
            return
        if not self._album_from_csv and not self.album_edit.text().strip():
            self.download_btn.setEnabled(False)
            return
        self.download_btn.setEnabled(True)

    def _start(self):
        src = self.file_edit.text()
        out = self.out_edit.text()
        is_spot = self.source_combo.currentData() == "spotify"
        if not out:
            self._set_status("Wybierz folder docelowy.")
            return
        if not is_spot and not src:
            self._set_status("Wybierz plik CSV.")
            return
        if not self._tracks:
            self._set_status("Najpierw wczytaj utwory (CSV lub link Spotify).")
            return
        if not self._album_from_csv and not self.album_edit.text().strip():
            self._set_status("Wpisz album (nie udało się odczytać ze źródła).")
            return
        if self._worker is not None and self._worker.isRunning():
            return

        self._set_controls_enabled(False)
        self.track_list.clear()
        for t in self._tracks:
            label = f"{t['artists']} - {t['title']}".strip(" -")
            self.track_list.addItem(QListWidgetItem(label))
        self.progress.setRange(0, max(1, len(self._tracks)))
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._set_status("Pobieranie…")

        opts = self._current_download_options()
        if is_spot:
            self._worker = DownloadWorker(
                dest_dir=out, options=opts, parent=self,
                tracks=self._tracks, playlist_name=self._playlist_name,
            )
        else:
            self._worker = DownloadWorker(src, out, opts, self)
        self._worker.trackStarted.connect(self._on_track_started)
        self._worker.trackFinished.connect(self._on_track_finished)
        self._worker.progressChanged.connect(self.progress.setValue)
        self._worker.finishedAll.connect(self._on_finished)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self):
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def _on_track_started(self, index, total, label):
        item = self.track_list.item(index)
        if item:
            item.setText(f"{label}  —  pobieram…")
        self._set_status(f"[{index + 1}/{total}] {label}")

    def _on_track_finished(self, index, ok, label, error):
        item = self.track_list.item(index)
        if item is None:
            return
        if ok:
            item.setText(f"✔  {label}")
        else:
            item.setText(f"✖  {label}")
            item.setToolTip(error or "błąd")

    def _on_finished(self, result):
        self._set_controls_enabled(True)
        self.progress.setVisible(False)
        if result.get("error"):
            self._set_status(result["error"])
            return
        ok = result["ok"]
        total = result["total"]
        errors = result["errors"]
        msg = f"Gotowe: pobrano {ok}/{total}"
        if errors:
            msg += f", błędów: {len(errors)}"
        if result.get("album"):
            msg += " — album gotowy (tagi + numeracja utworów)."
        elif result.get("library_m3u"):
            msg += " — playlista dodana do biblioteki."
            self.playlistSaved.emit(result["library_m3u"])
        self._set_status(msg)

    def _set_controls_enabled(self, enabled):
        self.browse_file_btn.setEnabled(enabled)
        self.browse_out_btn.setEnabled(enabled)
        self.load_btn.setEnabled(enabled)
        if enabled:
            self._update_download_enabled()
        else:
            self.download_btn.setEnabled(False)

    def _set_status(self, text):
        self.status_label.setText(text)
