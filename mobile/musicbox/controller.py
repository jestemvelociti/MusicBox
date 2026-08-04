"""Logika odtwarzania dla wersji mobilnej.

Czysta logika (bez UI), wzorowana na desktopowym ui/main_window.py.
Mozna ja testowac niezaleznie od Kivy.
"""
import random

REPEAT_ALL = "all"
REPEAT_ONE = "one"
REPEAT_OFF = "off"


class PlaybackController:
    def __init__(self, playlist=None):
        self._playlist = playlist
        self._shuffle_on = False
        self._repeat_mode = REPEAT_ALL
        self._shuffle_queue = []
        self._history = []
        self._played_this_round = set()

    # ---------- konfiguracja ----------
    @property
    def playlist(self):
        return self._playlist

    def set_playlist(self, playlist):
        self._playlist = playlist
        if self._shuffle_on:
            self._refill_shuffle()

    @property
    def shuffle_on(self):
        return self._shuffle_on

    @property
    def repeat_mode(self):
        return self._repeat_mode

    def set_shuffle(self, on):
        self._shuffle_on = bool(on)
        if self._shuffle_on:
            self._shuffle_queue = []
            self._history = []
            self._refill_shuffle()
        else:
            self._shuffle_queue = []
            self._history = []
            self._played_this_round = set()

    def set_repeat(self, mode):
        if mode not in (REPEAT_ALL, REPEAT_ONE, REPEAT_OFF):
            mode = REPEAT_ALL
        self._repeat_mode = mode

    # ---------- odtwarzanie ----------
    @property
    def current_index(self):
        if self._playlist is None:
            return -1
        return self._playlist.current_index

    def current(self):
        if self._playlist is None:
            return None
        return self._playlist.current()

    def play_at(self, index, record=True):
        if self._playlist is None:
            return None
        if not (0 <= index < len(self._playlist.tracks)):
            return None
        previous = self._playlist.current_index
        if record and self._shuffle_on and previous >= 0 and previous != index:
            self._history.append(previous)
        self._playlist.current_index = index
        if self._shuffle_on:
            self._shuffle_queue = [i for i in self._shuffle_queue if i != index]
            self._played_this_round.add(index)
        return self._playlist.current()

    def play_next(self):
        if self._playlist is None or not self._playlist.tracks:
            return None
        if self._shuffle_on:
            nxt = self._shuffle_next()
        else:
            nxt = self._playlist.next_index()
        if nxt >= 0:
            return self.play_at(nxt)
        return None

    def play_prev(self):
        if self._playlist is None:
            return None
        if self._shuffle_on and self._history:
            return self.play_at(self._history.pop(), record=False)
        prev = self._playlist.prev_index()
        if prev >= 0:
            return self.play_at(prev)
        return None

    def on_playback_ended(self):
        """Zwraca tuple (akcja, track). Akcja: 'replay' | 'next' | 'stop'."""
        if self._repeat_mode == REPEAT_ONE:
            return "replay", self.current()
        if self._playlist is None or not self._playlist.tracks:
            return "stop", None
        if self._repeat_mode == REPEAT_OFF:
            if self._shuffle_on:
                if len(self._played_this_round) >= len(self._playlist.tracks):
                    return "stop", None
            elif self._playlist.current_index >= len(self._playlist.tracks) - 1:
                return "stop", None
        nxt = self.play_next()
        if nxt is None:
            return "stop", None
        return "next", nxt

    def resume_after_round(self):
        """Rekcja na przycisk Play, gdy runda shuffle sie skonczyla (repeat off)."""
        if (
            self._shuffle_on
            and self._playlist is not None
            and len(self._played_this_round) >= len(self._playlist.tracks)
        ):
            self._refill_shuffle()
            nxt = self._shuffle_next()
            if nxt >= 0:
                return self.play_at(nxt)
        return None

    # ---------- shuffle ----------
    def _refill_shuffle(self):
        if self._playlist is None:
            return
        current = self._playlist.current_index
        indices = [i for i in range(len(self._playlist.tracks)) if i != current]
        random.shuffle(indices)
        self._shuffle_queue = indices
        self._played_this_round = set()

    def _shuffle_next(self):
        if self._playlist is None:
            return -1
        for _ in range(2):
            if not self._shuffle_queue:
                self._refill_shuffle()
            while self._shuffle_queue:
                index = self._shuffle_queue.pop(0)
                if 0 <= index < len(self._playlist.tracks):
                    return index
        return -1
