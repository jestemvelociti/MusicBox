from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

from ui.download_worker import DownloadWorker


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
            "Wczytaj plik CSV (eksport playlisty ze Spotify) i pobierz utwory do "
            "wybranego folderu. Na końcu powstanie plik .m3u i playlista trafi "
            "do Twojej biblioteki."
        )
        sub.setObjectName("addSubtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)

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

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Wybierz plik CSV",
            "",
            "CSV (*.csv);;Wszystkie pliki (*)",
        )
        if path:
            self.file_edit.setText(path)
            self._load_tracks()

    def load_csv(self, path):
        if self._worker is not None and self._worker.isRunning():
            self._set_status("Pobieranie w trakcie — zaczekaj, aż się zakończy.")
            return False
        self.file_edit.setText(path)
        self._load_tracks()
        return bool(self._tracks)

    def _browse_out(self):
        path = QFileDialog.getExistingDirectory(self, "Wybierz folder docelowy")
        if path:
            self.out_edit.setText(path)

    def _load_tracks(self):
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
        self._tracks = tracks
        self._playlist_name = playlist_name
        self.track_list.clear()
        for t in tracks:
            label = f"{t['artists']} - {t['title']}".strip(" -")
            item = QListWidgetItem(label)
            item.setToolTip(label)
            self.track_list.addItem(item)
        self.download_btn.setEnabled(bool(tracks))
        self._set_status(
            f"Wczytano {len(tracks)} utworów z playlisty „{playlist_name}”."
        )

    def _start(self):
        src = self.file_edit.text()
        out = self.out_edit.text()
        if not src:
            self._set_status("Wybierz plik CSV.")
            return
        if not out:
            self._set_status("Wybierz folder docelowy.")
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

        self._worker = DownloadWorker(src, out, self)
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
        if result.get("library_m3u"):
            msg += " — playlista dodana do biblioteki."
            self.playlistSaved.emit(result["library_m3u"])
        self._set_status(msg)

    def _set_controls_enabled(self, enabled):
        self.browse_file_btn.setEnabled(enabled)
        self.browse_out_btn.setEnabled(enabled)
        self.load_btn.setEnabled(enabled)
        self.download_btn.setEnabled(enabled and bool(self._tracks))

    def _set_status(self, text):
        self.status_label.setText(text)
