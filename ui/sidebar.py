from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
)

from core.cover import first_cover


class Sidebar(QFrame):
    playlistClicked = Signal(int)
    removeRequested = Signal(int)
    homeRequested = Signal()
    libraryRequested = Signal()
    statsRequested = Signal()
    addRequested = Signal()
    importRequested = Signal()
    downloadRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(230)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(10)

        self.home_btn = QPushButton("← Strona główna")
        self.home_btn.setObjectName("homeBtn")
        self.home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.home_btn.clicked.connect(self.homeRequested)
        layout.addWidget(self.home_btn)

        header = QLabel("BIBLIOTEKA")
        header.setObjectName("libraryLabel")
        layout.addWidget(header)

        self.library_btn = QPushButton("♪ Biblioteka")
        self.library_btn.setObjectName("homeBtn")
        self.library_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.library_btn.clicked.connect(self.libraryRequested)
        layout.addWidget(self.library_btn)

        self.stats_btn = QPushButton("📊 Statystyki")
        self.stats_btn.setObjectName("homeBtn")
        self.stats_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stats_btn.clicked.connect(self.statsRequested)
        layout.addWidget(self.stats_btn)

        self.list = QListWidget()
        self.list.setObjectName("playlistList")
        self.list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list.setIconSize(QSize(28, 28))
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._on_context_menu)
        self.list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list, 1)

        self.add_btn = QPushButton("＋ Dodaj playlistę")
        self.add_btn.setObjectName("addPlaylistBtn")
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self.addRequested)
        layout.addWidget(self.add_btn)

        self.import_btn = QPushButton("⇧ Importuj .m3u")
        self.import_btn.setObjectName("homeBtn")
        self.import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_btn.clicked.connect(self.importRequested)
        layout.addWidget(self.import_btn)

        self.download_btn = QPushButton("⤓ Pobierz playlistę")
        self.download_btn.setObjectName("downloadPlaylistBtn")
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self.downloadRequested)
        layout.addWidget(self.download_btn)

    def set_playlists(self, playlists, current):
        self.list.blockSignals(True)
        self.list.clear()
        for playlist in playlists:
            item = QListWidgetItem(playlist.name)
            item.setToolTip(playlist.name)
            pixmap = self._playlist_pixmap(playlist)
            if pixmap is not None:
                item.setIcon(QIcon(pixmap))
            self.list.addItem(item)
        if 0 <= current < self.list.count():
            self.list.setCurrentRow(current)
        self.list.blockSignals(False)

    @staticmethod
    def _playlist_pixmap(playlist):
        data = first_cover([t.path for t in playlist.tracks])
        if not data:
            return None
        pm = QPixmap()
        if not pm.loadFromData(data):
            return None
        return pm.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

    def _on_item_clicked(self, item):
        self.playlistClicked.emit(self.list.row(item))

    def _on_context_menu(self, pos):
        item = self.list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        remove = menu.addAction("Usuń playlistę")
        chosen = menu.exec(self.list.mapToGlobal(pos))
        if chosen is remove:
            self.removeRequested.emit(self.list.row(item))

    def set_waiting_state(self, waiting):
        self.add_btn.setEnabled(not waiting)
        if waiting:
            self.add_btn.setText("Czekam na pliki…")
        else:
            self.add_btn.setText("＋ Dodaj playlistę")
