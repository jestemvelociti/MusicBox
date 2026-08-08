import os

from .playlist import Playlist


class Library:
    def __init__(self):
        self.playlists = []
        self.current_index = -1

    def __len__(self):
        return len(self.playlists)

    def current(self):
        if 0 <= self.current_index < len(self.playlists):
            return self.playlists[self.current_index]
        return None

    def add_playlist(self, playlist):
        name = playlist.name
        for i, existing in enumerate(self.playlists):
            if existing.name == name:
                del self.playlists[i]
                break
        self.playlists.append(playlist)
        self.current_index = len(self.playlists) - 1
        return self.current_index

    def add_playlist_from_files(self, paths, name=None):
        if not paths:
            return None
        if name is None:
            parent = os.path.basename(os.path.dirname(os.path.abspath(paths[0])))
            name = parent or "Moja playlista"
        playlist = Playlist(name)
        playlist.add_tracks(paths)
        return self.add_playlist(playlist)

    def load_m3u(self, path):
        playlist = Playlist()
        if playlist.load_m3u(path) > 0:
            return self.add_playlist(playlist)
        return None

    def switch_to(self, index):
        if 0 <= index < len(self.playlists):
            self.current_index = index
            return self.current()
        return None

    def remove(self, index):
        if 0 <= index < len(self.playlists):
            del self.playlists[index]
            if self.current_index > index:
                self.current_index -= 1
            elif self.current_index == index:
                self.current_index = min(index, len(self.playlists) - 1)
