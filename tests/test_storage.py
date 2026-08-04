import os

from core import storage
from core.playlist import Playlist


def _playlist(tmp_path, name, files):
    pl = Playlist(name)
    pl.add_tracks([str(tmp_path / f) for f in files])
    return pl


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")

    pl = _playlist(tmp_path, "Moja playlista", ["a.mp3", "b.mp3"])
    saved = storage.save_playlist(pl)
    assert os.path.isfile(saved)
    assert os.path.basename(saved) == "Moja playlista.m3u"

    loaded = storage.load_saved_playlists()
    assert len(loaded) == 1
    assert loaded[0].name == "Moja playlista"
    assert [t.path for t in loaded[0].tracks] == [str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")]


def test_save_uses_absolute_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "a.mp3").write_bytes(b"x")
    pl = _playlist(tmp_path, "Test", ["a.mp3"])
    saved = storage.save_playlist(pl)
    content = open(saved, encoding="utf-8").read()
    expected = os.path.abspath(str(tmp_path / "a.mp3")).replace("\\", "/")
    assert expected in content


def test_delete_playlist(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "a.mp3").write_bytes(b"x")
    pl = _playlist(tmp_path, "Do usuniecia", ["a.mp3"])
    storage.save_playlist(pl)
    assert storage.delete_playlist("Do usuniecia") is True
    assert storage.load_saved_playlists() == []
    assert storage.delete_playlist("Do usuniecia") is False


def test_sanitize_name(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "a.mp3").write_bytes(b"x")
    pl = _playlist(tmp_path, "zła/\\nazwa:*?\"<>|", ["a.mp3"])
    storage.save_playlist(pl)
    names = os.listdir(storage.playlists_dir())
    assert len(names) == 1
    assert "/" not in names[0] and "\\" not in names[0]


def test_data_dir_per_platform(monkeypatch):
    monkeypatch.delenv("MUSICPLAYER_DATA_DIR", raising=False)
    monkeypatch.setenv("HOME", "/home/test")
    monkeypatch.setenv("APPDATA", "C:\\AppData")
    monkeypatch.setenv("XDG_DATA_HOME", "/xdg")

    monkeypatch.setattr(storage.sys, "platform", "win32")
    assert "C:\\AppData" in storage.get_data_dir()
    monkeypatch.setattr(storage.sys, "platform", "linux")
    assert storage.get_data_dir() == os.path.join("/xdg", "MusicBox")
    monkeypatch.delenv("XDG_DATA_HOME")
    assert storage.get_data_dir() == os.path.join(os.path.expanduser("~"), ".local", "share", "MusicBox")
    monkeypatch.setattr(storage.sys, "platform", "darwin")
    assert storage.get_data_dir() == os.path.join(
        os.path.expanduser("~"), "Library", "Application Support", "MusicBox"
    )


def test_empty_playlist_not_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.ensure()
    open(os.path.join(storage.playlists_dir(), "pusta.m3u"), "w", encoding="utf-8").write("#EXTM3U\n")
    assert storage.load_saved_playlists() == []
