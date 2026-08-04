import os

import pytest

from core.files import split_dropped
from core.playlist import Playlist


def test_load_m3u_relative(tmp_path):
    (tmp_path / "song1.mp3").write_bytes(b"x")
    (tmp_path / "song2.mp3").write_bytes(b"x")
    m3u = tmp_path / "list.m3u"
    m3u.write_text(
        "#EXTM3U\n"
        "#EXTINF:123,Artysta - Tytul\n"
        "song1.mp3\n"
        "song2.mp3\n",
        encoding="utf-8",
    )

    pl = Playlist()
    assert pl.load_m3u(str(m3u)) == 2
    assert pl.tracks[0].path == str(tmp_path / "song1.mp3")
    assert pl.tracks[1].title == "song2"


def test_load_m3u_ignores_missing(tmp_path):
    m3u = tmp_path / "list.m3u"
    m3u.write_text("#EXTM3U\nmissing.mp3\n", encoding="utf-8")
    pl = Playlist()
    pl.load_m3u(str(m3u))
    assert len(pl) == 0


def test_load_m3u_utf8_polish(tmp_path):
    (tmp_path / "Żółć.mp3").write_bytes(b"x")
    m3u = tmp_path / "list.m3u"
    m3u.write_text("#EXTM3U\nŻółć.mp3\n", encoding="utf-8")
    pl = Playlist()
    pl.load_m3u(str(m3u))
    assert pl.tracks[0].title == "Żółć"


def test_load_m3u_cp1250(tmp_path):
    (tmp_path / "Łąka.mp3").write_bytes(b"x")
    m3u = tmp_path / "list.m3u"
    m3u.write_bytes("#EXTM3U\nŁąka.mp3\n".encode("cp1250"))
    pl = Playlist()
    pl.load_m3u(str(m3u))
    assert pl.tracks[0].title == "Łąka"


def test_load_m3u_bom(tmp_path):
    (tmp_path / "test.mp3").write_bytes(b"x")
    m3u = tmp_path / "list.m3u"
    m3u.write_bytes(b"\xef\xbb\xbf" + "#EXTM3U\ntest.mp3\n".encode("utf-8"))
    pl = Playlist()
    pl.load_m3u(str(m3u))
    assert len(pl) == 1


def test_playlist_name_from_file(tmp_path):
    (tmp_path / "test.mp3").write_bytes(b"x")
    m3u = tmp_path / "moja_playlista.m3u"
    m3u.write_text("#EXTM3U\ntest.mp3\n", encoding="utf-8")
    pl = Playlist()
    pl.load_m3u(str(m3u))
    assert pl.name == "moja_playlista"


def test_save_and_reload_roundtrip(tmp_path):
    for name in ("a.mp3", "b.mp3"):
        (tmp_path / name).write_bytes(b"x")
    pl = Playlist()
    pl.add_tracks([str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")])
    saved = tmp_path / "out.m3u"
    pl.save_m3u(str(saved))

    loaded = Playlist()
    loaded.load_m3u(str(saved))
    assert [t.path for t in loaded.tracks] == [str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3")]


def test_navigation_wraps(tmp_path):
    pl = Playlist()
    pl.add_tracks([str(tmp_path / f"{i}.mp3") for i in range(3)])
    pl.current_index = 0
    assert pl.next_index() == 1
    pl.current_index = 2
    assert pl.next_index() == 0
    assert pl.prev_index() == 1


def test_remove_track_adjusts_index(tmp_path):
    pl = Playlist()
    pl.add_tracks([str(tmp_path / f"{i}.mp3") for i in range(3)])
    pl.current_index = 2

    removed = pl.remove_track(0)
    assert removed.title == "0"
    assert len(pl) == 2
    assert pl.current_index == 1
    assert pl.tracks[0].title == "1"

    pl.remove_track(pl.current_index)
    assert pl.current_index == -1
    assert pl.remove_track(99) is None


def test_split_dropped(tmp_path):
    audio = tmp_path / "a.mp3"
    playlist = tmp_path / "p.m3u"
    folder = tmp_path / "sub"
    folder.mkdir()
    audio.write_bytes(b"x")
    playlist.write_text("#EXTM3U\n", encoding="utf-8")

    pls, auds, folders = split_dropped([str(audio), str(playlist), str(folder)])
    assert pls == [str(playlist)]
    assert auds == [str(audio)]
    assert folders == [str(folder)]
