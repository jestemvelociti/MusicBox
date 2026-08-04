import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mobile"))

import pytest

from core.playlist import Playlist
from musicbox.controller import PlaybackController, REPEAT_ALL, REPEAT_OFF, REPEAT_ONE


@pytest.fixture
def playlist():
    pl = Playlist("Rock")
    pl.add_tracks([f"C:\\muzyka\\{name}.mp3" for name in ("a", "b", "c", "d")])
    return pl


def test_play_at_sets_current(playlist):
    c = PlaybackController(playlist)
    track = c.play_at(2)
    assert track is playlist.tracks[2]
    assert playlist.current_index == 2


def test_play_at_out_of_range_returns_none(playlist):
    c = PlaybackController(playlist)
    assert c.play_at(99) is None
    assert c.play_at(-1) is None


def test_play_next_linear(playlist):
    c = PlaybackController(playlist)
    c.play_at(1)
    nxt = c.play_next()
    assert nxt is playlist.tracks[2]


def test_play_prev_history_in_shuffle(playlist):
    c = PlaybackController(playlist)
    c.set_shuffle(True)
    c.play_at(0)
    c.play_at(3)
    prev = c.play_prev()
    assert prev is playlist.tracks[0]


def test_repeat_one_replays(playlist):
    c = PlaybackController(playlist)
    c.set_repeat(REPEAT_ONE)
    c.play_at(0)
    action, track = c.on_playback_ended()
    assert action == "replay"
    assert track is playlist.tracks[0]


def test_repeat_off_shuffle_stops_after_round(playlist):
    c = PlaybackController(playlist)
    c.set_repeat(REPEAT_OFF)
    c.set_shuffle(True)
    for i in range(len(playlist.tracks)):
        c.play_at(i)
    action, _ = c.on_playback_ended()
    assert action == "stop"


def test_repeat_off_shuffle_continues_mid_round(playlist):
    c = PlaybackController(playlist)
    c.set_repeat(REPEAT_OFF)
    c.set_shuffle(True)
    c.play_at(0)
    action, track = c.on_playback_ended()
    assert action == "next"
    assert track is not None


def test_repeat_off_linear_stops_at_end(playlist):
    c = PlaybackController(playlist)
    c.set_repeat(REPEAT_OFF)
    c.play_at(len(playlist.tracks) - 1)
    action, _ = c.on_playback_ended()
    assert action == "stop"


def test_repeat_all_wraps(playlist):
    c = PlaybackController(playlist)
    c.set_repeat(REPEAT_ALL)
    c.play_at(len(playlist.tracks) - 1)
    action, track = c.on_playback_ended()
    assert action == "next"
    assert track is playlist.tracks[0]


def test_resume_after_round_starts_new_round(playlist):
    c = PlaybackController(playlist)
    c.set_repeat(REPEAT_OFF)
    c.set_shuffle(True)
    for i in range(len(playlist.tracks)):
        c.play_at(i)
    assert c.on_playback_ended()[0] == "stop"

    track = c.resume_after_round()

    assert track is not None
    assert len(c._played_this_round) == 1
    assert track in playlist.tracks


def test_set_repeat_invalid_falls_back_to_all(playlist):
    c = PlaybackController(playlist)
    c.set_repeat("bogus")
    assert c.repeat_mode == REPEAT_ALL


def test_play_at_out_of_round_after_resume(playlist):
    c = PlaybackController(playlist)
    c.set_repeat(REPEAT_OFF)
    c.set_shuffle(True)
    for i in range(len(playlist.tracks)):
        c.play_at(i)
    c.resume_after_round()
    first = c.current_index
    action, _ = c.on_playback_ended()
    assert action == "next"
    assert c.current_index != first
