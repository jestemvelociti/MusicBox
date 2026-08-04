"""Warstwa odtwarzania audio.

Na Androidzie: KeepAliveService (Java) trzyma MediaPlayera — dzieki temu
przyciski powiadomienia dzialaja w tle nawet gdy petla Kivy jest zamrozona
(Moto/Xiaomi). Python wysyla komendy do serwisu i odbiera stan/pozycje
przez broadcasty. Na desktopie: kivy.core.audio.SoundLoader.
"""
import os

from kivy.clock import Clock
from kivy.core.audio import SoundLoader

from musicbox import android_io

_END_EPSILON = 0.15

CMD_PLAY = "org.musicbox.musicbox.cmd.PLAY"
CMD_PAUSE = "org.musicbox.musicbox.cmd.PAUSE"
CMD_RESUME = "org.musicbox.musicbox.cmd.RESUME"
CMD_NEXT = "org.musicbox.musicbox.cmd.NEXT"
CMD_PREV = "org.musicbox.musicbox.cmd.PREV"
CMD_STOP = "org.musicbox.musicbox.cmd.STOP"
CMD_SEEK = "org.musicbox.musicbox.cmd.SEEK"
CMD_REPEAT = "org.musicbox.musicbox.cmd.REPEAT"

STATE_CHANGED = "org.musicbox.musicbox.state.CHANGED"
STATE_POSITION = "org.musicbox.musicbox.state.POSITION"


class _ServiceAudio:
    """Klient KeepAliveService (Java MediaPlayer). Stan z broadcastow."""

    def __init__(self, on_ended=None, on_tick=None, volume=1.0):
        self._playing = False
        self._position = 0.0
        self._length = 0.0
        self._source = None
        self.on_ended = on_ended
        self.on_tick = on_tick

    def provider_name(self):
        return "android-service"

    @property
    def is_playing(self):
        return self._playing

    @property
    def current_source(self):
        return self._source

    @property
    def volume(self):
        return 1.0

    def position(self):
        return self._position

    def length(self):
        return self._length

    def play(self, path, index, paths, repeat, title="", cover=None, resume_ms=0):
        android_io.send_playback_command(
            CMD_PLAY,
            path=path,
            index=int(index),
            paths="\n".join(paths),
            repeat=int(repeat),
            title=title or "",
            cover=cover or "",
            resume_ms=int(resume_ms),
        )
        self._source = path

    def play_file(self, path):
        return False

    def pause(self):
        self._playing = False
        android_io.send_playback_command(CMD_PAUSE)

    def resume(self):
        android_io.send_playback_command(CMD_RESUME)

    def replay(self):
        android_io.send_playback_command(CMD_SEEK, position_ms=0)
        android_io.send_playback_command(CMD_RESUME)

    def stop(self):
        self._playing = False
        android_io.send_playback_command(CMD_STOP)

    def seek(self, position):
        android_io.send_playback_command(
            CMD_SEEK, position_ms=int(max(0.0, float(position)) * 1000)
        )

    def set_resume_position(self, position):
        pass

    def set_volume(self, value):
        pass

    def set_repeat(self, repeat):
        android_io.send_playback_command(CMD_REPEAT, repeat=int(repeat))

    def apply_state(self, path, index, playing, ended, title, cover):
        if path:
            self._source = path
        self._playing = bool(playing)
        if ended:
            self._playing = False
            self._position = 0.0

    def apply_position(self, position_ms, duration_ms):
        self._position = position_ms / 1000.0
        if duration_ms and duration_ms > 0:
            self._length = duration_ms / 1000.0
        if self.on_tick is not None:
            self.on_tick(self._position, self._length)


class _DesktopAudio:
    """Kivy SoundLoader (desktop)."""

    def __init__(self, on_ended=None, on_tick=None, volume=1.0):
        self.sound = None
        self._volume = volume
        self._pause_pos = 0.0
        self._ended_armed = False
        self._clock = None
        self._source = None
        self.on_ended = on_ended
        self.on_tick = on_tick

    def provider_name(self):
        return "kivy"

    @property
    def is_playing(self):
        return self.sound is not None and self.sound.state == "play"

    @property
    def current_source(self):
        return self._source

    @property
    def volume(self):
        return self._volume

    def position(self):
        if self.sound is None:
            return 0.0
        return self.sound.get_pos() or 0.0

    def length(self):
        if self.sound is None:
            return 0.0
        return self.sound.length or 0.0

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
            self._source = None
            return False
        self.sound = sound
        self.sound.volume = self._volume
        self.sound.play()
        self._source = path
        self._pause_pos = 0.0
        self._ended_armed = True
        self._clock = Clock.schedule_interval(self._tick, 0.25)
        return True

    def pause(self):
        self._stop_clock()
        self._ended_armed = False
        if self.sound is None:
            return
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
        self._source = None

    def seek(self, position):
        if self.sound is None:
            return
        try:
            self.sound.seek(max(0.0, float(position)))
        except Exception:
            pass

    def set_resume_position(self, position):
        self._pause_pos = max(0.0, float(position))

    def set_volume(self, value):
        self._volume = max(0.0, min(1.0, float(value)))
        if self.sound is not None:
            self.sound.volume = self._volume

    def _tick(self, dt):
        length = self.length()
        pos = self.position()
        if self.on_tick is not None:
            self.on_tick(pos, length)
        if self._ended_armed and length > 1.0 and pos >= length - _END_EPSILON:
            self._ended_armed = False
            self._stop_clock()
            if self.on_ended is not None:
                self.on_ended()

    def _stop_clock(self):
        if self._clock is not None:
            self._clock.cancel()
            self._clock = None


class AudioPlayer:
    def __init__(self, on_ended=None, on_tick=None, volume=1.0):
        self._volume = volume
        if android_io.is_android():
            self._backend = _ServiceAudio(on_ended, on_tick, volume)
        else:
            self._backend = _DesktopAudio(on_ended, on_tick, volume)

    def provider_name(self):
        return self._backend.provider_name()

    @property
    def is_playing(self):
        return self._backend.is_playing

    @property
    def current_source(self):
        return self._backend.current_source

    @property
    def volume(self):
        return self._volume

    def position(self):
        return self._backend.position()

    def length(self):
        return self._backend.length()

    def play_file(self, path):
        return self._backend.play_file(path)

    def play(self, path, index, paths, repeat, title="", cover=None, resume_ms=0):
        self._backend.play(path, index, paths, repeat, title, cover, resume_ms)

    def pause(self):
        self._backend.pause()

    def resume(self):
        self._backend.resume()

    def replay(self):
        self._backend.replay()

    def stop(self):
        self._backend.stop()

    def next_track(self):
        if android_io.is_android():
            android_io.send_playback_command(CMD_NEXT)

    def prev_track(self):
        if android_io.is_android():
            android_io.send_playback_command(CMD_PREV)

    def seek(self, position):
        self._backend.seek(position)

    def set_resume_position(self, position):
        self._backend.set_resume_position(position)

    def set_volume(self, value):
        self._volume = max(0.0, min(1.0, float(value)))
        self._backend.set_volume(self._volume)

    def set_repeat(self, repeat):
        if hasattr(self._backend, "set_repeat"):
            self._backend.set_repeat(repeat)

    def apply_state(self, path, index, playing, ended, title, cover):
        if hasattr(self._backend, "apply_state"):
            self._backend.apply_state(path, index, playing, ended, title, cover)

    def apply_position(self, position_ms, duration_ms):
        if hasattr(self._backend, "apply_position"):
            self._backend.apply_position(position_ms, duration_ms)
