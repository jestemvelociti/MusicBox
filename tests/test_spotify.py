import json

import pytest

from core import spotify


def test_parse_spotify_url_variants():
    i22 = "1a2b3c4d5e6f7g8h9i0j1k"
    assert spotify.parse_spotify_url(
        "https://open.spotify.com/track/%s?si=abc" % i22
    ) == ("track", i22)
    assert spotify.parse_spotify_url(
        "spotify:album:%s" % i22
    ) == ("album", i22)
    assert spotify.parse_spotify_url(
        "https://open.spotify.com/playlist/%s" % i22
    ) == ("playlist", i22)
    assert spotify.parse_spotify_url(
        "https://open.spotify.com/intl-pl/album/%s" % i22
    ) == ("album", i22)
    assert spotify.parse_spotify_url(
        "https://open.spotify.com/embed/playlist/%s" % i22
    ) == ("playlist", i22)
    assert spotify.parse_spotify_url("https://example.com/foo") is None
    assert spotify.parse_spotify_url("") is None


def test_spotify_token_error_when_no_token(monkeypatch):
    monkeypatch.setattr(spotify, "_http_json", lambda *a, **k: {})
    with pytest.raises(spotify.SpotifyError):
        spotify.spotify_token("id", "sec")


def test_resolve_track(monkeypatch):
    def fake_http_json(url, **kw):
        assert "tracks/" in url
        return {
            "name": "Foo",
            "artists": [{"name": "Art"}],
            "duration_ms": 180000,
            "uri": "spotify:track:xxx",
            "track_number": 1,
            "disc_number": 1,
            "album": {"name": "Alb", "release_date": "2024-03-01"},
        }

    monkeypatch.setattr(spotify, "spotify_token", lambda *a, **k: "tok")
    monkeypatch.setattr(spotify, "_http_json", fake_http_json)
    name, tracks = spotify.resolve_spotify_link(
        "id", "sec", "https://open.spotify.com/track/1111111111111111111111"
    )
    assert name == "Foo"
    assert tracks[0]["title"] == "Foo"
    assert tracks[0]["artists"] == "Art"
    assert tracks[0]["album"] == "Alb"
    assert tracks[0]["track_no"] == 1
    assert tracks[0]["year"] == "2024"
    assert tracks[0]["duration_ms"] == 180000


def test_resolve_album(monkeypatch):
    album_resp = {
        "name": "Alb",
        "release_date": "2024-01-01",
        "total_tracks": 2,
        "tracks": {
            "total": 2,
            "items": [
                {"name": "A1", "artists": [{"name": "Art"}], "duration_ms": 100000,
                 "uri": "spotify:track:a1", "track_number": 1, "disc_number": 1},
                {"name": "A2", "artists": [{"name": "Art"}], "duration_ms": 200000,
                 "uri": "spotify:track:a2", "track_number": 2, "disc_number": 1},
            ],
        },
    }

    monkeypatch.setattr(spotify, "spotify_token", lambda *a, **k: "tok")
    monkeypatch.setattr(spotify, "_http_json", lambda *a, **k: album_resp)
    name, tracks = spotify.resolve_spotify_link(
        "id", "sec", "https://open.spotify.com/album/1111111111111111111111"
    )
    assert name == "Alb"
    assert len(tracks) == 2
    assert tracks[0]["track_no"] == 1 and tracks[0]["album"] == "Alb"
    assert tracks[0]["year"] == "2024"
    assert tracks[1]["track_no"] == 2


def test_resolve_playlist_embed(monkeypatch):
    html = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(
            {
                "props": {
                    "pageProps": {
                        "state": {
                            "data": {
                                "entity": {
                                    "name": "Play",
                                    "trackList": [
                                        {"title": "T1", "subtitle": "A1",
                                         "uri": "spotify:track:t1", "duration": 100000},
                                        {"title": "T2", "subtitle": "A2",
                                         "uri": "spotify:track:t2", "duration": 200000},
                                    ],
                                }
                            }
                        }
                    }
                }
            }
        )
        + '</script></html>'
    )

    class FakeResp:
        def read(self):
            return html.encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

    def fake_urlopen(req, timeout=20, context=None):
        return FakeResp()

    monkeypatch.setattr(spotify.urllib.request, "urlopen", fake_urlopen)
    name, tracks = spotify.resolve_spotify_link(
        "id", "sec", "https://open.spotify.com/playlist/1111111111111111111111"
    )
    assert name == "Play"
    assert len(tracks) == 2
    assert tracks[0]["title"] == "T1" and tracks[0]["artists"] == "A1"
    assert tracks[0]["duration_ms"] == 100000


def test_http_json_uses_ssl_context(monkeypatch):
    ctx = object()

    def fake_create_default_context(**kw):
        assert kw.get("cafile"), "brak cafile (certifi)"
        return ctx

    monkeypatch.setattr(spotify.ssl, "create_default_context", fake_create_default_context)

    captured = {}

    class FakeResp:
        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

    def fake_urlopen(req, timeout=20, context=None):
        captured["context"] = context
        return FakeResp()

    monkeypatch.setattr(spotify.urllib.request, "urlopen", fake_urlopen)
    spotify._http_json("https://example.com")
    assert captured["context"] is ctx
