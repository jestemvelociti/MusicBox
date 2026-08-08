import json
import os
import re
from datetime import date as _date

_STATS_VERSION = 1

_MONTH_KEY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _int_dict(value):
    if not isinstance(value, dict):
        return {}
    out = {}
    for key, count in value.items():
        count = _to_int(count)
        if count > 0:
            out[str(key)] = count
    return out


def _clean_monthly(value):
    if not isinstance(value, dict):
        return {}
    out = {}
    for key, bucket in value.items():
        if not isinstance(key, str) or not _MONTH_KEY_RE.match(key):
            continue
        if not isinstance(bucket, dict):
            continue
        out[key] = {
            "listening_seconds": _to_int(bucket.get("listening_seconds")),
            "play_counts": _int_dict(bucket.get("play_counts")),
            "artist_counts": _int_dict(bucket.get("artist_counts")),
        }
    return out


def _clean_year_summaries(value):
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        year = _to_int(item.get("year"), default=None)
        if year is None:
            continue
        clean = {
            "year": year,
            "listening_seconds": _to_int(item.get("listening_seconds")),
            "play_counts": _int_dict(item.get("play_counts")),
            "artist_counts": _int_dict(item.get("artist_counts")),
        }
        if item.get("created_on"):
            clean["created_on"] = str(item["created_on"])
        out.append(clean)
    return out


def _clean_import_profile(profile):
    return {
        "name": str(profile.get("name", "")).strip(),
        "listening_seconds": _to_int(profile.get("listening_seconds")),
        "play_counts": _int_dict(profile.get("play_counts")),
        "artist_counts": _int_dict(profile.get("artist_counts")),
        "monthly": _clean_monthly(profile.get("monthly")),
        "year_summaries": _clean_year_summaries(profile.get("year_summaries")),
    }


def format_listening(seconds):
    try:
        total = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        total = 0
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h} godz. {m} min"
    if m:
        return f"{m} min"
    return f"{s} sek"


def _artist_of(path):
    from core.tags import read_tags

    tags = read_tags(path)
    artist = None
    if tags:
        artist = tags.get("artist")
    if artist:
        return artist
    stem = os.path.splitext(os.path.basename(path))[0]
    artist, _, _ = stem.partition(" - ")
    return artist.strip() or "Nieznany"


class Stats:
    def __init__(self, path):
        self.path = path
        self._data = {"profile": None}
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        profile = data.get("profile")
        if isinstance(profile, dict):
            self._data["profile"] = _clean_import_profile(profile)

    def save(self):
        tmp = self.path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except OSError:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass

    @property
    def has_profile(self):
        return self._data.get("profile") is not None

    @property
    def profile_name(self):
        profile = self._data.get("profile")
        return profile.get("name") if profile else ""

    def create_profile(self, name):
        name = (name or "").strip()
        if not name:
            return False
        self._data["profile"] = {
            "name": name,
            "listening_seconds": 0,
            "play_counts": {},
            "artist_counts": {},
            "monthly": {},
            "year_summaries": [],
        }
        self.save()
        return True

    def rename_profile(self, name):
        name = (name or "").strip()
        if not name or not self.has_profile:
            return False
        self._data["profile"]["name"] = name
        self.save()
        return True

    def reset(self):
        if not self.has_profile:
            return False
        profile = self._data["profile"]
        profile["listening_seconds"] = 0
        profile["play_counts"] = {}
        profile["artist_counts"] = {}
        profile["monthly"] = {}
        self.save()
        return True

    @staticmethod
    def _month_key(today):
        return f"{today.year:04d}-{today.month:02d}"

    def add_listening(self, seconds, today=None):
        if not self.has_profile:
            return
        today = today or _date.today()
        profile = self._data["profile"]
        seconds = max(0, int(seconds))
        profile["listening_seconds"] = profile.get("listening_seconds", 0) + seconds
        bucket = profile.setdefault("monthly", {}).setdefault(self._month_key(today), {})
        bucket["listening_seconds"] = bucket.get("listening_seconds", 0) + seconds

    def increment_play(self, path, today=None):
        if not self.has_profile:
            return
        today = today or _date.today()
        profile = self._data["profile"]
        counts = profile.setdefault("play_counts", {})
        counts[path] = counts.get(path, 0) + 1
        acounts = profile.setdefault("artist_counts", {})
        artist = _artist_of(path)
        acounts[artist] = acounts.get(artist, 0) + 1
        bucket = profile.setdefault("monthly", {}).setdefault(self._month_key(today), {})
        bcounts = bucket.setdefault("play_counts", {})
        bcounts[path] = bcounts.get(path, 0) + 1
        bacounts = bucket.setdefault("artist_counts", {})
        bacounts[artist] = bacounts.get(artist, 0) + 1

    def play_counts(self):
        if not self.has_profile:
            return {}
        return dict(self._data["profile"].get("play_counts") or {})

    def artist_counts(self):
        if not self.has_profile:
            return {}
        return dict(self._data["profile"].get("artist_counts") or {})

    def total_listening_seconds(self):
        if not self.has_profile:
            return 0
        return int(self._data["profile"].get("listening_seconds", 0))

    def top_tracks(self, n):
        return self._top(self.play_counts(), n)

    def top_artists(self, n):
        return self._top(self.artist_counts(), n)

    @staticmethod
    def _top(counts, n):
        items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
        return items[:n]

    def months(self):
        if not self.has_profile:
            return []
        monthly = self._data["profile"].get("monthly") or {}
        return sorted(monthly)

    def month_summary(self, key):
        if not self.has_profile:
            return None
        bucket = (self._data["profile"].get("monthly") or {}).get(key)
        if not bucket:
            return None
        return {
            "listening_seconds": int(bucket.get("listening_seconds", 0)),
            "play_counts": dict(bucket.get("play_counts") or {}),
            "artist_counts": dict(bucket.get("artist_counts") or {}),
        }

    def year_summaries(self):
        if not self.has_profile:
            return []
        summaries = self._data["profile"].get("year_summaries") or []
        return sorted(summaries, key=lambda s: s.get("year", 0), reverse=True)

    def _build_year_summary(self, year):
        monthly = self._data["profile"].get("monthly") or {}
        start_key = f"{year - 1:04d}-12"
        end_key = f"{year:04d}-11"
        listening = 0
        play_counts = {}
        artist_counts = {}
        for key in sorted(monthly):
            if not start_key <= key <= end_key:
                continue
            bucket = monthly[key]
            listening += int(bucket.get("listening_seconds", 0))
            for path, count in (bucket.get("play_counts") or {}).items():
                play_counts[path] = play_counts.get(path, 0) + count
            for artist, count in (bucket.get("artist_counts") or {}).items():
                artist_counts[artist] = artist_counts.get(artist, 0) + count
        if listening == 0 and not play_counts and not artist_counts:
            return None
        return {
            "year": year,
            "listening_seconds": listening,
            "play_counts": play_counts,
            "artist_counts": artist_counts,
        }

    def maybe_create_year_summary(self, today=None):
        if not self.has_profile:
            return []
        today = today or _date.today()
        monthly = self._data["profile"].get("monthly") or {}
        if not monthly:
            return []
        summaries = self._data["profile"].setdefault("year_summaries", [])
        existing = {s.get("year") for s in summaries}
        years = [
            _to_int(key[:4])
            for key in monthly
            if isinstance(key, str) and _MONTH_KEY_RE.match(key)
        ]
        if not years:
            return []
        min_year = min(years)
        created = []
        for year in range(min_year, today.year + 1):
            if year == today.year:
                # Biezacy rok: podsumowanie na biezaco (rok-w-dotychczas),
                # odbudowywane przy kazdym odswiezeniu, by odzwierciedlac nowe odsluchy.
                summary = self._build_year_summary(year)
                if summary is None:
                    continue
                summary["created_on"] = today.isoformat()
                summaries[:] = [s for s in summaries if s.get("year") != year]
                summaries.append(summary)
                created.append(year)
            else:
                if year in existing:
                    continue
                summary = self._build_year_summary(year)
                if summary is None:
                    continue
                summary["created_on"] = today.isoformat()
                summaries.append(summary)
                created.append(year)
        if created:
            self.save()
        return created

    def export(self, path):
        if not self.has_profile:
            return False
        payload = {
            "app": "musicbox",
            "version": _STATS_VERSION,
            "profile": self._data["profile"],
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def import_(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        profile = payload.get("profile") if isinstance(payload, dict) else None
        if not isinstance(profile, dict) or not str(profile.get("name") or "").strip():
            return False
        self._data["profile"] = _clean_import_profile(profile)
        self.save()
        return True
