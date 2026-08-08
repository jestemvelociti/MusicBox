import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from core import storage
from ui.download_view import DownloadView


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def view(app, tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    v = DownloadView()
    v.resize(900, 600)
    v.show()
    yield v
    v.close()


def _csv(tmp_path, name, header, rows):
    p = tmp_path / name
    p.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return str(p)


def test_load_csv_without_album_autofills_and_enables(view, tmp_path):
    csv = _csv(
        tmp_path, "bez_albumu.csv",
        "Track Name,Artist Name(s)",
        ['"Piosenka","Wykonawca"'],
    )
    assert view.load_csv(csv) is True
    assert view.album_edit.text() == "bez_albumu"
    assert view.download_btn.isEnabled() is True


def test_load_csv_with_album_keeps_field_and_enables(view, tmp_path):
    csv = _csv(
        tmp_path, "z_albumem.csv",
        "Track Name,Artist Name(s),Album Name",
        ['"Piosenka","Wykonawca","Album Real"'],
    )
    assert view.load_csv(csv) is True
    assert view.album_edit.text() == ""
    assert view.download_btn.isEnabled() is True
    assert view._album_from_csv is True


def test_clearing_autofilled_album_blocks_button(view, tmp_path):
    csv = _csv(
        tmp_path, "bez_albumu.csv",
        "Track Name,Artist Name(s)",
        ['"Piosenka","Wykonawca"'],
    )
    view.load_csv(csv)
    assert view.download_btn.isEnabled() is True
    view.album_edit.setText("")
    assert view.download_btn.isEnabled() is False


def test_source_is_remembered(app, tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.set_spotify_credentials("cid123", "sec456")
    v1 = DownloadView()
    idx = v1.source_combo.findData("spotify")
    v1.source_combo.setCurrentIndex(idx)
    app.processEvents()
    assert storage.get_download_settings()["source"] == "spotify"
    v1.close()

    v2 = DownloadView()
    v2.show()
    app.processEvents()
    assert v2.source_combo.currentData() == "spotify"
    assert v2.spotify_cid.text() == "cid123"
    assert v2.spotify_secret.text() == "sec456"
    v2.close()


def test_persist_does_not_wipe_creds_with_empty_fields(app, tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    storage.set_spotify_credentials("cid123", "sec456")
    v = DownloadView()
    v.spotify_cid.setText("")
    v.spotify_secret.setText("")
    app.processEvents()
    assert storage.get_spotify_credentials() == {"client_id": "cid123", "client_secret": "sec456"}
    v.close()
