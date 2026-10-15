"""Phase 0 spike: what does 2026 telemetry look like?

Run: uv run python scripts/spike_2026_telemetry.py [DRIVER_CODE]
Prints a report; findings go into docs/spikes/2026-telemetry.md.
"""

import sys
from datetime import UTC, datetime

import fastf1
import httpx
import pandas as pd

from pitwall.config import get_settings

DRIVER = sys.argv[1] if len(sys.argv) > 1 else "HAM"
settings = get_settings()


def header(title: str) -> None:
    print(f"\n## {title}")


def sample_interval_ms(df: pd.DataFrame) -> str:
    gaps = df["SessionTime"].diff().dt.total_seconds().dropna() * 1000
    return f"median {gaps.median():.0f} ms, p95 {gaps.quantile(0.95):.0f} ms, n={len(df)}"


settings.fastf1_cache_dir.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(settings.fastf1_cache_dir))
fastf1.set_log_level("WARNING")

header(f"{settings.season} schedule")
schedule = fastf1.get_event_schedule(settings.season, include_testing=False)
now = datetime.now(UTC)
done = schedule[pd.to_datetime(schedule["Session5DateUtc"], utc=True) < now]
print(f"rounds in calendar: {len(schedule)}, completed: {len(done)}")
print(f"sprint weekends so far: {(done['EventFormat'].str.contains('sprint')).sum()}")
event = done.iloc[-1]
print(f"latest completed: R{event['RoundNumber']} {event['EventName']} ({event['EventFormat']})")

header("Qualifying session load")
session = fastf1.get_session(settings.season, int(event["RoundNumber"]), "Q")
session.load(laps=True, telemetry=True, weather=False, messages=False)
laps = session.laps
print(f"laps: {len(laps)}, drivers: {laps['Driver'].nunique()}")
print(f"lap columns: {list(laps.columns)}")
q1, q2, q3 = laps.split_qualifying_sessions()
print(f"Q1/Q2/Q3 laps: {len(q1)}/{len(q2)}/{len(q3) if q3 is not None else 'n/a'}")
print(f"compounds seen: {sorted(laps['Compound'].dropna().unique())}")

header(f"Telemetry for {DRIVER}'s fastest Q lap")
driver_laps = laps.pick_drivers(DRIVER)
if driver_laps.empty:
    DRIVER = session.results.iloc[0]["Abbreviation"]
    print(f"no laps for that driver, using pole sitter {DRIVER}")
    driver_laps = laps.pick_drivers(DRIVER)
lap = driver_laps.pick_fastest()
print(f"lap {int(lap['LapNumber'])}: {lap['LapTime']}, compound {lap['Compound']}")

car = lap.get_car_data()
print(f"car_data columns: {list(car.columns)}")
print(f"car_data sampling: {sample_interval_ms(car)}")
if "DRS" in car.columns:
    print(f"DRS values seen: {sorted(car['DRS'].dropna().unique().tolist())}")

pos = lap.get_pos_data()
print(f"pos_data columns: {list(pos.columns)}")
print(f"pos_data sampling: {sample_interval_ms(pos)}")
print(f"x range: {pos['X'].min():.0f}..{pos['X'].max():.0f}")
print(f"y range: {pos['Y'].min():.0f}..{pos['Y'].max():.0f}")

tel = lap.get_telemetry()
print(f"merged telemetry columns: {list(tel.columns)}")
print(f"distance covered: {tel['Distance'].max():.0f} m, top speed {tel['Speed'].max():.0f} km/h")

corners = session.get_circuit_info().corners
print(f"circuit corners: {len(corners)}, columns: {list(corners.columns)}")

header("Other sources")
with httpx.Client(timeout=20) as client:
    r = client.get(f"https://api.jolpi.ca/ergast/f1/{settings.season}/results/?limit=1")
    total = r.json()["MRData"]["total"] if r.is_success else f"HTTP {r.status_code}"
    print(f"Jolpica {settings.season} race result rows: {total}")

    r = client.get("https://api.openf1.org/v1/sessions", params={"year": settings.season})
    sessions = r.json() if r.is_success else []
    print(f"OpenF1 {settings.season} sessions: {len(sessions)}")
    # OpenF1 also lists future sessions, so only consider ones that have started
    past_q = [
        s
        for s in sessions
        if s.get("session_name") == "Qualifying" and datetime.fromisoformat(s["date_start"]) < now
    ]
    if past_q:
        q = past_q[-1]
        radio_url = "https://api.openf1.org/v1/team_radio"
        r = client.get(radio_url, params={"session_key": q["session_key"]})
        clips = r.json() if r.is_success else []
        print(f"OpenF1 latest past qualifying: {q['location']} (session {q['session_key']})")
        print(f"OpenF1 team radio: HTTP {r.status_code}, {len(clips)} clips")
        if clips:
            print(f"team radio fields: {list(clips[0].keys())}")
