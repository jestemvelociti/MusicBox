import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core.summary_image import CARD_H, CARD_W, render_summary_card, save_summary_card


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


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


def test_card_has_story_dimensions(app):
    pixmap = render_summary_card("Demo", "Grudzień 2025", SAMPLE_SUMMARY)
    assert not pixmap.isNull()
    assert pixmap.width() == CARD_W == 1080
    assert pixmap.height() == CARD_H == 1920


def test_save_writes_png(app, tmp_path):
    out = str(tmp_path / "karta.png")
    assert save_summary_card("Demo", "Rok 2026", SAMPLE_SUMMARY, out) is True
    assert os.path.isfile(out)
    assert os.path.getsize(out) > 0


def test_render_without_covers_and_empty_counts(app):
    summary = {"listening_seconds": 0, "play_counts": {}, "artist_counts": {}}
    pixmap = render_summary_card("Demo", "Styczeń 2026", summary)
    assert not pixmap.isNull()
    assert pixmap.width() == CARD_W


def test_render_year_summary(app):
    summary = dict(SAMPLE_SUMMARY)
    pixmap = render_summary_card("Demo", "Rok 2026", summary)
    assert not pixmap.isNull()
