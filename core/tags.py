import os
from functools import lru_cache

from mutagen import File


@lru_cache(maxsize=1024)
def read_tags(path):
    try:
        audio = File(path, easy=True)
    except Exception:
        return None
    if audio is None or getattr(audio, "tags", None) is None:
        return None

    def first(*keys):
        for key in keys:
            value = audio.tags.get(key)
            if isinstance(value, (list, tuple)) and value:
                return str(value[0])
            if value:
                return str(value)
        return None

    return {
        "title": first("title", "Title", "tit2", "TIT2"),
        "artist": first("artist", "Artist", "tpe1", "TPE1"),
    }


def display_title(path, fallback):
    tags = read_tags(path)
    if tags and tags.get("title"):
        return tags["title"]
    return fallback


def display_artist(path, fallback="Nieznany"):
    tags = read_tags(path)
    if tags and tags.get("artist"):
        return tags["artist"]
    stem = os.path.splitext(os.path.basename(path))[0]
    artist, _, _ = stem.partition(" - ")
    artist = artist.strip()
    return artist or fallback


def combine_name(title, artist, fallback):
    if artist and title and title != fallback:
        return f"{artist} – {title}"
    if title:
        return title
    if artist:
        return f"{artist} – {fallback}"
    return fallback


def display_name(path, fallback):
    return combine_name(display_title(path, fallback), display_artist(path, fallback), fallback)
