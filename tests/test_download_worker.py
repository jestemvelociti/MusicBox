import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from ui.download_worker import DownloadWorker


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_worker_cleans_tmp_after_run(app, tmp_path, monkeypatch):
    monkeypatch.setenv("MUSICPLAYER_DATA_DIR", str(tmp_path / "data"))
    from core import storage

    storage.ensure()

    def fake_resolve_tools():
        return {"yt_dlp": "yt", "ffmpeg": "ff", "deno": "de", "missing": []}

    monkeypatch.setattr("ui.download_worker.resolve_tools", fake_resolve_tools)
    monkeypatch.setattr("ui.download_worker._tool_version", lambda t: "v")

    class FakeYTMusic:
        def __init__(self, *a, **k):
            pass

    monkeypatch.setattr("ui.download_worker.YTMusic", FakeYTMusic)

    def fake_download_track(ytmusic, track, dest_dir, tools, options=None,
                            stop_event=None, track_timeout=300, cover_bytes=None):
        p = os.path.join(dest_dir, "ok.mp3")
        with open(p, "w") as f:
            f.write("x")
        tr = dict(track)
        tr["file"] = p
        return {"ok": True, "file": p, "track": tr, "video_id": "x"}

    monkeypatch.setattr("ui.download_worker.download_track", fake_download_track)

    out_root = os.path.join(str(tmp_path), "Test")
    os.makedirs(os.path.join(out_root, ".tmp", "vid123"), exist_ok=True)

    worker = DownloadWorker(
        dest_dir=str(tmp_path),
        options={"mode": "playlist", "genre": "", "album": ""},
        parent=app,
        tracks=[{"title": "T", "artists": "A", "duration_ms": 100000}],
        playlist_name="Test",
    )
    worker.run()

    assert os.path.exists(os.path.join(out_root, "Test.m3u"))
    assert not os.path.exists(os.path.join(out_root, ".tmp"))
