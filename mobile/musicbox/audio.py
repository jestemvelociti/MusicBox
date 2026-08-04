"""Warstwa odtwarzania audio.

Na Androidzie: android.media.MediaPlayer bezposrednio przez jnius (pomija
kivy.core.audio.audio_android, ktore na tym p4a spada na ImportError — brak
android.api_version — co wymuszalo SLD2: martwy suwak (pos=0), brak seeka
i crash przy pauzie aplikacji). Na desktopie: kivy.core.audio.SoundLoader.
"""
import os

from kivy.clock import Clock
from kivy.core.audio import SoundLoader

_END_EPSILON = 0.15


def _is_android():
    return bool(
        os.environ.get("ANDROID_ARGUMENT")
        or os.environ.get("ANDROID_APP_PATH")
        or os.environ.get("P4A_BOOTSTRAP")
    )


try:
    from jnius import autoclass, java_method, PythonJavaClass

    class _CompletionListener(PythonJavaClass):
        __javainterfaces__ = ["android/media/MediaPlayer$OnCompletionListener"]
        __javacontext__ = "app"

        def __init__(self, callback):
            super(_CompletionListener, self).__init__()
            self._callback = callback

        @java_method("(Landroid/media/MediaPlayer;)V")
        def onCompletion(self, mp):
            if self._callback is not None:
                self._callback()

except Exception:
    _CompletionListener = None


class _AndroidPlayer:
    def __init__(self):
        self._player = None
        self._listener = None

    def load(self, path, on_ended):
        self.release()
        player = autoclass("android.media.MediaPlayer")()
        audio_manager = autoclass("android.media.AudioManager")
        attributes = (
            autoclass("android.media.AudioAttributes$Builder")()
            .setLegacyStreamType(audio_manager.STREAM_MUSIC)
            .build()
        )
        player.setAudioAttributes(attributes)
        player.setDataSource(path)
        player.prepare()
        listener = _CompletionListener(on_ended)
        player.setOnCompletionListener(listener)
        self._player = player
        self._listener = listener

    def play(self):
        if self._player is not None:
            self._player.start()

    def pause(self):
        if self._player is not None:
            self._player.pause()

    def stop(self):
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass

    def seek(self, position):
        if self._player is not None:
            self._player.seekTo(int(max(0.0, float(position)) * 1000))

    def position(self):
        if self._player is None:
            return 0.0
        try:
            return self._player.getCurrentPosition() / 1000.0
        except Exception:
            return 0.0

    def length(self):
        if self._player is None:
            return 0.0
        try:
            duration = self._player.getDuration()
            if duration and duration > 0:
                return duration / 1000.0
        except Exception:
            pass
        return 0.0

    def set_volume(self, volume):
        if self._player is not None:
            try:
                self._player.setVolume(float(volume), float(volume))
            except Exception:
                pass

    def release(self):
        if self._player is not None:
            try:
                self._player.release()
            except Exception:
                pass
        self._player = None
        self._listener = None


class AudioPlayer:
    def __init__(self, on_ended=None, on_tick=None, volume=1.0):
        self._android = _AndroidPlayer() if _is_android() else None
        self.sound = None
        self._source = None
        self._volume = volume
        self._pause_pos = 0.0
        self._ended_armed = False
        self._clock = None
        self._playing = False
        self.on_ended = on_ended
        self.on_tick = on_tick

    def provider_name(self):
        return "android" if self._android is not None else "kivy"

    # ---------- stan ----------
    @property
    def is_playing(self):
        if self._android is not None:
            return self._playing
        return self.sound is not None and self.sound.state == "play"

    @property
    def volume(self):
        return self._volume

    @property
    def current_source(self):
        return self._source

    def position(self):
        if self._android is not None:
            return self._android.position()
        if self.sound is None:
            return 0.0
        return self.sound.get_pos() or 0.0

    def length(self):
        if self._android is not None:
            return self._android.length()
        if self.sound is None:
            return 0.0
        return self.sound.length or 0.0

    # ---------- sterowanie ----------
    def play_file(self, path):
        self._stop_clock()
        if self._android is not None:
            try:
                self._android.load(path, self._on_android_ended)
            except Exception:
                self._source = None
                self._playing = False
                return False
            self._android.play()
            self._source = path
            self._pause_pos = 0.0
            self._ended_armed = True
            self._playing = True
            self._clock = Clock.schedule_interval(self._tick, 0.25)
            return True
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
            self._playing = False
            return False
        self.sound = sound
        self.sound.volume = self._volume
        self.sound.play()
        self._source = path
        self._pause_pos = 0.0
        self._ended_armed = True
        self._playing = True
        self._clock = Clock.schedule_interval(self._tick, 0.25)
        return True

    def pause(self):
        self._stop_clock()
        self._ended_armed = False
        self._playing = False
        if self._android is not None:
            self._pause_pos = self._android.position()
            self._android.pause()
            return
        if self.sound is None:
            return
        self._pause_pos = self.sound.get_pos() or 0.0
        self.sound.stop()

    def resume(self):
        if self._android is not None:
            self._android.seek(self._pause_pos)
            self._android.play()
            self._ended_armed = True
            self._playing = True
            self._clock = Clock.schedule_interval(self._tick, 0.25)
            return
        if self.sound is None:
            return
        try:
            self.sound.seek(self._pause_pos)
        except Exception:
            pass
        self.sound.play()
        self._ended_armed = True
        self._playing = True
        self._clock = Clock.schedule_interval(self._tick, 0.25)

    def replay(self):
        if self._android is not None:
            self._android.seek(0)
            self._android.play()
            self._ended_armed = True
            self._playing = True
            self._clock = Clock.schedule_interval(self._tick, 0.25)
            return
        if self.sound is None:
            return
        try:
            self.sound.seek(0)
        except Exception:
            pass
        self.sound.play()
        self._ended_armed = True
        self._playing = True
        self._clock = Clock.schedule_interval(self._tick, 0.25)

    def stop(self):
        self._stop_clock()
        self._ended_armed = False
        self._playing = False
        if self._android is not None:
            self._android.release()
            self._source = None
            return
        if self.sound is not None:
            try:
                self.sound.stop()
            except Exception:
                pass
            self.sound.unload()
            self.sound = None
        self._source = None

    def seek(self, position):
        if self._android is not None:
            self._android.seek(position)
            return
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
        if self._android is not None:
            self._android.set_volume(self._volume)
            return
        if self.sound is not None:
            self.sound.volume = self._volume

    # ---------- wewnetrzne ----------
    def _tick(self, dt):
        length = self.length()
        pos = self.position()
        if self.on_tick is not None:
            self.on_tick(pos, length)
        if (
            self._android is None
            and self._ended_armed
            and length > 1.0
            and pos >= length - _END_EPSILON
        ):
            self._ended_armed = False
            self._stop_clock()
            if self.on_ended is not None:
                self.on_ended()

    def _on_android_ended(self):
        Clock.schedule_once(lambda dt: self._android_ended_main(), 0)

    def _android_ended_main(self):
        if self._playing:
            self._ended_armed = False
            self._playing = False
            self._stop_clock()
            if self.on_ended is not None:
                self.on_ended()

    def _stop_clock(self):
        if self._clock is not None:
            self._clock.cancel()
            self._clock = None
