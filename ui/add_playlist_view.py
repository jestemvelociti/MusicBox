from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui.track_list import TrackList


class AddPlaylistView(QFrame):
    confirmRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("addView")

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self._build_waiting())
        self.stack.addWidget(self._build_preview())
        self.stack.setCurrentIndex(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

    # --- strona 1: czekanie na .m3u ---
    def _build_waiting(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.addStretch(1)

        hint = QLabel("🎵\nPrzeciągnij pliki .m3u, muzykę lub foldery tutaj")
        hint.setObjectName("dropHintLabel")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            "QLabel#dropHintLabel { background-color: #111a30; "
            "border: 2px dashed #3d7bff; border-radius: 16px; "
            "padding: 48px; color: #93a4c7; font-size: 17px; }"
        )
        lay.addWidget(hint)
        lay.addStretch(1)
        return page

    # --- strona 2: podgląd playlisty ---
    def _build_preview(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(20)

        self.cover = QLabel()
        self.cover.setObjectName("previewCover")
        self.cover.setFixedSize(120, 120)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setStyleSheet(
            "QLabel#previewCover { background-color: #22304f; "
            "border-radius: 12px; color: #5c90ff; font-size: 44px; }"
        )

        info = QVBoxLayout()
        info.setSpacing(6)
        self.title_label = QLabel("")
        self.title_label.setObjectName("addTitle")
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("addSubtitle")
        info.addStretch(1)
        info.addWidget(self.title_label)
        info.addWidget(self.subtitle_label)
        info.addStretch(1)

        head.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignTop)
        head.addLayout(info, 1)
        lay.addLayout(head)

        self.track_list = TrackList(self)
        self.track_list.setObjectName("addTrackTable")
        lay.addWidget(self.track_list, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton("Anuluj")
        self.cancel_btn.setObjectName("cancelBtn")
        self.confirm_btn = QPushButton("＋ Dodaj")
        self.confirm_btn.setObjectName("confirmAddBtn")
        self.cancel_btn.clicked.connect(self.cancelRequested)
        self.confirm_btn.clicked.connect(self.confirmRequested)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.confirm_btn)
        lay.addLayout(buttons)

        return page

    # --- API ---
    def set_waiting_state(self):
        self.stack.setCurrentIndex(0)

    def show_preview(self, playlist, pixmap=None):
        self.title_label.setText(playlist.name)
        self.subtitle_label.setText(f"{len(playlist.tracks)} utworów")
        if pixmap is not None:
            scaled = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.cover.setPixmap(scaled)
            self.cover.setText("")
        else:
            self.cover.setText("♪")
        self.track_list.set_playlist(playlist)
        self.track_list.clearSelection()
        self.stack.setCurrentIndex(1)
