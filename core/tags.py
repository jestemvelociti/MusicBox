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


def display_name(path, fallback):
    tags = read_tags(path)
    if not tags:
        return fallback
    title = tags.get("title")
    artist = tags.get("artist")
    if title and artist:
        return f"{artist} – {title}"
    if title:
        return title
    if artist:
        return f"{artist} – {fallback}"
    return fallback
