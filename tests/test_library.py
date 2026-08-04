import os

import pytest

from core.library import Library
from core.playlist import Playlist


def make_m3u(tmp_path, name, entries, encoding="utf-8"):
    path = tmp_path / name
    content = "#EXTM3U\n" + "\n".join(entries) + "\n"
    if encoding == "utf-8-sig":
        path.write_bytes(b"\xef\xbb\xbf" + content.encode("utf-8"))
    else:
        path.write_bytes(content.encode(encoding))
    return str(path)


def test_load_m3u_as_new_playlist(tmp_path):
    (tmp_path / "song.mp3").write_bytes(b"x")
    m3u = make_m3u(tmp_path, "moja.m3u", ["song.mp3"])

    lib = Library()
    index = lib.load_m3u(m3u)
    assert index == 0
    assert len(lib) == 1
    assert lib.current().name == "moja"
    assert len(lib.current()) == 1


def test_multiple_playlists_and_switch(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    (tmp_path / "b.mp3").write_bytes(b"x")
    lib = Library()
    lib.load_m3u(make_m3u(tmp_path, "pierwsza.m3u", ["a.mp3"]))
    lib.load_m3u(make_m3u(tmp_path, "druga.m3u", ["b.mp3"]))
    assert len(lib) == 2
    assert lib.current_index == 1

    switched = lib.switch_to(0)
    assert switched.name == "pierwsza"
    assert lib.current_index == 0


def test_remove_playlist(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    lib = Library()
    lib.load_m3u(make_m3u(tmp_path, "p.m3u", ["a.mp3"]))
    lib.remove(0)
    assert len(lib) == 0
    assert lib.current() is None


def test_add_audio_to_current(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    lib = Library()
    lib.add_playlist_from_files([str(tmp_path / "a.mp3")])
    assert len(lib.current()) == 1


def test_add_playlist_replaces_same_name(tmp_path):
    (tmp_path / "a.mp3").write_bytes(b"x")
    lib = Library()
    first = Playlist("Rock")
    first.add_tracks([str(tmp_path / "a.mp3")])
    lib.add_playlist(first)
    second = Playlist("Rock")
    second.add_tracks([str(tmp_path / "a.mp3")])
    lib.add_playlist(second)
    assert len(lib) == 1
    assert lib.current() is second
