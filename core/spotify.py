import json
import re
import ssl
import urllib.parse
import urllib.request

TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"


class SpotifyError(Exception):
    pass


def _ssl_context():
    """Kontekst SSL z CA bundle z certifi (działa w PyInstaller exe)."""
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _http_json(url, data=None, headers=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def spotify_token(client_id, client_secret, timeout=20):
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
    ).encode("utf-8")
    data = _http_json(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    token = data.get("access_token")
    if not token:
        raise SpotifyError("Nie udało się pobrać tokena Spotify (sprawdź Client ID/Secret)")
    return token


def parse_spotify_url(url):
    """Zwraca (typ, id) dla linku Spotify (track/album/playlist) albo None."""
    url = (url or "").strip()
    m = re.search(r"spotify:(track|album|playlist):([A-Za-z0-9]{22})", url)
    if m:
        return m.group(1), m.group(2)
    m = re.search(
        r"open\.spotify\.com/(?:intl-[a-z]{2}/)?(?:embed/)?(track|album|playlist)/([A-Za-z0-9]{22})",
        url,
    )
    if m:
        return m.group(1), m.group(2)
    return None


def _artist_names(artists):
    return ", ".join(a.get("name", "") for a in (artists or []) if isinstance(a, dict))


def _track_from_api(item):
    return {
        "title": item.get("name") or "",
        "artists": _artist_names(item.get("artists")),
        "album": "",
        "playlist": "",
        "isrc": "",
        "sp_id": item.get("uri") or "",
        "duration_ms": int(item.get("duration_ms") or 0),
        "year": "",
        "cover_url": "",
        "track_no": int(item.get("track_number") or 0),
        "disc_no": int(item.get("disc_number") or 0),
    }


def _resolve_track(token, spot_id, timeout):
    t = _http_json("%s/tracks/%s" % (API_URL, spot_id),
                   headers={"Authorization": "Bearer " + token}, timeout=timeout)
    track = _track_from_api(t)
    album = t.get("album") or {}
    track["album"] = album.get("name") or ""
    track["year"] = (album.get("release_date") or "")[:4]
    return (track["title"] or "Utwór", [track])


def _resolve_album(token, spot_id, timeout):
    a = _http_json("%s/albums/%s" % (API_URL, spot_id),
                   headers={"Authorization": "Bearer " + token}, timeout=timeout)
    album_name = a.get("name") or ""
    year = (a.get("release_date") or "")[:4]
    total = int((a.get("tracks") or {}).get("total") or 0)
    tracks = []
    offset = 0
    while True:
        data = a if offset == 0 else _http_json(
            "%s/albums/%s/tracks?limit=50&offset=%d" % (API_URL, spot_id, offset),
            headers={"Authorization": "Bearer " + token}, timeout=timeout,
        )
        for it in (data.get("tracks") or {}).get("items", []):
            tr = _track_from_api(it)
            tr["album"] = album_name or tr["album"]
            tr["year"] = year or tr["year"]
            tracks.append(tr)
        offset += 50
        if offset >= max(total, len(tracks)) or not (data.get("tracks") or {}).get("items"):
            break
    return (album_name or "Album", tracks)


def _resolve_playlist_embed(spot_id, timeout):
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "Chrome/126.0 Safari/537.36")
    url = "https://open.spotify.com/embed/playlist/%s" % spot_id
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        raise SpotifyError("Nie udało się odczytać playlisty (embed)")
    data = json.loads(m.group(1))
    entity = (data.get("props") or {}).get("pageProps", {}).get("state", {}) \
        .get("data", {}).get("entity", {})
    name = entity.get("name") or ""
    tl = entity.get("trackList") or []
    items = tl if isinstance(tl, list) else (tl or {}).get("items") or []
    tracks = []
    for it in items:
        title = it.get("title") or ""
        if not title:
            continue
        try:
            dur_ms = int(it.get("duration") or 0)
        except (TypeError, ValueError):
            dur_ms = 0
        tracks.append(
            {
                "title": title,
                "artists": it.get("subtitle") or "",
                "album": "",
                "playlist": name,
                "isrc": "",
                "sp_id": it.get("uri") or "",
                "duration_ms": dur_ms,
                "year": "",
                "cover_url": "",
                "track_no": 0,
                "disc_no": 0,
            }
        )
    if not tracks:
        raise SpotifyError("Playlista nie zawiera utworów (może być prywatna)")
    return (name or "Playlista", tracks)


def resolve_spotify_link(client_id, client_secret, url, timeout=20):
    """Zwraca (nazwa, [Track]) dla linku Spotify — utwór, album albo playlista."""
    parsed = parse_spotify_url(url)
    if not parsed:
        raise SpotifyError("To nie wygląda na link Spotify (utwór/album/playlista)")
    kind, spot_id = parsed
    if kind == "playlist":
        return _resolve_playlist_embed(spot_id, timeout=timeout)
    token = spotify_token(client_id, client_secret, timeout=timeout)
    if kind == "track":
        return _resolve_track(token, spot_id, timeout)
    return _resolve_album(token, spot_id, timeout)
