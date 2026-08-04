from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class PlayerEngine(QObject):
    positionChanged = Signal(int)
    durationChanged = Signal(int)
    trackChanged = Signal(str)
    trackStarted = Signal(str)
    playbackEnded = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.media.setAudioOutput(self.audio)
        self._pending_count_source = None

        self.media.positionChanged.connect(self._forward_position)
        self.media.durationChanged.connect(self._forward_duration)
        self.media.mediaStatusChanged.connect(self._on_status)
        self.media.errorOccurred.connect(self._on_error)
        self.media.playbackStateChanged.connect(self._on_playback_state)

    def _forward_position(self, value):
        self.positionChanged.emit(int(value))

    def _forward_duration(self, value):
        self.durationChanged.emit(int(value))

    def _on_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.playbackEnded.emit()

    def _on_playback_state(self, state):
        if state != QMediaPlayer.PlaybackState.PlayingState:
            return
        if self._pending_count_source is None:
            return
        source = self.media.source().toLocalFile()
        if source and source == self._pending_count_source:
            self._pending_count_source = None
            self.trackStarted.emit(source)

    def _on_error(self, error, message):
        self.errorOccurred.emit(message)

    def play(self):
        self.media.play()

    def pause(self):
        self.media.pause()

    def stop(self):
        self.media.stop()

    def replay(self):
        self.media.setPosition(0)
        self.media.play()

    def set_track(self, path):
        self.media.stop()
        self.media.setSource(QUrl.fromLocalFile(path))
        self._pending_count_source = path
        self.trackChanged.emit(path)
        self.play()

    @property
    def is_playing(self):
        return self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    @property
    def volume(self):
        return int(self.audio.volume() * 100)

    def set_volume(self, value):
        self.audio.setVolume(max(0, min(100, int(value))) / 100.0)

    @property
    def current_source(self):
        return self.media.source().toLocalFile()

    def seek(self, ms):
        self.media.setPosition(ms)
