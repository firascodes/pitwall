from datetime import UTC, datetime

import pytest

from pitwall.ingest.laps_pipeline import match_openf1_session

SESSIONS = [
    {"session_key": 11276, "session_name": "Qualifying", "date_start": "2026-05-02T20:00:00+00:00"},
    {"session_key": 11275, "session_name": "Sprint", "date_start": "2026-05-02T16:00:00+00:00"},
    {"session_key": 11280, "session_name": "Race", "date_start": "2026-05-03T17:00:00+00:00"},
    {"session_key": 11291, "session_name": "Race", "date_start": "2026-05-24T20:00:00+00:00"},
]


def test_matches_the_nearest_session_even_when_start_times_disagree() -> None:
    # Miami 2026: Jolpica says 20:00 UTC, OpenF1 says 17:00 UTC.
    jolpica_start = datetime(2026, 5, 3, 20, tzinfo=UTC)
    assert match_openf1_session(SESSIONS, "R", jolpica_start) == 11280


def test_never_matches_a_session_from_another_weekend() -> None:
    with pytest.raises(LookupError):
        match_openf1_session(SESSIONS, "R", datetime(2026, 5, 10, 20, tzinfo=UTC))
