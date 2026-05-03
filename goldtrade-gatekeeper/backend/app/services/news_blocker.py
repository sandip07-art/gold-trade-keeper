"""
News Blocker
────────────
Blocks trade if any HIGH-impact USD event falls within ±window_minutes of now.
Events are dicts: {time: ISO-8601, name: str, impact: "HIGH"|"MEDIUM"|"LOW"}
"""
from datetime import datetime, timedelta, timezone
from typing import Any


def is_in_news_window(
    news_events: list[dict[str, Any]],
    dt: datetime | None = None,
    window_minutes: int = 30,
) -> tuple[bool, list[str]]:
    """Return (is_blocked, [blocking_event_names])."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    window = timedelta(minutes=window_minutes)
    blocking: list[str] = []

    for event in news_events or []:
        if event.get("impact", "").upper() != "HIGH":
            continue
        raw_time = event.get("time", "")
        try:
            event_time = datetime.fromisoformat(raw_time)
        except (ValueError, TypeError):
            continue
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        if abs(dt - event_time) <= window:
            blocking.append(event.get("name", "Unknown Event"))

    return bool(blocking), blocking
