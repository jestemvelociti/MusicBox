import json
import os
from datetime import date

import pytest

from core.stats import Stats


@pytest.fixture
def stats(tmp_path):
    return Stats(str(tmp_path / "stats.json"))


def test_no_profile_by_default(stats):
    assert not stats.has_profile
    assert stats.profile_name == ""
    assert stats.total_listening_seconds() == 0
    assert stats.play_counts() == {}
    assert stats.artist_counts() == {}


def test_create_profile_and_persist(stats, tmp_path):
    assert stats.create_profile("Jan") is True
    assert stats.has_profile
    assert stats.profile_name == "Jan"
    stats.add_listening(75)
    stats.increment_play(r"C:\a.mp3")
    stats.save()

    reloaded = Stats(str(tmp_path / "stats.json"))
    assert reloaded.profile_name == "Jan"
    assert reloaded.total_listening_seconds() == 75
    assert reloaded.play_counts() == {r"C:\a.mp3": 1}


def test_create_profile_rejects_blank(stats):
    assert stats.create_profile("   ") is False
    assert not stats.has_profile


def test_increment_play_and_top_tracks(stats):
    stats.create_profile("Jan")
    for _ in range(3):
        stats.increment_play(r"C:\a.mp3")
    stats.increment_play(r"C:\b.mp3")
    stats.increment_play(r"C:\b.mp3")
    stats.increment_play(r"C:\c.mp3")

    top = stats.top_tracks(3)
    assert top[0] == (r"C:\a.mp3", 3)
    assert top[1] == (r"C:\b.mp3", 2)
    assert top[2] == (r"C:\c.mp3", 1)


def test_top_tracks_respects_limit(stats):
    stats.create_profile("Jan")
    for i in range(5):
        stats.increment_play(rf"C:\t{i}.mp3")
    assert len(stats.top_tracks(3)) == 3


def test_artist_counts_from_filename_fallback(stats):
    stats.create_profile("Jan")
    stats.increment_play(r"C:\Waima - Finesse.mp3")
    stats.increment_play(r"C:\Waima - Drugi.mp3")
    stats.increment_play(r"C:\Chivas - X.mp3")

    artists = stats.top_artists(3)
    assert artists[0] == ("Waima", 2)
    assert artists[1] == ("Chivas", 1)


def test_artist_unknown_fallback(stats):
    stats.create_profile("Jan")
    stats.increment_play(r"C:\bezartysty.mp3")
    assert stats.artist_counts()["bezartysty"] == 1


def test_no_tracking_without_profile(stats):
    stats.increment_play(r"C:\a.mp3")
    stats.add_listening(10)
    assert stats.play_counts() == {}
    assert stats.total_listening_seconds() == 0


def test_reset(stats):
    stats.create_profile("Jan")
    stats.add_listening(50)
    stats.increment_play(r"C:\Waima - Finesse.mp3")
    assert stats.reset() is True
    assert stats.total_listening_seconds() == 0
    assert stats.play_counts() == {}
    assert stats.artist_counts() == {}
    assert stats.profile_name == "Jan"


def test_rename(stats):
    stats.create_profile("Jan")
    assert stats.rename_profile("Asia") is True
    assert stats.profile_name == "Asia"
    assert stats.rename_profile(" ") is False


def test_export_import(stats, tmp_path):
    stats.create_profile("Jan")
    stats.add_listening(100)
    stats.increment_play(r"C:\Waima - Finesse.mp3")

    out = str(tmp_path / "export.json")
    assert stats.export(out) is True

    other = Stats(str(tmp_path / "other.json"))
    assert other.import_(out) is True
    assert other.profile_name == "Jan"
    assert other.total_listening_seconds() == 100
    assert other.top_artists(1)[0][0] == "Waima"


def test_import_rejects_invalid(stats, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    assert stats.import_(str(bad)) is False
    assert not stats.has_profile


def test_import_sanitizes_bad_shape(stats, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps(
            {
                "profile": {
                    "name": "Jan",
                    "listening_seconds": "abc",
                    "play_counts": {"a": "x", "b": 2},
                    "monthly": {"2026/01": {"listening_seconds": 10}},
                    "year_summaries": [{"year": None}, {"year": 2026, "listening_seconds": 5}],
                }
            }
        ),
        encoding="utf-8",
    )
    assert stats.import_(str(bad)) is True
    assert stats.profile_name == "Jan"
    assert stats.total_listening_seconds() == 0
    assert stats.play_counts() == {"b": 2}
    assert stats.months() == []
    assert [s["year"] for s in stats.year_summaries()] == [2026]


def test_monthly_buckets_recorded(stats):
    stats.create_profile("Jan")
    stats.add_listening(30, today=date(2026, 1, 15))
    stats.add_listening(20, today=date(2026, 2, 1))
    stats.increment_play(r"C:\Waima - A.mp3", today=date(2026, 1, 15))
    stats.increment_play(r"C:\Waima - B.mp3", today=date(2026, 1, 15))

    assert stats.total_listening_seconds() == 50
    assert stats.months() == ["2026-01", "2026-02"]
    jan = stats.month_summary("2026-01")
    assert jan["listening_seconds"] == 30
    assert jan["play_counts"] == {r"C:\Waima - A.mp3": 1, r"C:\Waima - B.mp3": 1}
    assert jan["artist_counts"] == {"Waima": 2}
    assert stats.month_summary("2026-03") is None


def test_no_periods_without_activity(stats):
    stats.create_profile("Jan")
    assert stats.months() == []
    assert stats.year_summaries() == []


def test_year_summary_created_on_dec4(stats):
    stats.create_profile("Jan")
    stats.add_listening(100, today=date(2025, 12, 15))
    stats.add_listening(50, today=date(2026, 1, 10))
    stats.add_listening(25, today=date(2026, 11, 30))
    stats.increment_play(r"C:\Waima - Finesse.mp3", today=date(2026, 2, 5))

    assert stats.maybe_create_year_summary(date(2026, 12, 4)) == [2026]
    summaries = stats.year_summaries()
    assert len(summaries) == 1
    s = summaries[0]
    assert s["year"] == 2026
    assert s["listening_seconds"] == 175
    assert s["play_counts"] == {r"C:\Waima - Finesse.mp3": 1}
    assert s["artist_counts"] == {"Waima": 1}
    assert s["created_on"] == "2026-12-04"

    assert stats.maybe_create_year_summary(date(2026, 12, 4)) == []


def test_year_cycle_boundary_december_belongs_to_next_year(stats):
    stats.create_profile("Jan")
    stats.add_listening(100, today=date(2025, 12, 15))

    assert stats.maybe_create_year_summary(date(2025, 12, 4)) == []
    assert stats.maybe_create_year_summary(date(2026, 12, 4)) == [2026]
    assert stats.year_summaries()[0]["listening_seconds"] == 100


def test_no_summary_before_dec4(stats):
    stats.create_profile("Jan")
    stats.add_listening(60, today=date(2026, 3, 1))
    assert stats.maybe_create_year_summary(date(2026, 11, 30)) == []
    assert stats.year_summaries() == []


def test_catchup_after_missed_trigger_date(stats):
    stats.create_profile("Jan")
    stats.add_listening(40, today=date(2026, 5, 1))
    stats.add_listening(20, today=date(2026, 9, 1))

    assert stats.maybe_create_year_summary(date(2027, 3, 1)) == [2026]
    assert stats.year_summaries()[0]["listening_seconds"] == 60


def test_reset_keeps_year_summaries(stats):
    stats.create_profile("Jan")
    stats.add_listening(50, today=date(2026, 1, 1))
    assert stats.maybe_create_year_summary(date(2026, 12, 4)) == [2026]

    assert stats.reset() is True
    assert stats.total_listening_seconds() == 0
    assert stats.months() == []
    assert len(stats.year_summaries()) == 1


def test_export_import_carries_periods(stats, tmp_path):
    stats.create_profile("Jan")
    stats.add_listening(30, today=date(2026, 1, 15))
    stats.increment_play(r"C:\Waima - Finesse.mp3", today=date(2026, 1, 15))
    stats.maybe_create_year_summary(date(2026, 12, 4))

    out = str(tmp_path / "export.json")
    assert stats.export(out) is True

    other = Stats(str(tmp_path / "other.json"))
    assert other.import_(out) is True
    assert other.months() == ["2026-01"]
    assert other.month_summary("2026-01")["listening_seconds"] == 30
    assert len(other.year_summaries()) == 1
    assert other.year_summaries()[0]["year"] == 2026
