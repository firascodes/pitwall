"""Answer blocks -> one Telegram message: HTML text, plain-text fallbacks and an inline keyboard."""

import html
import re
from typing import Any
from urllib.parse import urlencode

MAX_CHARS = 4000  # Telegram allows 4096
MAX_ROWS = 10


def text_html(markdown: str) -> str:
    """The composer's small markdown -> Telegram HTML: bold, bullets, no citation markers."""
    out = html.escape(re.sub(r"\s*\[r\d+(?:,\s*r\d+)*\]", "", markdown))
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out)
    return re.sub(r"^\s*[-*] ", "• ", out, flags=re.M)


def _cell(value: Any) -> str:
    return "–".join(map(str, value)) if isinstance(value, list) else str(value)


def _table(rows: list[dict]) -> str:
    cols = [c for c in rows[0] if c != "lap_id"]
    lines = [" ".join(_cell(r.get(c, "")) for c in cols) for r in rows[:MAX_ROWS]]
    more = f"\n… {len(rows) - MAX_ROWS} more rows" if len(rows) > MAX_ROWS else ""
    return f"<pre>{html.escape(chr(10).join(lines))}</pre>{more}"


def _code(name: str) -> str:
    return name.split()[-1][:3].upper()


def fallback(block: dict) -> str | None:
    """A component as text, for the channels that cannot draw it."""
    kind, data = block["type"], block.get("data", {})
    if kind == "results_table" and data["rows"]:
        return _table(data["rows"])
    if kind == "h2h_card":
        return "\n".join(
            f"<b>{html.escape(r['driver'])} vs {html.escape(r['teammate'])}</b>: "
            f"quali {_cell(r['quali_h2h'])}, race {_cell(r['race_h2h'])}, "
            f"gap {r['avg_quali_gap_pct']:+.2f}%"
            for r in data["rows"]
        )
    if kind == "stint_timeline":
        return "\n".join(
            f"• {html.escape(s['team'])}: R{s['from_round']}–R{s['to_round']}"
            for s in data["stints"]
        )
    if kind == "corner_table":
        a, b = _code(data["a"]["driver"]), _code(data["b"]["driver"])
        top = sorted(data["rows"], key=lambda r: -abs(r["a_gain_s"]))[:5]
        return "\n".join(
            f"<code>{r['corner']:<4}</code> {a if r['a_gain_s'] >= 0 else b} "
            f"+{abs(r['a_gain_s']):.3f}s · {html.escape(r['cause'])}"
            for r in top
        )
    return None


def replay_url(web_url: str, block: dict) -> str:
    data = block["data"]
    query = {k: ",".join(data[k]) for k in ("laps", "drivers", "times")}
    return f"{web_url.rstrip('/')}/replay?{urlencode(query)}"


def render(
    blocks: list[dict], usage: dict | None, web_url: str
) -> tuple[str, list[list[dict]], list[str]]:
    """(message HTML, inline keyboard rows, chip questions in button order)."""
    parts = [text_html(b["text"]) for b in blocks if b["type"] == "text"]
    parts += [f for b in blocks if (f := fallback(b))]
    if usage:
        parts.append(f"<i>${usage['usd']:.6f} · {usage['llm_calls']} LLM calls</i>")
    message = "\n\n".join(parts)[:MAX_CHARS] or "I have no answer for that one."

    keyboard: list[list[dict]] = []
    replay = next((b for b in blocks if b["type"] == "lap_replay"), None)
    if replay and web_url.startswith("https://"):  # Mini Apps need HTTPS
        keyboard.append(
            [{"text": "▶ Open lap replay", "web_app": {"url": replay_url(web_url, replay)}}]
        )
    chips = next((b["options"] for b in blocks if b["type"] == "chips"), [])
    keyboard += [[{"text": c[:60], "callback_data": f"chip:{i}"}] for i, c in enumerate(chips)]
    return message, keyboard, chips
