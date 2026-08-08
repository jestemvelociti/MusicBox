import os

import pytest

from core.summary_pillow import (
    CARD_H,
    CARD_W,
    render_summary_card,
    save_summary_card,
)

SAMPLE_SUMMARY = {
    "listening_seconds": 120000,
    "play_counts": {
        r"C:\Muzyka\Demo\Vexa - Miasto.mp3": 12,
        r"C:\Muzyka\Demo\Zefir - Horyzont.mp3": 9,
        r"C:\Muzyka\Demo\Vexa - Szum.mp3": 7,
        r"C:\Muzyka\Demo\Kometa - Świt.mp3": 5,
    },
    "artist_counts": {"Vexa": 19, "Zefir": 14, "Kometa": 5},
}


def test_card_has_story_dimensions():
    image = render_summary_card("Demo", "Grudzień 2025", SAMPLE_SUMMARY)
    assert image.size == (CARD_W, CARD_H) == (1080, 1920)


def test_save_writes_png(tmp_path):
    out = str(tmp_path / "karta.png")
    assert save_summary_card("Demo", "Rok 2026", SAMPLE_SUMMARY, out) is True
    assert os.path.isfile(out)
    assert os.path.getsize(out) > 0
    assert out.lower().endswith(".png")


def test_render_without_covers_and_empty_counts():
    summary = {"listening_seconds": 0, "play_counts": {}, "artist_counts": {}}
    image = render_summary_card("Demo", "Styczeń 2026", summary)
    assert image.size == (CARD_W, CARD_H)


def test_render_year_summary():
    summary = dict(SAMPLE_SUMMARY)
    image = render_summary_card("Demo", "Rok 2026", summary)
    assert image.size == (CARD_W, CARD_H)


def test_top3_sorted_desc():
    from core.summary_pillow import _top

    counts = {"b": 3, "a": 5, "c": 1, "d": 5}
    top = _top(counts, 3)
    assert [p for p, _ in top] == ["a", "d", "b"]
    top_all = _top(counts, 10)
    assert len(top_all) == 4


def test_polish_diacritics_render():
    image = render_summary_card(
        "Szymon",
        "Sierpień 2026",
        {"listening_seconds": 3600, "play_counts": {}, "artist_counts": {}},
    )
    assert image.size == (CARD_W, CARD_H)


def test_cover_dir_ignored_when_missing():
    summary = dict(SAMPLE_SUMMARY)
    image = render_summary_card("Demo", "Rok 2026", summary, cover_dir=r"C:\nie_istnieje")
    assert image.size == (CARD_W, CARD_H)


def test_save_bad_path_returns_false(tmp_path):
    assert save_summary_card("Demo", "Rok 2026", SAMPLE_SUMMARY, str(tmp_path / "no" / "dir" / "karta.png")) is False
