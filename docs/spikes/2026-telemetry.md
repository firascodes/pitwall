# Spike: 2026 telemetry (Phase 0)

Date: 2026-10-15. Script: `backend/scripts/spike_2026_telemetry.py`.
Sample: R17 Singapore Grand Prix qualifying, Hamilton's fastest lap (lap 21, 1:31.496, soft tyres).

## Findings

| Question | Result |
|---|---|
| Season so far | 23 rounds in the calendar, 17 completed, 6 sprint weekends |
| Grid size | **22 drivers** (11 teams). Do not hard-code 20. |
| Q1/Q2/Q3 split | Works: `laps.split_qualifying_sessions()` gave 190 / 111 / 62 laps |
| Lap fields | Lap and sector times, `Compound`, `TyreLife`, `FreshTyre`, `Stint`, `IsPersonalBest`, `Deleted` + `DeletedReason` (track limits), `IsAccurate`, speed traps |
| Car data | `Speed`, `RPM`, `nGear`, `Throttle`, `Brake`, `DRS`. Median sample gap **240 ms**, p95 **440 ms** |
| `DRS` channel | **Always 0.** DRS is gone in 2026. The feed has **no active-aero channel**. |
| Position data | `X`, `Y`, `Z`, `Status`. Median gap 240 ms, p95 420 ms. Units are 1/10 m (the lap spans approx. 1.4 km × 0.9 km). |
| Merged telemetry | `get_telemetry()` adds `Distance`, `RelativeDistance`, `DriverAhead`, `DistanceToDriverAhead`. Lap distance 4,904 m, top speed 306 km/h. |
| Circuit corners | 19 corners with `Number`, `Letter`, `Angle`, `X`, `Y` and **`Distance`** |
| Session load time | Approx. 13 s for a full qualifying session, the first time (cached after) |
| Jolpica | 374 race-result rows for 2026 = 17 races × 22 drivers. Complete. |
| OpenF1 | 131 sessions listed, **including future ones**. Team radio works for past sessions: 12 clips in Singapore Q, with `recording_url`. |

## What this changes in the design

1. **No DRS or aero in the replay HUD.** The DRS channel is empty and active aero is not in the feed. The HUD shows speed, gear, throttle, brake and RPM only. The UI must not claim aero data that does not exist.
2. **Interpolation is required.** At 306 km/h a car moves approx. 20 m between median samples and approx. 37 m at p95. Resample to a 5 m distance step in the backend. Interpolate between steps in the frontend.
3. **Corner analysis can use distance windows.** Each corner has a `Distance`, so "time lost in Turn 7" is the delta change across a window around that distance.
4. **Lap node properties.** Add `deleted`, `deleted_reason` and `is_accurate`. Deleted laps (track limits) must not count as a best lap. Inaccurate laps must not go into a replay.
5. **Grid size from data.** 22 drivers changes Q1/Q2/Q3 elimination counts. Read the counts from the data and never hard-code them.
6. **Cold start.** Lazy load of a session costs approx. 13 s (qualifying; races will be longer). This confirms the hot-set plus lazy loading decision and the "fetching from timing feed" loader.
7. **OpenF1 lists future sessions.** Always filter by `date_start < now`. (The first spike run picked a future session and got HTTP 404.)

## Still open in Phase 0

- Race and sprint sessions: load time and size (expected to be larger than qualifying).
- Jev latency and cost (needs a TypeSafe API key).
