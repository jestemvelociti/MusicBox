from mutagen.id3 import APIC, ID3, TIT2

from core.cover import extract_cover, first_cover


def _frame():
    return bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(413)


def make_mp3_with_cover(path):
    with open(path, "wb") as f:
        for _ in range(4):
            f.write(_frame())

    tags = ID3()
    tags.add(TIT2(encoding=3, text="Tytuł"))
    tags.add(
        APIC(
            encoding=3,
            mime="image/png",
            type=3,
            desc="cover",
            data=b"\x89PNG\r\n\x1a\nfakedata",
        )
    )
    tags.save(path)


def test_extract_cover(tmp_path):
    song = tmp_path / "song.mp3"
    make_mp3_with_cover(song)
    data = extract_cover(str(song))
    assert data == b"\x89PNG\r\n\x1a\nfakedata"


def test_extract_cover_missing(tmp_path):
    song = tmp_path / "song.mp3"
    song.write_bytes(_frame() * 4)
    assert extract_cover(str(song)) is None


def test_first_cover_picks_first_with_art(tmp_path):
    plain = tmp_path / "plain.mp3"
    plain.write_bytes(_frame() * 4)
    with_cover = tmp_path / "cover.mp3"
    make_mp3_with_cover(with_cover)

    data = first_cover([str(plain), str(with_cover)])
    assert data == b"\x89PNG\r\n\x1a\nfakedata"
