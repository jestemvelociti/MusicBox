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
        playlist.save_m3u(path, absolute=True)
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
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def settings_path():
    return os.path.join(get_data_dir(), "settings.json")


def stats_path():
    return os.path.join(get_data_dir(), "stats.json")


def save_settings(settings):
    ensure()
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def load_settings():
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
