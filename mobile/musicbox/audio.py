"""Warstwa odtwarzania audio oparta o kivy.core.audio.SoundLoader.

Na Androidzie SoundLoader uzywa natywnego android.media.MediaPlayer
(obsluguje mp3/ogg/m4a/wav). Pause/resume realizowane przez zapis pozycji
i seek(), bo API Sound nie ma wbudowanego pause.
"""
from kivy.clock import Clock
from kivy.core.audio import SoundLoader

_END_EPSILON = 0.15


class AudioPlayer:
    def __init__(self, on_ended=None, on_tick=None, volume=1.0):
        self.sound = None
        self._volume = volume
        self._pause_pos = 0.0
        self._ended_armed = False
        self._clock = None
        self.on_ended = on_ended
        self.on_tick = on_tick

    # ---------- stan ----------
    @property
    def is_playing(self):
        return self.sound is not None and self.sound.state == "play"

    @property
    def volume(self):
        return self._volume

    @property
    def current_source(self):
        return getattr(self.sound, "source", None)

    def position(self):
        if self.sound is None:
            return 0.0
        return self.sound.get_pos() or 0.0

    def length(self):
        if self.sound is None:
            return 0.0
        return self.sound.length or 0.0

    # ---------- sterowanie ----------
    def play_file(self, path):
        self._stop_clock()
        if self.sound is not None:
            try:
                self.sound.stop()
            except Exception:
                pass
            self.sound.unload()
            self.sound = None
        sound = SoundLoader.load(path)
        if sound is None:
            return False
        self.sound = sound
        self.sound.volume = self._volume
        self.sound.play()
        self._pause_pos = 0.0
        self._ended_armed = True
        self._clock = Clock.schedule_interval(self._tick, 0.25)
        return True

    def pause(self):
        if self.sound is None:
            return
        self._stop_clock()
        self._ended_armed = False
        self._pause_pos = self.sound.get_pos() or 0.0
        self.sound.stop()

    def resume(self):
        if self.sound is None:
            return
        try:
            self.sound.seek(self._pause_pos)
        except Exception:
            pass
        self.sound.play()
        self._ended_armed = True
        self._clock = Clock.schedule_interval(self._tick, 0.25)

    def replay(self):
        if self.sound is None:
            return
        try:
            self.sound.seek(0)
        except Exception:
            pass
        self.sound.play()
        self._ended_armed = True
        self._clock = Clock.schedule_interval(self._tick, 0.25)

    def stop(self):
        self._stop_clock()
        self._ended_armed = False
        if self.sound is not None:
            try:
                self.sound.stop()
            except Exception:
                pass
            self.sound.unload()
            self.sound = None

    def seek(self, position):
        if self.sound is None:
            return
        try:
            self.sound.seek(max(0.0, float(position)))
        except Exception:
            pass

    def set_resume_position(self, position):
        """Ustawia pozycje, z ktorej wznowi resume() (bez wplywu na sound)."""
        self._pause_pos = max(0.0, float(position))

    def set_volume(self, value):
        self._volume = max(0.0, min(1.0, float(value)))
        if self.sound is not None:
            self.sound.volume = self._volume

    # ---------- wewnetrzne ----------
    def _tick(self, dt):
        if self.sound is None:
            return
        length = self.length()
        pos = self.position()
        if self.on_tick is not None:
            self.on_tick(pos, length)
        if (
            self._ended_armed
            and length > 1.0
            and pos >= length - _END_EPSILON
        ):
            self._ended_armed = False
            self._stop_clock()
            if self.on_ended is not None:
                self.on_ended()

    def _stop_clock(self):
        if self._clock is not None:
            self._clock.cancel()
            self._clock = None
