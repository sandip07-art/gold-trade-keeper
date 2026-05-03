"""
Session Filter
──────────────
London  : 07:00–10:00 UTC
New York: 12:00–16:00 UTC
Any other time → BLOCKED: "OUTSIDE SESSION"
"""
from datetime import datetime, timezone, time


SESSIONS: dict[str, tuple[time, time]] = {
    "LONDON":   (time(7, 0),  time(10, 0)),
    "NEW_YORK": (time(12, 0), time(16, 0)),
}


def get_session(dt: datetime | None = None) -> tuple[str, bool]:
    """Return (session_name, is_valid).  dt must be UTC-aware or naive-UTC."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    t = dt.time().replace(tzinfo=None)
    for name, (start, end) in SESSIONS.items():
        if start <= t < end:
            return name, True
    return "OUTSIDE", False
