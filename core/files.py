import os

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma"}
PLAYLIST_EXTENSIONS = {".m3u", ".m3u8"}


def is_audio_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS


def is_playlist_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in PLAYLIST_EXTENSIONS


def collect_audio_files(directory: str) -> list:
    audio = []
    for root, _, files in os.walk(directory):
        for name in sorted(files):
            full = os.path.join(root, name)
            if is_audio_file(full):
                audio.append(full)
    return audio


def split_dropped(paths):
    playlists = []
    audio = []
    folders = []
    for p in paths:
        if os.path.isdir(p):
            folders.append(p)
        elif is_playlist_file(p):
            playlists.append(p)
        elif is_audio_file(p):
            audio.append(p)
    return playlists, audio, folders
