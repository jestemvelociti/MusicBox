from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QRegion
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

SCROLL_INTERVAL_MS = 30
SCROLL_STEP_PX = 1
SCROLL_HOLD_MS = 1500


class ScrollingTitle(QWidget):
    def __init__(self, text="", parent=None, object_name="titleLabel", height=22):
        super().__init__(parent)
        self._text_width = 0
        self._x = 0
        self._hold_ticks = 0
        self._scrolling = False

        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self._label = QLabel(self)
        self._label.setObjectName(object_name)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._timer = QTimer(self)
        self._timer.setInterval(SCROLL_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        self.setText(text)

    def setText(self, text):
        self._label.setText(text)
        self._update_metrics()
        self._stop_scroll()
        self._x = 0
        self._hold_ticks = 0
        if self._text_width > self.width():
            self._start_scroll()
        self._reposition()

    def text(self):
        return self._label.text()

    def _update_metrics(self):
        fm = self.fontMetrics()
        self._text_width = fm.horizontalAdvance(self.text()) + 4

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_metrics()
        if self._text_width > self.width():
            self._start_scroll()
        else:
            self._stop_scroll()
            self._x = 0
            self._reposition()

    def _reposition(self):
        self._label.setGeometry(self._x, 0, self._text_width, self.height())
        visible = QRect(-self._x, 0, self.width(), self.height())
        visible = visible.intersected(QRect(0, 0, self._text_width, self.height()))
        self._label.setMask(QRegion(visible))

    def _start_scroll(self):
        if not self._scrolling:
            self._scrolling = True
            self._timer.start()

    def _stop_scroll(self):
        self._scrolling = False
        self._timer.stop()

    def _tick(self):
        if self._hold_ticks > 0:
            self._hold_ticks -= 1
            return
        if self._text_width <= self.width():
            self._stop_scroll()
            self._x = 0
            self._reposition()
            return
        max_offset = max(0, self._text_width - self.width())
        self._x = max(-max_offset, self._x - SCROLL_STEP_PX)
        self._reposition()
        if self._x <= -max_offset:
            self._hold_ticks = max(1, SCROLL_HOLD_MS // SCROLL_INTERVAL_MS)
            self._x = -max_offset
            self._reposition()


class PlayerBar(QFrame):
    playClicked = Signal()
    prevClicked = Signal()
    nextClicked = Signal()
    stopClicked = Signal()
    shuffleToggled = Signal(bool)
    repeatCycled = Signal()
    seekRequested = Signal(int)
    volumeChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerBar")
        self.setFixedHeight(88)
        self._syncing = False

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 8, 16, 8)
        root.setSpacing(16)

        # --- lewa: okładka + tytuł ---
        self.cover = QLabel()
        self.cover.setObjectName("coverLabel")
        self.cover.setFixedSize(56, 56)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder()

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.title_label = ScrollingTitle("Brak utworu")
        self.artist_label = ScrollingTitle("", object_name="subtitleLabel", height=16)
        self.artist_label.setVisible(False)
        title_box.addStretch(1)
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.artist_label)
        title_box.addStretch(1)

        left = QWidget()
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        left_layout.addWidget(self.cover)
        left_layout.addLayout(title_box, 1)
        left_layout.setStretch(0, 0)
        left_layout.setStretch(1, 1)
        root.addWidget(left, 1)

        # --- środek: sterowanie + postęp ---
        center = QVBoxLayout()
        center.setSpacing(6)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.btn_shuffle = QPushButton("🔀")
        self.btn_prev = QPushButton("|<<")
        self.btn_play = QPushButton("▶")
        self.btn_next = QPushButton(">>|")
        self.btn_stop = QPushButton("■")
        self.btn_repeat = QPushButton("🔁")
        for btn, name in (
            (self.btn_shuffle, "ctrlBtn"),
            (self.btn_prev, "ctrlBtn"),
            (self.btn_play, "playBtn"),
            (self.btn_next, "ctrlBtn"),
            (self.btn_stop, "ctrlBtn"),
            (self.btn_repeat, "ctrlBtn"),
        ):
            btn.setObjectName(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(34)
            buttons.addWidget(btn)
        self.btn_shuffle.clicked.connect(self._toggle_shuffle)
        self.btn_shuffle.setCheckable(True)
        self.btn_repeat.setCheckable(True)
        self.btn_repeat.clicked.connect(self.repeatCycled)
        self.btn_prev.clicked.connect(self.prevClicked)
        self.btn_play.clicked.connect(self.playClicked)
        self.btn_next.clicked.connect(self.nextClicked)
        self.btn_stop.clicked.connect(self.stopClicked)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.setEnabled(False)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("timeLabel")

        progress = QHBoxLayout()
        progress.setSpacing(10)
        progress.addWidget(self.position_slider, 1)
        progress.addWidget(self.time_label)

        center.addLayout(buttons)
        center.addLayout(progress)
        root.addLayout(center, 3)

        # --- prawa: głośność ---
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(110)
        self.volume_slider.valueChanged.connect(self.volumeChanged)

        vol_box = QVBoxLayout()
        vol_label = QLabel("🔊")
        vol_label.setObjectName("timeLabel")
        vol_box.addStretch(1)
        vol_box.addLayout(self._hbox(vol_label, self.volume_slider))
        vol_box.addStretch(1)
        root.addLayout(vol_box)

        # postęp
        self.position_slider.sliderPressed.connect(self._pos_pressed)
        self.position_slider.sliderReleased.connect(self._pos_released)

    @staticmethod
    def _hbox(*widgets):
        hb = QHBoxLayout()
        hb.setSpacing(8)
        for w in widgets:
            hb.addWidget(w)
        return hb

    def _placeholder(self):
        pm = QPixmap(56, 56)
        pm.fill(Qt.GlobalColor.transparent)
        self.cover.setPixmap(pm)
        self.cover.setText("♪")
        self.cover.setStyleSheet(
            "QLabel#coverLabel { background-color: #22304f; border-radius: 8px; color: #5c90ff; font-size: 22px; }"
        )

    # --- API dla main_window ---
    def set_track(self, title, artist=None, pixmap=None):
        self.title_label.setText(title or "Brak utworu")
        if artist:
            self.artist_label.setText(str(artist))
            self.artist_label.setVisible(True)
        else:
            self.artist_label.setVisible(False)
        if pixmap is not None:
            scaled = pixmap.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            self.cover.setPixmap(scaled)
            self.cover.setText("")
            self.cover.setStyleSheet("QLabel#coverLabel { background-color: transparent; border-radius: 8px; }")
        else:
            self._placeholder()

    def set_playing(self, playing):
        self.btn_play.setText("⏸" if playing else "▶")

    def _toggle_shuffle(self):
        on = self.btn_shuffle.isChecked()
        self.shuffleToggled.emit(on)

    def set_shuffle(self, on):
        self.btn_shuffle.setChecked(bool(on))

    def set_repeat(self, mode):
        self.btn_repeat.setChecked(mode != "off")
        if mode == "one":
            self.btn_repeat.setText("🔂")
        else:
            self.btn_repeat.setText("🔁")

    def set_position(self, ms):
        if not self._syncing:
            self.position_slider.setValue(ms)
        dur = self.position_slider.maximum()
        self.time_label.setText(f"{format_time(ms)} / {format_time(dur)}")

    def set_duration(self, ms):
        self.position_slider.setRange(0, max(0, ms))
        self.position_slider.setEnabled(ms > 0)
        self.time_label.setText(f"0:00 / {format_time(ms)}")

    def set_volume(self, value):
        self.volume_slider.setValue(value)

    def _pos_pressed(self):
        self._syncing = True

    def _pos_released(self):
        self._syncing = False
        self.seekRequested.emit(self.position_slider.value())


def format_time(ms):
    total = max(0, ms // 1000)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
