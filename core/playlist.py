import os
from dataclasses import dataclass


@dataclass
class Track:
    path: str
    title: str


def _decode_m3u(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp1250", "cp1252"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1", errors="replace")


class Playlist:
    def __init__(self, name="Playlista"):
        self.name = name
        self.tracks = []
        self.current_index = -1

    def __len__(self):
        return len(self.tracks)

    def clear(self):
        self.tracks = []
        self.current_index = -1

    def add_tracks(self, paths):
        for path in paths:
            title = os.path.splitext(os.path.basename(path))[0]
            self.tracks.append(Track(path=path, title=title))

    def remove_track(self, index):
        if not (0 <= index < len(self.tracks)):
            return None
        removed = self.tracks[index]
        self.tracks.pop(index)
        if self.current_index == index:
            self.current_index = -1
        elif self.current_index > index:
            self.current_index -= 1
        return removed

    def current(self):
        if 0 <= self.current_index < len(self.tracks):
            return self.tracks[self.current_index]
        return None

    def next_index(self):
        if not self.tracks:
            return -1
        if self.current_index < 0:
            return 0
        return (self.current_index + 1) % len(self.tracks)

    def prev_index(self):
        if not self.tracks:
            return -1
        if self.current_index < 0:
            return len(self.tracks) - 1
        return (self.current_index - 1) % len(self.tracks)

    def load_m3u(self, path):
        self.tracks = []
        self.name = os.path.splitext(os.path.basename(path))[0]
        base = os.path.dirname(os.path.abspath(path))
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError:
            self.current_index = -1
            return 0
        text = _decode_m3u(raw)
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not os.path.isabs(line):
                line = os.path.join(base, line)
            line = os.path.normpath(line)
            if os.path.isfile(line):
                title = os.path.splitext(os.path.basename(line))[0]
                self.tracks.append(Track(path=line, title=title))
        self.current_index = 0 if self.tracks else -1
        return len(self.tracks)

    def save_m3u(self, path, absolute=False):
        lines = ["#EXTM3U"]
        base = os.path.dirname(os.path.abspath(path))
        for track in self.tracks:
            lines.append("#EXTINF:0," + track.title)
            if absolute:
                lines.append(track.path.replace("\\", "/"))
                continue
            try:
                rel = os.path.relpath(track.path, base)
            except ValueError:
                rel = track.path
            lines.append(rel.replace("\\", "/"))
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except OSError:
            return False
        return True
