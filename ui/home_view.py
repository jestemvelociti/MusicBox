from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.cover import first_cover

TILE_W = 176
TILE_H = 220
GAP = 16


def pluralize(count):
    if count == 1:
        return f"{count} utwór"
    if count % 10 in (2, 3, 4) and not 12 <= count % 100 <= 14:
        return f"{count} utwory"
    return f"{count} utworów"


class PlaylistTile(QPushButton):
    removeRequested = Signal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.setObjectName("playlistTile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(TILE_W, TILE_H)
        self._index = index
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.cover = QLabel()
        self.cover.setObjectName("tileCover")
        self.cover.setFixedSize(TILE_W - 24, TILE_W - 24)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cover, 0, Qt.AlignmentFlag.AlignHCenter)

        self.name_label = QLabel("")
        self.name_label.setObjectName("tileName")
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(40)
        layout.addWidget(self.name_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.count_label = QLabel("")
        self.count_label.setObjectName("tileCount")
        layout.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self._placeholder()

    def _placeholder(self):
        self.cover.setText("♪")
        self.cover.setStyleSheet(
            "QLabel#tileCover { background-color: #22304f; border-radius: 12px; "
            "color: #5c90ff; font-size: 44px; }"
        )

    def set_cover(self, pixmap):
        if pixmap is None:
            self._placeholder()
            return
        scaled = pixmap.scaled(
            TILE_W - 24,
            TILE_W - 24,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.cover.setPixmap(scaled)
        self.cover.setText("")
        self.cover.setStyleSheet(
            "QLabel#tileCover { background-color: transparent; border-radius: 12px; }"
        )

    def set_name(self, name):
        self.name_label.setText(name)

    def set_count(self, count):
        self.count_label.setText(pluralize(count))

    def _on_context_menu(self, pos):
        menu = QMenu(self)
        open_action = menu.addAction("Otwórz playlistę")
        menu.addSeparator()
        remove_action = menu.addAction("Usuń playlistę")
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is open_action:
            self.clicked.emit()
        elif chosen is remove_action:
            self.removeRequested.emit(self._index)


class HomeView(QWidget):
    playlistClicked = Signal(int)
    addRequested = Signal()
    downloadRequested = Signal()
    libraryRequested = Signal()
    statsRequested = Signal()
    removeRequested = Signal(int)
    refreshRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homeView")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header = QLabel("Twoje playlisty")
        header.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #ffffff;"
        )
        header_row.addWidget(header)
        header_row.addStretch(1)
        self.refresh_btn = QPushButton("⟳ Odśwież")
        self.refresh_btn.setObjectName("homeBtn")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refreshRequested)
        header_row.addWidget(self.refresh_btn)
        layout.addLayout(header_row)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("homeScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(self.scroll, 1)

        self.content = QWidget()
        self.content.setObjectName("homeContent")
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(GAP)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.stats_btn = QPushButton("📊")
        self.stats_btn.setObjectName("homeBtn")
        self.stats_btn.setFixedSize(40, 40)
        self.stats_btn.setToolTip("Statystyki")
        self.stats_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.stats_btn.clicked.connect(self.statsRequested)
        footer.addWidget(self.stats_btn)
        layout.addLayout(footer)

        self._playlists = []
        self._current_index = -1
        self._tiles = []

    def refresh(self, playlists, current_index=-1):
        self._playlists = playlists
        self._current_index = current_index
        for tile in self._tiles:
            tile.deleteLater()
        self._tiles = []

        for index, playlist in enumerate(playlists):
            tile = PlaylistTile(index, self.content)
            tile.clicked.connect(lambda _, i=index: self.playlistClicked.emit(i))
            tile.removeRequested.connect(self.removeRequested)
            cover = first_cover([t.path for t in playlist.tracks])
            pm = None
            if cover:
                pm = QPixmap()
                if not pm.loadFromData(cover):
                    pm = None
            tile.set_cover(pm)
            tile.set_name(playlist.name)
            tile.set_count(len(playlist.tracks))
            self._tiles.append(tile)

        add_tile = self._build_add_tile()
        self._tiles.append(add_tile)

        library_tile = self._build_library_tile()
        self._tiles.append(library_tile)

        download_tile = self._build_download_tile()
        self._tiles.append(download_tile)

        self._relayout()
        self._apply_active()

    def _build_add_tile(self):
        btn = QPushButton("＋\nDodaj playlistę")
        btn.setObjectName("addTile")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(TILE_W, TILE_H)
        btn.clicked.connect(self.addRequested)
        return btn

    def _build_library_tile(self):
        btn = QPushButton("♪\nBiblioteka\nwszystkie utwory")
        btn.setObjectName("addTile")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(TILE_W, TILE_H)
        btn.clicked.connect(self.libraryRequested)
        return btn

    def _build_download_tile(self):
        btn = QPushButton("⤓\nPobierz playlistę\nz YouTube")
        btn.setObjectName("downloadTile")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedSize(TILE_W, TILE_H)
        btn.clicked.connect(self.downloadRequested)
        return btn

    def _relayout(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        width = self.content.width() or self.scroll.viewport().width()
        cols = max(1, (width + GAP) // (TILE_W + GAP))
        for i, tile in enumerate(self._tiles):
            self.grid.addWidget(tile, i // cols, i % cols)

    def _apply_active(self):
        for tile in self._tiles:
            if isinstance(tile, PlaylistTile):
                active = tile._index == self._current_index
                if bool(tile.property("active")) != active:
                    tile.setProperty("active", active)
                    tile.style().unpolish(tile)
                    tile.style().polish(tile)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def set_waiting_state(self, waiting):
        for tile in self._tiles:
            if isinstance(tile, QPushButton) and tile.objectName() == "addTile":
                tile.setEnabled(not waiting)
