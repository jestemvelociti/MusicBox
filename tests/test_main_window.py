import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

from core import storage
from core.playlist import Playlist
from ui.home_view import pluralize
from ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    w = MainWindow()
    w.show()
    yield w
    w.close()


def make_m3u(tmp_path, name, entries):
    path = tmp_path / name
    path.write_text("#EXTM3U\n" + "\n".join(entries) + "\n", encoding="utf-8")
    return str(path)


def test_drop_m3u_requires_add_mode(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    m3u = make_m3u(tmp_path, "lista.m3u", ["a.mp3"])

    window._handle_dropped_paths([m3u])
    assert len(window.library) == 0
    assert window._pending_playlist is None
    assert "Dodaj playlistę" in window.status_bar.currentMessage()


def test_drop_audio_requires_add_mode(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    window._handle_dropped_paths([str(tmp_path / "a.mp3")])
    assert len(window.library) == 0
    assert "Dodaj playlistę" in window.status_bar.currentMessage()


def test_drop_m3u_in_add_mode(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    m3u = make_m3u(tmp_path, "lista.m3u", ["a.mp3"])

    window._enter_add_mode()
    window._handle_dropped_paths([m3u])
    assert window._pending_playlist is not None
    assert window._pending_playlist.name == "lista"
    assert window.add_view.stack.currentIndex() == 1


def test_drop_audio_in_add_mode(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")

    window._enter_add_mode()
    window._handle_dropped_paths([str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")])
    assert window._pending_playlist is not None
    assert len(window._pending_playlist.tracks) == 2
    assert window.add_view.stack.currentIndex() == 1


def test_drop_folder_in_add_mode(window, tmp_path):
    folder = tmp_path / "Muzyka"
    folder.mkdir()
    (folder / "a.mp3").write_bytes(b"x")
    (folder / "b.mp3").write_bytes(b"x")
    (folder / "ignored.txt").write_bytes(b"x")

    window._enter_add_mode()
    window._handle_dropped_paths([str(folder)])
    assert window._pending_playlist is not None
    assert len(window._pending_playlist.tracks) == 2
    assert window._pending_playlist.name == "Muzyka"


def test_launch_shows_home(window):
    QApplication.processEvents()
    assert window.stack.currentWidget() is window.home_view
    assert not window.sidebar.isVisible()


def test_home_tile_opens_playlist(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3")])
    window.library.add_playlist(p1)
    window._refresh_home()

    window.home_view.playlistClicked.emit(0)

    assert window.library.current() is p1
    assert window.sidebar.isVisible()
    assert window.stack.currentWidget() is window.playlist_page


def test_show_home_hides_sidebar(window):
    window._open_playlist_from_home(0) if window.library.playlists else None
    window._show_home()
    assert window.stack.currentWidget() is window.home_view
    assert not window.sidebar.isVisible()


def test_drop_csv_opens_download_view(window, tmp_path):
    csv = tmp_path / "playlist.csv"
    csv.write_text(
        "Track Name,Artist Name(s),Album Name,Duration (ms)\n"
        '"Piosenka","Wykonawca","Album X",180000\n',
        encoding="utf-8",
    )

    window._handle_dropped_paths([str(csv)])

    assert window.stack.currentWidget() is window.download_view
    assert window.download_view.file_edit.text() == str(csv)
    assert window.download_view.track_list.count() == 1


def test_drop_csv_while_adding_playlist_goes_to_download(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    csv = tmp_path / "playlist.csv"
    csv.write_text("Track Name,Artist Name\nT,Art\n", encoding="utf-8")

    window._enter_add_mode()
    window._handle_dropped_paths([str(csv)])

    assert window.stack.currentWidget() is window.download_view
    assert window.download_view.track_list.count() == 1


def test_pluralize():
    assert pluralize(1) == "1 utwór"
    assert pluralize(2) == "2 utwory"
    assert pluralize(4) == "4 utwory"
    assert pluralize(5) == "5 utworów"
    assert pluralize(21) == "21 utworów"
    assert pluralize(12) == "12 utworów"
    assert pluralize(14) == "14 utworów"
    assert pluralize(24) == "24 utwory"


def test_cancel_add_returns_to_previous_view(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3")])
    window.library.add_playlist(p1)
    window._show_playlist_view()

    window._enter_add_mode()
    assert window.stack.currentWidget() is window.add_view
    window._cancel_add()

    assert window.stack.currentWidget() is window.playlist_page
    assert window.sidebar.isVisible()


def test_remove_playing_playlist_stops_engine(window, tmp_path, monkeypatch):
    (tmp_path / "a.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3")])
    window.library.add_playlist(p1)

    stopped = []
    monkeypatch.setattr(window.engine, "stop", lambda: stopped.append(1))
    monkeypatch.setattr(
        type(window.engine), "current_source", property(lambda self: str(tmp_path / "a.mp3"))
    )

    window._remove_playlist(0)

    assert stopped
    assert len(window.library) == 0
    assert window._shuffle_queue == []


def test_repeat_off_shuffle_stops_after_all_played(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")
    (tmp_path / "c.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3"), str(tmp_path / "c.mp3")])
    window.library.add_playlist(p1)
    window._set_shuffle(True)
    window._set_repeat("off")

    for i in range(3):
        window._play_at(i)

    window._on_playback_ended()

    assert window._played_this_round == {0, 1, 2}
    assert window.engine.is_playing is False


def test_shuffle_next_refills_after_stale_indices(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")])
    window.library.add_playlist(p1)
    window._shuffle_on = True
    window._shuffle_queue = [5]

    nxt = window._shuffle_next()

    assert 0 <= nxt < len(p1.tracks)


def test_no_resume_without_track(window):
    window._persist_settings()

    saved = json.loads(open(storage.settings_path(), encoding="utf-8").read())
    assert saved.get("resume") is None


def test_track_change_records_resume(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3")])
    window.library.add_playlist(p1)
    window._view_playlist = p1
    p1.current_index = 0

    window._on_track_changed(str(tmp_path / "a.mp3"))

    assert window._resume_source == {
        "path": str(tmp_path / "a.mp3"),
        "playlist": "Rock",
        "library": False,
    }
    saved = json.loads(open(storage.settings_path(), encoding="utf-8").read())
    assert saved["resume"]["path"] == str(tmp_path / "a.mp3")
    assert saved["resume"]["playlist"] == "Rock"
    assert saved["resume"]["library"] is False


def test_restore_sets_playlist_index_and_pauses(window, tmp_path, monkeypatch):
    (tmp_path / "a.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3")])
    window.library.add_playlist(p1)
    window._settings["resume"] = {
        "path": str(tmp_path / "a.mp3"),
        "position_ms": 12345,
        "playlist": "Rock",
        "library": False,
    }

    calls = {}
    monkeypatch.setattr(window.engine, "set_track", lambda p: calls.setdefault("set_track", p))
    monkeypatch.setattr(window.engine, "pause", lambda: calls.setdefault("pause", True))
    monkeypatch.setattr(window.engine, "seek", lambda ms: calls.setdefault("seek", ms))

    window._restore_last_session()
    window.engine.media.mediaStatusChanged.emit(QMediaPlayer.MediaStatus.LoadedMedia)

    assert window._view_playlist is p1
    assert p1.current_index == 0
    assert window.stack.currentWidget() is window.playlist_page
    assert calls.get("set_track") == str(tmp_path / "a.mp3")
    assert calls.get("pause") is True
    assert calls.get("seek") == 12345
    assert window._resume_source["path"] == str(tmp_path / "a.mp3")


def test_restore_skips_missing_file(window, tmp_path, monkeypatch):
    window.library.add_playlist(Playlist("Rock"))
    window._settings["resume"] = {
        "path": str(tmp_path / "nie-istnieje.mp3"),
        "position_ms": 1000,
        "playlist": "Rock",
        "library": False,
    }

    set_track = []
    monkeypatch.setattr(window.engine, "set_track", lambda p: set_track.append(p))

    window._restore_last_session()

    assert not set_track
    assert window.stack.currentWidget() is window.home_view


def test_stop_clears_resume(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    window._resume_source = {"path": str(tmp_path / "a.mp3"), "playlist": None, "library": False}
    window._resume_position_ms = 5000

    window._on_stop_clicked()

    saved = json.loads(open(storage.settings_path(), encoding="utf-8").read())
    assert saved.get("resume") is None


def test_position_changed_ignored_while_restoring(window):
    window._resume_position_ms = 42
    window._restoring_session = True
    window._on_position_changed(0)
    assert window._resume_position_ms == 42
    window._restoring_session = False
    window._on_position_changed(7)
    assert window._resume_position_ms == 7


def test_restore_with_malformed_resume_does_not_crash(window, monkeypatch):
    window._settings["resume"] = {"path": 123, "position_ms": 1000, "playlist": "Rock", "library": False}

    set_track = []
    monkeypatch.setattr(window.engine, "set_track", lambda p: set_track.append(p))

    window._restore_last_session()

    assert not set_track


def test_restore_settings_clamps_repeat(window):
    window._restore_settings({"volume": 50, "shuffle": False, "repeat": "bogus"})
    assert window._repeat_mode == "all"
    window._repeat_mode = "bogus"
    window._cycle_repeat()
    assert window._repeat_mode in ("all", "one", "off")


def test_suppress_persist_prevents_startup_wipe(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    window._resume_source = {"path": str(tmp_path / "a.mp3"), "playlist": "Rock", "library": False}
    window._resume_position_ms = 100

    window._suppress_persist = True
    window._persist_settings()
    assert storage.load_settings().get("resume") is None

    window._suppress_persist = False
    window._persist_settings()
    assert storage.load_settings()["resume"]["position_ms"] == 100


def test_toggle_play_resets_round_after_shuffle_complete(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")
    (tmp_path / "c.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3"), str(tmp_path / "c.mp3")])
    window.library.add_playlist(p1)
    window._view_playlist = p1
    window._set_shuffle(True)
    window._set_repeat("off")

    for i in range(3):
        window._play_at(i)
    window._on_playback_ended()
    assert not window.engine.is_playing
    assert len(window._played_this_round) == 3

    window.toggle_play()

    assert len(window._played_this_round) == 1
    assert window._played_this_round == {p1.current_index}
    assert 0 <= p1.current_index < 3


def test_playback_continues_after_restarted_shuffle_round(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")
    (tmp_path / "c.mp3").write_bytes(b"x")
    p1 = Playlist("Rock")
    p1.add_tracks([str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3"), str(tmp_path / "c.mp3")])
    window.library.add_playlist(p1)
    window._view_playlist = p1
    window._set_shuffle(True)
    window._set_repeat("off")

    for i in range(3):
        window._play_at(i)
    window._on_playback_ended()
    window.toggle_play()

    first = p1.current_index
    window._on_playback_ended()

    assert p1.current_index != first
    assert len(window._played_this_round) == 2


def test_track_started_increments_stats(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    window.stats.create_profile("Test")
    window._on_track_started(str(tmp_path / "a.mp3"))
    assert window.stats.play_counts().get(str(tmp_path / "a.mp3")) == 1


def test_track_started_skipped_while_restoring(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    window.stats.create_profile("Test")
    window._restoring_session = True
    window._on_track_started(str(tmp_path / "a.mp3"))
    assert window.stats.play_counts().get(str(tmp_path / "a.mp3")) is None


def test_track_changed_does_not_increment_stats(window, tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    window.stats.create_profile("Test")
    window._on_track_changed(str(tmp_path / "a.mp3"))
    assert window.stats.play_counts().get(str(tmp_path / "a.mp3")) is None
