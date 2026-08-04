from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMenu,
    QTableView,
)

from core.cover import extract_cover
from core.tags import display_name


class TrackList(QTableView):
    playRequested = Signal(int)
    removeRequested = Signal(int)
    revealRequested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.allow_remove = True
        self.setObjectName("trackTable")
        self.setModel(QStandardItemModel(self))
        self.model().setHorizontalHeaderLabels(["#", "Okładka", "Tytuł"])

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(True)
        self.setIconSize(QSize(24, 24))
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(32)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 44)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 40)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        self.doubleClicked.connect(self._on_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_playlist(self, playlist):
        model = self.model()
        model.removeRows(0, model.rowCount())
        if playlist is None:
            return
        for i, track in enumerate(playlist.tracks, start=1):
            num = QStandardItem(str(i))
            num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            cover = QStandardItem()
            cover.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            pixmap = self._cover_pixmap(track.path)
            if pixmap is not None:
                cover.setIcon(QIcon(pixmap))
            title = QStandardItem(display_name(track.path, track.title))
            model.appendRow([num, cover, title])

    @staticmethod
    def _cover_pixmap(path):
        data = extract_cover(path)
        if not data:
            return None
        pm = QPixmap()
        if not pm.loadFromData(data):
            return None
        return pm.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)

    def set_filter(self, text):
        query = text.strip().lower()
        model = self.model()
        for row in range(model.rowCount()):
            item = model.item(row, 2)
            match = not query or (item is not None and query in item.text().lower())
            self.setRowHidden(row, not match)

    def highlight_current(self, index):
        if index < 0:
            self.clearSelection()
            return
        self.selectRow(index)

    def _on_double_clicked(self, index):
        self.playRequested.emit(index.row())

    def _on_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        menu = QMenu(self)
        play = menu.addAction("Odtwórz teraz")
        remove = menu.addAction("Usuń z playlisty")
        if not self.allow_remove:
            remove.setVisible(False)
        menu.addSeparator()
        reveal = menu.addAction("Pokaż w folderze")
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is play:
            self.playRequested.emit(row)
        elif chosen is remove:
            self.removeRequested.emit(row)
        elif chosen is reveal:
            self.revealRequested.emit(row)
