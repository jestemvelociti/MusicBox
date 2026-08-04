from mutagen.id3 import ID3, TIT2, TPE1

from core.tags import display_name, read_tags


def make_mp3(path, title=None, artist=None):
    frame = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)
    with open(path, "wb") as f:
        for _ in range(4):
            f.write(frame)
    if title or artist:
        tags = ID3()
        if title:
            tags.add(TIT2(encoding=3, text=title))
        if artist:
            tags.add(TPE1(encoding=3, text=artist))
        tags.save(path)


def test_read_tags_artist_title(tmp_path):
    song = tmp_path / "song.mp3"
    make_mp3(song, title="Kiedyś", artist="Mój Zespół")
    tags = read_tags(str(song))
    assert tags["title"] == "Kiedyś"
    assert tags["artist"] == "Mój Zespół"


def test_read_tags_missing(tmp_path):
    song = tmp_path / "song.mp3"
    make_mp3(song)
    assert read_tags(str(song)) is None


def test_display_name_with_tags(tmp_path):
    song = tmp_path / "song.mp3"
    make_mp3(song, title="Kiedyś", artist="Mój Zespół")
    assert display_name(str(song), "song") == "Mój Zespół – Kiedyś"


def test_display_name_fallback(tmp_path):
    song = tmp_path / "song.mp3"
    make_mp3(song)
    assert display_name(str(song), "song") == "song"
