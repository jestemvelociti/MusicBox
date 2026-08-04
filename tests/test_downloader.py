import os
import sys
import threading
import time

import pytest

from core.downloader import (
    _duration_s,
    _find_downloaded,
    _run,
    load_playlist_file,
    parse_csv,
    parse_m3u,
    sanitize_name,
    write_m3u,
    write_m3u_copy,
)


def test_sanitize_name_fullwidth():
    assert sanitize_name("a?b") == "a？b"
    assert sanitize_name("a/b") == "a／b"
    assert sanitize_name('a"b') == "a＂b"
    assert sanitize_name("a:b") == "a：b"
    assert sanitize_name("a|b") == "a｜b"
    assert sanitize_name("  a   b  ") == "a b"
    assert sanitize_name(". ") == "_"
    assert sanitize_name("nazwa. ") == "nazwa"


def test_sanitize_name_escapes_windows_reserved():
    assert sanitize_name("CON") == "_CON"
    assert sanitize_name("aux") == "_aux"
    assert sanitize_name("Nul") == "_Nul"
    assert sanitize_name("COM1") == "_COM1"
    assert sanitize_name("lpt9") == "_lpt9"
    assert sanitize_name("CON.m3u") == "_CON.m3u"
    assert sanitize_name("Kon") == "Kon"
    assert sanitize_name("comic") == "comic"


def test_duration_s_parses_hours_minutes_seconds():
    assert _duration_s("1:05:00") == 3900
    assert _duration_s("1:05") == 65
    assert _duration_s("3:45") == 225
    assert _duration_s("1:02:30") == 3750
    assert _duration_s("180000") == 180000
    assert _duration_s(None) == 0
    assert _duration_s("abc") == 0


def test_parse_m3u(tmp_path):
    p = tmp_path / "play.m3u"
    p.write_text(
        "#EXTM3U\n"
        "#EXTPLAYLIST:Moja Playlista\n"
        "#EXTINF:133,Chivas - anyżowe żelki\n"
        "Chivas - anyżowe żelki.mp3\n"
        "#EXTINF:200,Artysta - Utwór\n"
        "Artysta - Utwór.mp3\n",
        encoding="utf-8",
    )
    name, tracks = parse_m3u(str(p))
    assert name == "Moja Playlista"
    assert len(tracks) == 2
    assert tracks[0]["artists"] == "Chivas"
    assert tracks[0]["title"] == "anyżowe żelki"
    assert tracks[0]["duration_ms"] == 133000


def test_parse_csv_spotify(tmp_path):
    p = tmp_path / "export.csv"
    p.write_text(
        "Track Name,Artist Name(s),Album Name,Duration (ms)\n"
        '"Piosenka","Wykonawca","Album X",180000\n',
        encoding="utf-8",
    )
    name, tracks = parse_csv(str(p))
    assert len(tracks) == 1
    assert tracks[0]["title"] == "Piosenka"
    assert tracks[0]["artists"] == "Wykonawca"
    assert tracks[0]["album"] == "Album X"
    assert tracks[0]["duration_ms"] == 180000


def test_load_playlist_file_accepts_both(tmp_path):
    m3u = tmp_path / "a.m3u"
    m3u.write_text("#EXTM3U\n#EXTINF:10,Artysta - Tytul\nArtysta - Tytul.mp3\n", encoding="utf-8")
    name, tracks = load_playlist_file(str(m3u))
    assert name == "a" and len(tracks) == 1

    csv = tmp_path / "b.csv"
    csv.write_text("Track Name,Artist Name\nT,Art\n", encoding="utf-8")
    name, tracks = load_playlist_file(str(csv))
    assert name == "b" and len(tracks) == 1


def test_parse_csv_applies_header_fix_in_memory(tmp_path):
    bad = (
        "Track URI,Track Name,Album Name,Artist Name(s),Release Date,Duration (ms),"
        "Popularity,Explicit,Added By,Added At,Genres,Record Label,Danceability,Energy,Key,"
        "Loudness,Mode,Speechiness,Acousticness,Instrumentalness,Liveness,Valence,Tempo,Time Signature\n"
    )
    row = 'spotify:track:x,"Finesse","Finesse","Waima",2021-12-31,131402,45,true,u,2026-01-01T00:00:00Z,"","LBL",0.7,0.6,1,-8,0,0.1,0.2,0,0.3,0.3,164,4\n'
    p = tmp_path / "bad.csv"
    p.write_text(bad + row, encoding="utf-8")
    before = p.read_bytes()

    name, tracks = parse_csv(str(p))

    assert len(tracks) == 1
    assert tracks[0]["artists"] == "Waima"
    assert tracks[0]["title"] == "Finesse"
    assert tracks[0]["playlist"] == "Finesse"
    assert name == "Finesse"
    assert p.read_bytes() == before


def test_write_m3u_format(tmp_path):
    tracks = [
        {
            "title": "anyżowe żelki",
            "artists": "Chivas",
            "album": "",
            "isrc": "",
            "duration_ms": 133000,
            "file": "x",
        }
    ]
    path = write_m3u(str(tmp_path), "młody say10", tracks, ext="mp3", suffix=".m3u")
    content = open(path, encoding="utf-8").read()
    assert content.startswith("#EXTM3U\n#EXTPLAYLIST:młody say10\n")
    assert "#EXTINF:133,Chivas - anyżowe żelki\n" in content
    assert "Chivas - anyżowe żelki.mp3\n" in content
    assert os.path.join("młody say10") in path


def test_write_m3u_escapes_commas_in_label(tmp_path):
    tracks = [
        {
            "title": "Kiss, Kiss",
            "artists": "Art, Band",
            "album": "",
            "isrc": "",
            "duration_ms": 100000,
            "file": "x",
        }
    ]
    path = write_m3u(str(tmp_path), "Play", tracks, ext="mp3", suffix=".m3u")
    content = open(path, encoding="utf-8").read()
    assert "#EXTINF:100,Art， Band - Kiss， Kiss\n" in content


def test_write_m3u_copy_absolute_paths(tmp_path):
    out = write_m3u_copy(str(tmp_path), "Play", [r"C:\muzyka\a.mp3", r"C:\muzyka\b.mp3"])
    content = open(out, encoding="utf-8").read()
    assert r"C:\muzyka\a.mp3" in content
    assert "#EXTPLAYLIST:Play" in content


def test_write_m3u_copy_does_not_overwrite_existing(tmp_path):
    first = write_m3u_copy(str(tmp_path), "Play", [r"C:\a.mp3"])
    second = write_m3u_copy(str(tmp_path), "Play", [r"C:\b.mp3"])
    assert first != second
    assert os.path.exists(first)
    assert os.path.exists(second)
    assert second.endswith("Play (2).m3u")
    assert "C:\\a.mp3" in open(first, encoding="utf-8").read()
    assert "C:\\b.mp3" in open(second, encoding="utf-8").read()


def test_find_downloaded_matches_prefix_with_brackets(tmp_path):
    (tmp_path / "Levitating [Remix].webm").write_bytes(b"x")
    (tmp_path / "Levitating [Remix].webm.part").write_bytes(b"x")
    (tmp_path / "other.webm").write_bytes(b"x")

    found = _find_downloaded(tmp_path, "Levitating [Remix]")

    assert [p.name for p in found] == ["Levitating [Remix].webm"]


def test_find_downloaded_excludes_part_only(tmp_path):
    (tmp_path / "Utwor - Tytul.webm.part").write_bytes(b"x")
    (tmp_path / "Utwor - Tytul.webm").write_bytes(b"x")
    (tmp_path / "Utwor - Tytul.mp3").write_bytes(b"x")

    found = _find_downloaded(tmp_path, "Utwor - Tytul")

    assert sorted(p.name for p in found) == ["Utwor - Tytul.mp3", "Utwor - Tytul.webm"]


def test_run_stops_on_stop_event():
    stop = threading.Event()

    def setter():
        time.sleep(1)
        stop.set()

    t = threading.Thread(target=setter)
    t.start()
    result = _run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        timeout=60,
        stop_event=stop,
    )
    t.join()
    assert result.returncode != 0
