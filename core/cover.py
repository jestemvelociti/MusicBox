from functools import lru_cache

from mutagen import File


@lru_cache(maxsize=64)
def extract_cover(path):
    try:
        audio = File(path)
    except Exception:
        return None
    if audio is None:
        return None
    tags = getattr(audio, "tags", None)
    if tags is None:
        return None

    for key in tags.keys():
        if key.startswith("APIC"):
            pic = tags[key]
            if isinstance(pic, list):
                for p in pic:
                    if getattr(p, "data", None):
                        return p.data
            elif getattr(pic, "data", None):
                return pic.data

    for pic in getattr(tags, "pictures", []) or []:
        if getattr(pic, "data", None):
            return pic.data

    return None


def first_cover(paths):
    for path in paths:
        data = extract_cover(path)
        if data:
            return data
    return None
