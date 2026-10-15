"""Turn Jolpica's nested, all-string JSON into flat, typed rows for the graph."""

from typing import Any

from pydantic import BaseModel

# Jolpica endpoint -> session type stored in the graph
SESSION_TYPES = {"qualifying": "Q", "sprint": "S", "results": "R"}

# Schedule key -> session type (practice and sprint qualifying are out of scope)
SCHEDULE_SESSIONS = {"Qualifying": "Q", "Sprint": "S"}


def race_id(season: int, rnd: int) -> str:
    return f"{season}-{rnd:02d}"


def session_id(race: str, session_type: str) -> str:
    return f"{race}-{session_type}"


def parse_lap_time_ms(value: str | None) -> int | None:
    """'1:19.507' -> 79507. Empty or missing times -> None."""
    if not value:
        return None
    minutes, _, seconds = value.rpartition(":")
    return round((int(minutes or 0) * 60 + float(seconds)) * 1000)


def _int(value: str | None) -> int | None:
    return int(value) if value not in (None, "") else None


def _iso(date: str, time: str | None) -> str:
    return f"{date}T{time or '00:00:00Z'}"


class SessionRow(BaseModel):
    session_id: str
    type: str
    starts_at: str


class RaceRow(BaseModel):
    race_id: str
    season: int
    round: int
    name: str
    date: str
    url: str | None
    circuit_id: str
    circuit_name: str
    locality: str
    country: str
    lat: float
    lng: float
    sessions: list[SessionRow]


class DriverRow(BaseModel):
    driver_id: str
    code: str | None
    name: str
    nationality: str | None
    dob: str | None
    number: int | None


class ConstructorRow(BaseModel):
    constructor_id: str
    name: str
    nationality: str | None


class ResultProps(BaseModel):
    """Properties stored on the Result node."""

    session_type: str
    position: int | None
    position_text: str | None
    classified: bool
    grid: int | None = None
    points: float | None = None
    status: str | None = None
    laps: int | None = None
    q1_ms: int | None = None
    q2_ms: int | None = None
    q3_ms: int | None = None


class ResultRow(BaseModel):
    result_id: str
    session_id: str
    driver: DriverRow
    constructor: ConstructorRow
    props: ResultProps


def race_rows(races: list[dict[str, Any]]) -> list[RaceRow]:
    rows = []
    for race in races:
        rid = race_id(int(race["season"]), int(race["round"]))
        sessions = [
            SessionRow(
                session_id=session_id(rid, "R"),
                type="R",
                starts_at=_iso(race["date"], race.get("time")),
            )
        ]
        for key, session_type in SCHEDULE_SESSIONS.items():
            if key in race:
                start = _iso(race[key]["date"], race[key].get("time"))
                sessions.append(
                    SessionRow(
                        session_id=session_id(rid, session_type), type=session_type, starts_at=start
                    )
                )
        circuit = race["Circuit"]
        rows.append(
            RaceRow(
                race_id=rid,
                season=int(race["season"]),
                round=int(race["round"]),
                name=race["raceName"],
                date=race["date"],
                url=race.get("url"),
                circuit_id=circuit["circuitId"],
                circuit_name=circuit["circuitName"],
                locality=circuit["Location"]["locality"],
                country=circuit["Location"]["country"],
                lat=float(circuit["Location"]["lat"]),
                lng=float(circuit["Location"]["long"]),
                sessions=sessions,
            )
        )
    return rows


def result_rows(endpoint: str, races: list[dict[str, Any]], results_key: str) -> list[ResultRow]:
    session_type = SESSION_TYPES[endpoint]
    rows = []
    for race in races:
        sid = session_id(race_id(int(race["season"]), int(race["round"])), session_type)
        for entry in race[results_key]:
            d, c = entry["Driver"], entry["Constructor"]
            position = _int(entry.get("position"))
            position_text = entry.get("positionText")
            if session_type == "Q":
                classified = position is not None
            else:
                # positionText is a number when classified; "R", "D", "W", "N" otherwise
                classified = bool(position_text and position_text.isdigit())
            rows.append(
                ResultRow(
                    result_id=f"{sid}-{d['driverId']}",
                    session_id=sid,
                    driver=DriverRow(
                        driver_id=d["driverId"],
                        code=d.get("code"),
                        name=f"{d['givenName']} {d['familyName']}",
                        nationality=d.get("nationality"),
                        dob=d.get("dateOfBirth"),
                        number=_int(d.get("permanentNumber")),
                    ),
                    constructor=ConstructorRow(
                        constructor_id=c["constructorId"],
                        name=c["name"],
                        nationality=c.get("nationality"),
                    ),
                    props=ResultProps(
                        session_type=session_type,
                        position=position,
                        position_text=position_text,
                        classified=classified,
                        grid=_int(entry.get("grid")),
                        points=float(entry["points"]) if "points" in entry else None,
                        status=entry.get("status"),
                        laps=_int(entry.get("laps")),
                        q1_ms=parse_lap_time_ms(entry.get("Q1")),
                        q2_ms=parse_lap_time_ms(entry.get("Q2")),
                        q3_ms=parse_lap_time_ms(entry.get("Q3")),
                    ),
                )
            )
    return rows
