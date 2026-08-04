import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.stats import format_listening
from core.tags import display_name

PL_MONTHS = [
    "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
    "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
]


def month_label(key):
    year, month = key.split("-")
    return f"{PL_MONTHS[int(month) - 1]} {year}"


def format_date_iso(iso):
    if not iso:
        return ""
    parts = str(iso).split("-")
    if len(parts) == 3:
        return f"{int(parts[2])}.{int(parts[1])}.{parts[0]}"
    return str(iso)


def _top(counts, n):
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return items[:n]


class StatsView(QWidget):
    createRequested = Signal(str)
    renameRequested = Signal(str)
    resetRequested = Signal()
    exportRequested = Signal()
    importRequested = Signal()
    imageRequested = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statsView")
        self._profile_name = ""
        self._selected_month = None
        self._selected_year = None
        self._active_period = None
        self._active_kind = None
        self._periods_signature = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("homeScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("homeContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        header = QLabel("Statystyki")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        layout.addWidget(header)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("addSubtitle")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.create_box = QWidget()
        c_layout = QVBoxLayout(self.create_box)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(8)
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("searchBox")
        self.name_edit.setPlaceholderText("Nazwa profilu…")
        c_layout.addWidget(self.name_edit)
        self.create_btn = QPushButton("Załóż profil")
        self.create_btn.setObjectName("confirmAddBtn")
        self.create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_btn.clicked.connect(self._on_create)
        c_layout.addWidget(self.create_btn, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.create_box)

        self.detail_box = QWidget()
        d_layout = QVBoxLayout(self.detail_box)
        d_layout.setContentsMargins(0, 0, 0, 0)
        d_layout.setSpacing(12)

        self.profile_label = QLabel("")
        self.profile_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        d_layout.addWidget(self.profile_label)

        self.time_label = QLabel("")
        self.time_label.setObjectName("addSubtitle")
        d_layout.addWidget(self.time_label)

        self.tracks_header = QLabel("Top 3 najczęściej słuchane utwory")
        self.tracks_header.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        d_layout.addWidget(self.tracks_header)
        self.tracks_list = QLabel("")
        self.tracks_list.setObjectName("addSubtitle")
        self.tracks_list.setWordWrap(True)
        d_layout.addWidget(self.tracks_list)

        self.artists_header = QLabel("Top 3 najczęściej słuchani wykonawcy")
        self.artists_header.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        d_layout.addWidget(self.artists_header)
        self.artists_list = QLabel("")
        self.artists_list.setObjectName("addSubtitle")
        self.artists_list.setWordWrap(True)
        d_layout.addWidget(self.artists_list)

        self.rename_box = QWidget()
        r_layout = QHBoxLayout(self.rename_box)
        r_layout.setContentsMargins(0, 0, 0, 0)
        r_layout.setSpacing(8)
        self.rename_edit = QLineEdit()
        self.rename_edit.setObjectName("searchBox")
        self.rename_edit.setPlaceholderText("Nowa nazwa profilu…")
        self.rename_save_btn = QPushButton("Zapisz")
        self.rename_save_btn.setObjectName("confirmAddBtn")
        self.rename_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rename_save_btn.clicked.connect(self._on_rename)
        self.rename_cancel_btn = QPushButton("Anuluj")
        self.rename_cancel_btn.setObjectName("cancelBtn")
        self.rename_cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rename_cancel_btn.clicked.connect(self._hide_rename)
        r_layout.addWidget(self.rename_edit, 1)
        r_layout.addWidget(self.rename_save_btn)
        r_layout.addWidget(self.rename_cancel_btn)
        self.rename_box.setVisible(False)
        d_layout.addWidget(self.rename_box)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.change_btn = QPushButton("Zmień profil")
        self.change_btn.setObjectName("homeBtn")
        self.change_btn.clicked.connect(self._show_rename)
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("homeBtn")
        self.reset_btn.clicked.connect(self.resetRequested)
        self.export_btn = QPushButton("Pobierz profil")
        self.export_btn.setObjectName("homeBtn")
        self.export_btn.clicked.connect(self.exportRequested)
        self.import_btn = QPushButton("Wczytaj profil")
        self.import_btn.setObjectName("homeBtn")
        self.import_btn.clicked.connect(self.importRequested)
        for b in (self.change_btn, self.reset_btn, self.export_btn, self.import_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            actions.addWidget(b)
        actions.addStretch(1)
        d_layout.addLayout(actions)

        self.summaries_header = QLabel("Podsumowania")
        self.summaries_header.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        d_layout.addWidget(self.summaries_header)

        month_row = QHBoxLayout()
        month_row.setSpacing(8)
        month_caption = QLabel("Miesiąc:")
        month_caption.setObjectName("addSubtitle")
        month_row.addWidget(month_caption)
        self.month_combo = QComboBox()
        self.month_combo.setMinimumWidth(220)
        self.month_combo.currentIndexChanged.connect(self._on_month_changed)
        month_row.addWidget(self.month_combo, 1)
        d_layout.addLayout(month_row)

        year_row = QHBoxLayout()
        year_row.setSpacing(8)
        year_caption = QLabel("Rok:")
        year_caption.setObjectName("addSubtitle")
        year_row.addWidget(year_caption)
        self.year_combo = QComboBox()
        self.year_combo.setMinimumWidth(220)
        self.year_combo.currentIndexChanged.connect(self._on_year_changed)
        year_row.addWidget(self.year_combo, 1)
        d_layout.addLayout(year_row)

        self.summary_title = QLabel("")
        self.summary_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff;")
        d_layout.addWidget(self.summary_title)

        self.summary_body = QLabel("")
        self.summary_body.setObjectName("addSubtitle")
        self.summary_body.setWordWrap(True)
        d_layout.addWidget(self.summary_body)

        image_row = QHBoxLayout()
        image_row.setSpacing(8)
        self.image_btn = QPushButton("🖼 Wygeneruj obraz")
        self.image_btn.setObjectName("confirmAddBtn")
        self.image_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_btn.setEnabled(False)
        self.image_btn.clicked.connect(self._on_image_requested)
        image_row.addWidget(self.image_btn)
        image_row.addStretch(1)
        d_layout.addLayout(image_row)

        layout.addWidget(self.detail_box)
        layout.addStretch(1)

        self.scroll.setWidget(content)
        root_layout.addWidget(self.scroll, 1)

    def _on_create(self):
        name = self.name_edit.text().strip()
        if name:
            self.createRequested.emit(name)

    def _set_active_period(self, label, summary):
        self._active_period = (label, summary) if label is not None else None
        self.image_btn.setEnabled(self._active_period is not None)

    def _on_image_requested(self):
        if self._active_period:
            label, summary = self._active_period
            self.imageRequested.emit(label, summary)

    def _on_month_changed(self, index):
        data = self.month_combo.itemData(index)
        if data is None:
            self._selected_month = None
            self._set_active_period(None, None)
            self._render_summary(None)
            return
        key, summary = data
        self._selected_month = key
        self._active_kind = "month"
        self._set_active_period(month_label(key), summary)
        self._render_summary(data)

    def _on_year_changed(self, index):
        data = self.year_combo.itemData(index)
        if data is None:
            self._selected_year = None
            self._set_active_period(None, None)
            self._render_summary(None)
            return
        year, summary = data
        self._selected_year = year
        self._active_kind = "year"
        self._set_active_period(f"Rok {year}", summary)
        self._render_summary(data)

    def _render_summary(self, item_data):
        if item_data is None:
            self.summary_title.setText("")
            self.summary_body.setText("")
            return
        key, summary = item_data
        if isinstance(key, int):
            title = f"Podsumowanie roku {key}"
        else:
            title = f"Podsumowanie miesiąca: {month_label(key)}"
        listening = int(summary.get("listening_seconds", 0))
        play_counts = summary.get("play_counts") or {}
        artist_counts = summary.get("artist_counts") or {}
        lines = ["Czas słuchania: " + format_listening(listening)]
        total_plays = sum(play_counts.values())
        lines.append(f"Liczba odsłuchań: {total_plays}")
        top_tracks = _top(play_counts, 3)
        if top_tracks:
            lines.append("Najczęściej słuchane utwory:")
            for i, (path, count) in enumerate(top_tracks, start=1):
                stem = os.path.splitext(os.path.basename(path))[0]
                lines.append(f"  {i}. {display_name(path, stem)} — {count} odsłuchań")
        else:
            lines.append("Najczęściej słuchane utwory: brak")
        top_artists = _top(artist_counts, 3)
        if top_artists:
            lines.append("Najczęściej słuchani wykonawcy:")
            for i, (artist, count) in enumerate(top_artists, start=1):
                lines.append(f"  {i}. {artist} — {count} odsłuchań")
        else:
            lines.append("Najczęściej słuchani wykonawcy: brak")
        self.summary_title.setText(title)
        self.summary_body.setText("\n".join(lines))

    def _populate_periods(self, stats):
        prev_month = self._selected_month
        prev_year = self._selected_year

        months = stats.months()
        years = stats.year_summaries()
        signature = (
            tuple(months),
            tuple((s.get("year"), s.get("created_on")) for s in years),
        )
        rebuild = signature != self._periods_signature
        self._periods_signature = signature

        if not rebuild:
            self._update_active_summary(stats)
            return

        self.month_combo.blockSignals(True)
        self.month_combo.clear()
        self.month_combo.addItem("— wybierz miesiąc —", None)
        for key in reversed(months):
            self.month_combo.addItem(month_label(key), (key, stats.month_summary(key)))
        self.month_combo.blockSignals(False)

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItem("— wybierz rok —", None)
        for s in years:
            year = int(s.get("year", 0))
            created = format_date_iso(s.get("created_on"))
            label = f"Rok {year}" + (f" · {created}" if created else "")
            self.year_combo.addItem(label, (year, s))
        self.year_combo.blockSignals(False)

        target_month = None
        target_year = None
        if self._active_kind == "year":
            target_year = prev_year
        elif self._active_kind == "month":
            target_month = prev_month
        elif prev_year is not None:
            target_year = prev_year
        elif prev_month is not None:
            target_month = prev_month

        if target_month is None and target_year is None:
            if self.month_combo.count() > 1:
                target_month = self.month_combo.itemData(1)[0]
            elif self.year_combo.count() > 1:
                target_year = self.year_combo.itemData(1)[0]

        month_index = 0
        if target_month is not None:
            for i in range(1, self.month_combo.count()):
                data = self.month_combo.itemData(i)
                if data and data[0] == target_month:
                    month_index = i
                    break
        year_index = 0
        if target_year is not None:
            for i in range(1, self.year_combo.count()):
                data = self.year_combo.itemData(i)
                if data and data[0] == target_year:
                    year_index = i
                    break

        self.month_combo.blockSignals(True)
        self.month_combo.setCurrentIndex(month_index)
        self.month_combo.blockSignals(False)
        self.year_combo.blockSignals(True)
        self.year_combo.setCurrentIndex(year_index)
        self.year_combo.blockSignals(False)

        self._selected_month = None
        self._selected_year = None

        if month_index > 0:
            data = self.month_combo.itemData(month_index)
            key = data[0]
            self._selected_month = key
            summary = stats.month_summary(key) or data[1]
            self._set_active_period(month_label(key), summary)
            self._render_summary((key, summary))
        elif year_index > 0:
            data = self.year_combo.itemData(year_index)
            year = data[0]
            self._selected_year = year
            self._set_active_period(f"Rok {year}", data[1])
            self._render_summary(data)
        else:
            self._set_active_period(None, None)
            self.summary_title.setText("")
            self.summary_body.setText("Brak danych okresowych")

    def _update_active_summary(self, stats):
        if self._active_kind == "month" and self._selected_month:
            summary = stats.month_summary(self._selected_month)
            if summary:
                self._set_active_period(month_label(self._selected_month), summary)
                self._render_summary((self._selected_month, summary))
        elif self._active_kind == "year" and self._selected_year:
            for s in stats.year_summaries():
                if int(s.get("year", 0)) == self._selected_year:
                    self._set_active_period(f"Rok {self._selected_year}", s)
                    self._render_summary(s)
                    break

    def _show_rename(self):
        self.rename_edit.setText(self._profile_name)
        self.rename_box.setVisible(True)

    def _hide_rename(self):
        self.rename_box.setVisible(False)

    def _on_rename(self):
        name = self.rename_edit.text().strip()
        if name:
            self.renameRequested.emit(name)
            self._hide_rename()

    def refresh(self, stats):
        self._profile_name = stats.profile_name if stats.has_profile else ""
        has = stats.has_profile
        self.create_box.setVisible(not has)
        self.detail_box.setVisible(has)
        if not has:
            self.subtitle.setText(
                "Załóż profil, aby śledzić czas słuchania i najczęściej odtwarzane utwory."
            )
            self.rename_box.setVisible(False)
            self._populate_periods(stats)
            return
        self.subtitle.setText("Czas słuchania i odsłuchania zapisywane są automatycznie.")
        self.profile_label.setText(f"Profil: {stats.profile_name}")
        self.time_label.setText(
            "Czas słuchania: " + format_listening(stats.total_listening_seconds())
        )
        top_tracks = stats.top_tracks(3)
        if top_tracks:
            lines = []
            for i, (path, count) in enumerate(top_tracks, start=1):
                stem = os.path.splitext(os.path.basename(path))[0]
                name = display_name(path, stem)
                lines.append(f"{i}. {name} — {count} odsłuchań")
            self.tracks_list.setText("\n".join(lines))
        else:
            self.tracks_list.setText("Brak odsłuchań")
        top_artists = stats.top_artists(3)
        if top_artists:
            lines = [
                f"{i}. {artist} — {count} odsłuchań"
                for i, (artist, count) in enumerate(top_artists, start=1)
            ]
            self.artists_list.setText("\n".join(lines))
        else:
            self.artists_list.setText("Brak odsłuchań")
        self._populate_periods(stats)
