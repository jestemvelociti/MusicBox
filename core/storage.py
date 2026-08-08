import json
import os
import re
import sys

from .playlist import Playlist

APP_DIR_NAME = "MusicBox"


def _android_app_dir():
    try:
        from android.storage import app_storage_path
        return app_storage_path()
    except Exception:
        return None


def get_data_dir():
    override = os.environ.get("MUSICPLAYER_DATA_DIR")
    if override:
        return override
    android_dir = _android_app_dir()
    if android_dir:
        return os.path.join(android_dir, APP_DIR_NAME)
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return os.path.join(base, APP_DIR_NAME)
    if sys.platform == "darwin":
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", APP_DIR_NAME)
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_DIR_NAME)


def playlists_dir():
    return os.path.join(get_data_dir(), "playlists")


def ensure():
    path = playlists_dir()
    os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        _set_hidden(get_data_dir())
    return path


def _set_hidden(path):
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(path)
        if attrs != -1 and not (attrs & 2):
            ctypes.windll.kernel32.SetFileAttributesW(path, attrs | 2)
    except Exception:
        pass


_WIN_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _sanitize(name):
    clean = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    if not clean:
        return "playlista"
    base = clean.split(".")[0].strip().upper()
    if base in _WIN_RESERVED_NAMES:
        return "_" + clean
    return clean


def _path_for(name):
    return os.path.join(playlists_dir(), _sanitize(name) + ".m3u")


def save_playlist(playlist):
    try:
        ensure()
        path = _path_for(playlist.name)
        if not playlist.save_m3u(path, absolute=True):
            return None
    except OSError:
        return None
    return path


def load_saved_playlists():
    ensure()
    result = []
    if not os.path.isdir(playlists_dir()):
        return result
    for name in sorted(os.listdir(playlists_dir())):
        if not name.lower().endswith(".m3u"):
            continue
        full = os.path.join(playlists_dir(), name)
        playlist = Playlist()
        try:
            if playlist.load_m3u(full) > 0:
                result.append(playlist)
        except OSError:
            continue
    return result


def delete_playlist(name):
    path = _path_for(name)
    if not os.path.isfile(path):
        return False
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def delete_source_file(name, external_dir):
    """Usuwa plik <nazwa>.m3u z widocznego folderu MusicBox/.

    Dopasowuje po nazwie bazowej pliku (nie po sanitize), bo pliki tam
    moga miec dowolne nazwy nadane przy imporcie. Zwraca True gdy usunieto.
    """
    if not external_dir or not os.path.isdir(external_dir):
        return False
    for fn in os.listdir(external_dir):
        if fn.lower().endswith(".m3u") and os.path.splitext(fn)[0] == name:
            try:
                os.remove(os.path.join(external_dir, fn))
                return True
            except OSError:
                return False
    return False


def prune_missing(playlists, external_dir):
    """Usuwa playlisty, ktorych plik zrodlowy zniknal z folderu MusicBox/.

    Gdy external_dir jest podany (wersja z widocznym folderem MusicBox/),
    jest on jedynym prawdziwym zrodlem playlist — playlisty bez pliku
    <nazwa>.m3u tam zostaja oznaczone do usuniecia. Gdy external_dir jest
    None (brak 'Wszystkich plikow'), wewnetrzne kopie to jedyne zrodlo
    i nic nie jest usuwane.

    Zwraca (kept, removed_names).
    """
    if not external_dir or not os.path.isdir(external_dir):
        return list(playlists), []
    names = {
        os.path.splitext(n)[0]
        for n in os.listdir(external_dir)
        if n.lower().endswith(".m3u")
    }
    kept = []
    removed = []
    for p in playlists:
        if p.name in names:
            kept.append(p)
        else:
            removed.append(p.name)
    return kept, removed


def settings_path():
    return os.path.join(get_data_dir(), "settings.json")


def stats_path():
    return os.path.join(get_data_dir(), "stats.json")


def save_settings(settings):
    ensure()
    tmp = settings_path() + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        os.replace(tmp, settings_path())
    except OSError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def load_settings():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_last_dir(key, default=None):
    """Ostatnio uzyty katalog dla danego dialogu plikowego.

    Zwraca istniejacy katalog albo default. Nigdy nie zwraca katalogu,
    ktory zniknal (np. odmontowany dysk USB).
    """
    settings = load_settings()
    last = (settings.get("last_dirs") or {}).get(key)
    if last and isinstance(last, str) and os.path.isdir(last):
        return last
    return default


def set_last_dir(key, path):
    """Zapamiętuje katalog wybrany w danym dialogu plikowym."""
    if not path or not os.path.isdir(path):
        return
    settings = load_settings()
    dirs = settings.get("last_dirs")
    if not isinstance(dirs, dict):
        dirs = {}
    dirs[key] = path
    settings["last_dirs"] = dirs
    save_settings(settings)


_DL_BITRATES = ("128k", "192k", "320k")
_DL_COVER_SIZES = (300, 600)
_DL_MODES = ("playlist", "album")
_DL_SOURCES = ("csv", "spotify")
_DL_DEFAULT = {
    "mp3_bitrate": "320k",
    "cover_size": 600,
    "mode": "playlist",
    "genre": "",
    "source": "csv",
}


def get_download_settings():
    """Ustawienia pobierania (jakość mp3, rozmiar okładki, tryb, gatunek, źródło)."""
    settings = load_settings()
    d = settings.get("download")
    if not isinstance(d, dict):
        d = {}
    bit = d.get("mp3_bitrate")
    if bit not in _DL_BITRATES:
        bit = _DL_DEFAULT["mp3_bitrate"]
    size = d.get("cover_size")
    if size not in _DL_COVER_SIZES:
        size = _DL_DEFAULT["cover_size"]
    mode = d.get("mode")
    if mode not in _DL_MODES:
        mode = _DL_DEFAULT["mode"]
    genre = d.get("genre")
    if not isinstance(genre, str):
        genre = ""
    source = d.get("source")
    if source not in _DL_SOURCES:
        source = _DL_DEFAULT["source"]
    return {
        "mp3_bitrate": bit,
        "cover_size": size,
        "mode": mode,
        "genre": genre,
        "source": source,
    }


def set_download_settings(values):
    """Zapisuje ustawienia pobierania do settings.json (z walidacją)."""
    settings = load_settings()
    d = settings.get("download")
    if not isinstance(d, dict):
        d = {}
    values = values or {}
    bit = values.get("mp3_bitrate")
    if bit in _DL_BITRATES:
        d["mp3_bitrate"] = bit
    size = values.get("cover_size")
    if size in _DL_COVER_SIZES:
        d["cover_size"] = size
    mode = values.get("mode")
    if mode in _DL_MODES:
        d["mode"] = mode
    genre = values.get("genre")
    if isinstance(genre, str):
        d["genre"] = genre
    source = values.get("source")
    if source in _DL_SOURCES:
        d["source"] = source
    settings["download"] = d
    save_settings(settings)


def get_spotify_credentials():
    """Kredencjały Spotify (Client ID/Secret) z osobnego pliku
    `spotify_credentials.json` (fallback: stary klucz w settings.json)."""
    path = spotify_credentials_path()
    data = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    if not isinstance(data, dict):
        data = {}
    cid = data.get("client_id")
    sec = data.get("client_secret")
    if not isinstance(cid, str) or not cid:
        legacy = load_settings().get("spotify")
        if isinstance(legacy, dict):
            cid = legacy.get("client_id")
            sec = legacy.get("client_secret")
    return {
        "client_id": cid if isinstance(cid, str) else "",
        "client_secret": sec if isinstance(sec, str) else "",
    }


def set_spotify_credentials(client_id, client_secret):
    """Zapisuje kredencjały Spotify do osobnego pliku (odporne na zapisy
    `settings.json` — np. nadpisywanie przez biegnącą instancję apki)."""
    ensure()
    data = {}
    if isinstance(client_id, str):
        data["client_id"] = client_id.strip()
    if isinstance(client_secret, str):
        data["client_secret"] = client_secret.strip()
    path = spotify_credentials_path()
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except OSError:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def spotify_credentials_path():
    return os.path.join(get_data_dir(), "spotify_credentials.json")
