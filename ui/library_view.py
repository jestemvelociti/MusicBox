import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.playlist import Playlist, Track
from core.tags import display_name
from ui.home_view import pluralize
from ui.track_list import TrackList

_PL = str.maketrans(
    {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ź": "z", "ż": "z",
        "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
        "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
    }
)


def _sort_key(path, title):
    return display_name(path, title).translate(_PL).casefold()


def build_library_playlist(playlists):
    seen = set()
    tracks = []
    for pl in playlists:
        for t in pl.tracks:
            key = os.path.normcase(os.path.abspath(t.path))
            if key in seen:
                continue
            seen.add(key)
            tracks.append(Track(path=t.path, title=t.title))
    tracks.sort(key=lambda t: _sort_key(t.path, t.title))
    playlist = Playlist("Biblioteka")
    playlist.tracks = tracks
    return playlist


class LibraryView(QWidget):
    playRequested = Signal(int)
    revealRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("libraryView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        header = QLabel("Biblioteka")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        layout.addWidget(header)

        self.count_label = QLabel("")
        self.count_label.setObjectName("addSubtitle")
        layout.addWidget(self.count_label)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("Szukaj w bibliotece…")
        self.search_box.setClearButtonEnabled(True)
        layout.addWidget(self.search_box)

        self.track_list = TrackList()
        self.track_list.allow_remove = False
        layout.addWidget(self.track_list, 1)

        self.track_list.playRequested.connect(self.playRequested)
        self.track_list.revealRequested.connect(self.revealRequested)
        self.search_box.textChanged.connect(self.track_list.set_filter)

    def set_library(self, playlist):
        self.track_list.set_playlist(playlist)
        self.track_list.set_filter(self.search_box.text())
        if playlist:
            self.count_label.setText(
                f"Wszystkie utwory z playlist · {pluralize(len(playlist.tracks))}"
            )
        else:
            self.count_label.setText("Brak utworów")
