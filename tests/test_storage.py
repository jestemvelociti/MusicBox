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


def test_prune_missing_removes_playlists_without_file(tmp_path):
    external = tmp_path / "MusicBox"
    external.mkdir()
    (external / "zostaje.m3u").write_text("#EXTM3U\n", encoding="utf-8")

    stay = _playlist(tmp_path, "zostaje", ["a.mp3"])
    gone = _playlist(tmp_path, "skasowany", ["a.mp3"])
    kept, removed = storage.prune_missing([stay, gone], str(external))
    assert kept == [stay]
    assert removed == ["skasowany"]


def test_prune_missing_keeps_everything_without_external_dir(tmp_path):
    pl = _playlist(tmp_path, "jakas", ["a.mp3"])
    kept, removed = storage.prune_missing([pl], None)
    assert kept == [pl]
    assert removed == []


def test_delete_source_file_removes_file(tmp_path):
    external = tmp_path / "MusicBox"
    external.mkdir()
    (external / "fajna.m3u").write_text("#EXTM3U\n", encoding="utf-8")
    assert storage.delete_source_file("fajna", str(external)) is True
    assert not (external / "fajna.m3u").exists()


def test_delete_source_file_matches_other_names(tmp_path):
    external = tmp_path / "MusicBox"
    external.mkdir()
    (external / "inna.m3u").write_text("#EXTM3U\n", encoding="utf-8")
    assert storage.delete_source_file("brak", str(external)) is False
    assert (external / "inna.m3u").exists()


def test_delete_source_file_without_external_dir(tmp_path):
    assert storage.delete_source_file("x", None) is False


def test_last_dir_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    assert storage.get_last_dir("csv") is None
    storage.set_last_dir("csv", str(tmp_path))
    assert storage.get_last_dir("csv") == str(tmp_path)


def test_last_dir_ignores_missing_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.set_last_dir("csv", str(tmp_path))
    assert storage.get_last_dir("csv", "/brak") == str(tmp_path)
    storage.set_last_dir("csv", str(tmp_path / "nie_istnieje"))
    assert storage.get_last_dir("csv", "/brak") == str(tmp_path)


def test_load_settings_non_dict_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.ensure()
    with open(storage.settings_path(), "w", encoding="utf-8") as f:
        f.write("[1, 2, 3]")
    assert storage.load_settings() == {}


def test_download_settings_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    assert storage.get_download_settings() == {
        "mp3_bitrate": "320k",
        "cover_size": 600,
        "mode": "playlist",
        "genre": "",
        "source": "csv",
    }


def test_download_settings_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.set_download_settings(
        {"mp3_bitrate": "192k", "cover_size": 300, "mode": "album", "genre": "Hip-Hop", "source": "spotify"}
    )
    assert storage.get_download_settings() == {
        "mp3_bitrate": "192k",
        "cover_size": 300,
        "mode": "album",
        "genre": "Hip-Hop",
        "source": "spotify",
    }


def test_download_settings_invalid_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.set_download_settings(
        {"mp3_bitrate": "9999k", "cover_size": 42, "mode": "xyz", "genre": 5, "source": "foo"}
    )
    assert storage.get_download_settings() == {
        "mp3_bitrate": "320k",
        "cover_size": 600,
        "mode": "playlist",
        "genre": "",
        "source": "csv",
    }


def test_spotify_credentials_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    assert storage.get_spotify_credentials() == {"client_id": "", "client_secret": ""}
    storage.set_spotify_credentials("  cid  ", "secret")
    assert storage.get_spotify_credentials() == {"client_id": "cid", "client_secret": "secret"}


def test_spotify_credentials_survive_other_settings_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.set_spotify_credentials("cid", "sec")
    storage.set_download_settings({"mp3_bitrate": "192k", "mode": "album", "genre": "Rock", "source": "spotify"})
    storage.set_last_dir("csv", str(tmp_path))
    assert storage.get_spotify_credentials() == {"client_id": "cid", "client_secret": "sec"}


def test_spotify_credentials_fallback_legacy_key(tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.ensure()
    settings = storage.load_settings()
    settings["spotify"] = {"client_id": "oldcid", "client_secret": "oldsec"}
    storage.save_settings(settings)
    assert storage.get_spotify_credentials() == {"client_id": "oldcid", "client_secret": "oldsec"}
