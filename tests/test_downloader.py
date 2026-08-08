import os
import sys
import threading
import time

import pytest

from core.downloader import (
    _build_id3_tags,
    _duration_s,
    _ffmpeg_cmd,
    _find_downloaded,
    _run,
    _track_base,
    augment_album_tracks,
    ensure_album,
    load_playlist_file,
    normalize_download_options,
    parse_csv,
    parse_m3u,
    sanitize_name,
    search_candidates,
    single_artist,
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


def test_run_timeout_kills_proc():
    t0 = time.time()
    result = _run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        timeout=2,
    )
    assert result.returncode != 0
    assert time.time() - t0 < 30


def test_run_drains_pipes_no_deadlock():
    code = (
        "import sys; sys.stderr.write('x'*200000); sys.stderr.flush(); "
        "sys.stdout.write('y'*200000); sys.stdout.flush()"
    )
    t0 = time.time()
    result = _run([sys.executable, "-c", code], timeout=30)
    assert result.returncode == 0
    assert len(result.stdout) == 200000
    assert len(result.stderr) == 200000
    assert time.time() - t0 < 25


def test_search_candidates_empty_when_search_raises():
    class BrokenYT:
        def search(self, *a, **k):
            raise RuntimeError("timeout")

    assert (
        search_candidates(BrokenYT(), {"title": "x", "artists": "", "duration_ms": 0})
        == []
    )


def test_search_candidates_sorts_and_limits():
    class FakeYT:
        def search(self, *a, **k):
            return [
                {"videoId": "id1", "title": "Foo", "artists": [{"name": "Art"}], "duration": "3:00"},
                {"videoId": "id2", "title": "Something Else", "artists": [{"name": "Other"}], "duration": "3:00"},
            ]

    track = {"title": "Foo", "artists": "Art", "duration_ms": 180000}
    cands = search_candidates(FakeYT(), track, n=1)
    assert len(cands) == 1
    assert cands[0]["videoId"] == "id1"


def test_download_track_stops_after_deadline(monkeypatch, tmp_path):
    from core import downloader

    tools = {"yt_dlp": "yt", "ffmpeg": "ff", "deno": "de", "missing": []}

    class FakeYT:
        def search(self, *a, **k):
            return [
                {"videoId": "id%d" % i, "title": "Foo", "artists": [{"name": "Art"}], "duration": "3:00"}
                for i in range(5)
            ]

    calls = {"n": 0}

    def fake_download_one(*a, **k):
        calls["n"] += 1
        time.sleep(0.6)
        return {"ok": False, "error": "slow"}

    monkeypatch.setattr(downloader, "_download_one", fake_download_one)
    result = downloader.download_track(
        FakeYT(),
        {"title": "Foo", "artists": "Art", "duration_ms": 180000},
        str(tmp_path),
        tools,
        track_timeout=1,
    )
    assert result.get("ok") is False
    assert calls["n"] < 5
    assert "Przekroczono czas" in result.get("error", "")


def test_ffmpeg_cmd_includes_bitrate():
    cmd = _ffmpeg_cmd("ffmpeg", "a.webm", "b.mp3", "192k")
    assert "-b:a" in cmd
    assert cmd[cmd.index("-b:a") + 1] == "192k"
    assert "libmp3lame" in cmd


def test_normalize_download_options_defaults_and_validation():
    assert normalize_download_options(None) == {"mp3_bitrate": "320k", "cover_size": 600}
    assert normalize_download_options({}) == {"mp3_bitrate": "320k", "cover_size": 600}
    assert normalize_download_options(
        {"mp3_bitrate": "192k", "cover_size": 300}
    ) == {"mp3_bitrate": "192k", "cover_size": 300}
    assert normalize_download_options(
        {"mp3_bitrate": "banana", "cover_size": -5}
    ) == {"mp3_bitrate": "320k", "cover_size": 600}


def test_download_track_passes_cover_size(monkeypatch, tmp_path):
    from pathlib import Path

    from core import downloader

    tools = {"yt_dlp": "yt", "ffmpeg": "ff", "deno": "de", "missing": []}

    class FakeYT:
        def search(self, *a, **k):
            return [{"videoId": "id1", "title": "Foo", "artists": [{"name": "Art"}], "duration": "3:00"}]

    def fake_run(cmd, **kw):
        if "-o" in cmd:
            out = str(cmd[cmd.index("-o") + 1])
            tmp_dir = Path(out).parent
            tmp_dir.mkdir(parents=True, exist_ok=True)
            (tmp_dir / "Art - Foo.webm").write_bytes(b"raw")

        class R:
            returncode = 0
            stdout = b""
            stderr = b""

        return R()

    monkeypatch.setattr(downloader, "_run", fake_run)
    monkeypatch.setattr(downloader, "_yt_thumbnail_bytes", lambda vid: b"jpeg")
    captured = {}

    def fake_square(data, size=600):
        captured["size"] = size
        return b"sq"

    monkeypatch.setattr(downloader, "_square_cover_bytes", fake_square)
    monkeypatch.setattr(downloader, "_tag_mp3", lambda *a, **k: None)
    monkeypatch.setattr(downloader, "_duration_ms_of_file", lambda p: 100000)

    r = downloader.download_track(
        FakeYT(),
        {"title": "Foo", "artists": "Art", "duration_ms": 180000},
        str(tmp_path),
        tools,
        options={"mp3_bitrate": "192k", "cover_size": 300},
    )
    assert r.get("ok") is True
    assert captured.get("size") == 300


def test_build_id3_tags_track_number_and_genre():
    tags = _build_id3_tags(
        {
            "title": "T",
            "artists": "A",
            "album": "Alb",
            "year": "2024",
            "genre": "Hip-Hop",
            "track_no": 3,
            "disc_no": 1,
            "total_tracks": 12,
        },
        None,
    )
    assert tags.getall("TIT2")[0].text == ["T"]
    assert tags.getall("TPE1")[0].text == ["A"]
    assert tags.getall("TALB")[0].text == ["Alb"]
    assert tags.getall("TCON")[0].text == ["Hip-Hop"]
    assert tags.getall("TRCK")[0].text == ["3/12"]
    assert tags.getall("TPOS")[0].text == ["1"]


def test_build_id3_tags_track_number_without_total():
    tags = _build_id3_tags({"title": "T", "track_no": 2, "disc_no": 0}, None)
    assert tags.getall("TRCK")[0].text == ["2"]
    assert not tags.getall("TPOS")


def test_single_artist():
    assert single_artist("A, B") == "A"
    assert single_artist("A feat. B") == "A"
    assert single_artist("A ft B") == "A"
    assert single_artist("A featuring B") == "A"
    assert single_artist("Far East Movement, The Cataracs, DEV") == "Far East Movement"
    assert single_artist("Simon & Garfunkel") == "Simon & Garfunkel"
    assert single_artist("Earth, Wind & Fire") == "Earth, Wind & Fire"
    assert single_artist("Rick Astley") == "Rick Astley"
    assert single_artist("") == ""


def test_build_id3_tags_writes_single_artist():
    tags = _build_id3_tags({"title": "T", "artists": "A, B"}, None)
    assert tags.getall("TPE1")[0].text == ["A"]


def test_track_base_with_track_number():
    assert _track_base({"artists": "Art", "title": "Foo", "track_no": 3}) == "03 - Art - Foo"
    assert _track_base({"artists": "Art", "title": "Foo", "track_no": 0}) == "Art - Foo"


def test_augment_album_tracks_numbers_and_genre():
    tracks = [{"title": "A", "artists": "X"}, {"title": "B", "artists": "X"}]
    out = augment_album_tracks(tracks, "Rock")
    assert [t["track_no"] for t in out] == [1, 2]
    assert all(t["total_tracks"] == 2 for t in out)
    assert all(t["disc_no"] == 1 for t in out)
    assert all(t["genre"] == "Rock" for t in out)
    assert "track_no" not in tracks[0]


def test_augment_album_tracks_preserves_spotify_numbers():
    tracks = [{"title": "A", "artists": "X", "track_no": 3, "disc_no": 2}]
    out = augment_album_tracks(tracks, "Pop")
    assert out[0]["track_no"] == 3
    assert out[0]["disc_no"] == 2
    assert out[0]["total_tracks"] == 1


def test_ensure_album_fills_only_missing():
    tracks = [
        {"title": "A", "album": "Prawdziwy"},
        {"title": "B", "album": ""},
        {"title": "C", "album": None},
    ]
    out = ensure_album(tracks, "Fallback")
    assert out[0]["album"] == "Prawdziwy"
    assert out[1]["album"] == "Fallback"
    assert out[2]["album"] == "Fallback"
    assert tracks[1]["album"] == ""


def test_ensure_album_empty_fallback_no_change():
    tracks = [{"title": "A", "album": ""}]
    assert ensure_album(tracks, "")[0]["album"] == ""


def test_parse_csv_track_and_disc_numbers(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text(
        "Track Name,Artist Name(s),Track Number,Disc Number\n"
        '"A","X",3,1\n"B","X",4,1\n',
        encoding="utf-8",
    )
    name, tracks = parse_csv(str(p))
    assert tracks[0]["track_no"] == 3
    assert tracks[1]["track_no"] == 4
    assert tracks[0]["disc_no"] == 1


def test_download_track_uses_provided_cover(monkeypatch, tmp_path):
    from pathlib import Path

    from core import downloader

    tools = {"yt_dlp": "yt", "ffmpeg": "ff", "deno": "de", "missing": []}

    class FakeYT:
        def search(self, *a, **k):
            return [{"videoId": "id1", "title": "Foo", "artists": [{"name": "Art"}], "duration": "3:00"}]

    def fake_run(cmd, **kw):
        if "-o" in cmd:
            out = str(cmd[cmd.index("-o") + 1])
            tmp_dir = Path(out).parent
            tmp_dir.mkdir(parents=True, exist_ok=True)
            (tmp_dir / "Art - Foo.webm").write_bytes(b"raw")

        class R:
            returncode = 0
            stdout = b""
            stderr = b""

        return R()

    monkeypatch.setattr(downloader, "_run", fake_run)
    monkeypatch.setattr(
        downloader,
        "_yt_thumbnail_bytes",
        lambda vid: (_ for _ in ()).throw(AssertionError("nie wołać")),
    )
    captured = {}

    def fake_square(data, size=600):
        captured["data"] = data
        captured["size"] = size
        return b"sq"

    monkeypatch.setattr(downloader, "_square_cover_bytes", fake_square)
    monkeypatch.setattr(downloader, "_tag_mp3", lambda *a, **k: None)
    monkeypatch.setattr(downloader, "_duration_ms_of_file", lambda p: 100000)

    r = downloader.download_track(
        FakeYT(),
        {"title": "Foo", "artists": "Art", "duration_ms": 180000},
        str(tmp_path),
        tools,
        options={"mp3_bitrate": "192k", "cover_size": 300},
        cover_bytes=b"jpegdata",
    )
    assert r.get("ok") is True
    assert captured.get("data") == b"jpegdata"
    assert captured.get("size") == 300
