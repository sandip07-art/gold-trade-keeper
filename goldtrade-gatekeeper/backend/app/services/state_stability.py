"""
State Stability Filter
───────────────────────
Prevents a signal from being confirmed until it has persisted across
N consecutive candle evaluations.  Avoids reacting to single-candle spikes.

Usage
─────
  stable_bias, confirmed = require_persistence(
      current_value = bias,
      history       = last_N_biases,   # list of recent values, oldest first
      required_count = 2,
  )

If the current value matches the last (required_count - 1) values it is
considered stable and confirmed=True is returned.
If not enough history exists yet, confirmed=False is returned along with
the current raw value so callers can decide how to handle immaturity.

This is intentionally a pure function with no DB state — the caller
(gatekeeper) passes in the rolling window from the DecisionLog.
"""
from typing import TypeVar

T = TypeVar("T")


def require_persistence(
    current_value: T,
    history: list[T],
    required_count: int = 2,
) -> tuple[T, bool]:
    """
    Args:
        current_value:  The value just computed this tick.
        history:        Ordered list of past values (oldest → newest).
                        Should contain at least (required_count - 1) items
                        for a confirmation to be possible.
        required_count: Total consecutive identical values needed (including current).

    Returns:
        (stable_value, is_confirmed)
        stable_value  — current_value when confirmed, or "NEUTRAL"/"PENDING" otherwise.
        is_confirmed  — True only when the full run of required_count matches.
    """
    if required_count <= 1:
        return current_value, True

    # Need (required_count - 1) prior entries to compare against current
    needed_prior = required_count - 1
    recent = history[-needed_prior:] if len(history) >= needed_prior else history

    if len(recent) < needed_prior:
        # Not enough history yet — treat as unconfirmed
        return current_value, False

    all_match = all(v == current_value for v in recent)
    return current_value, all_match


def get_recent_bias_history(db, limit: int) -> list[str]:
    """
    Pull the `bias` field from the last `limit` DecisionLog rows (newest-last).
    Used by the gatekeeper to feed require_persistence().
    """
    from ..models import DecisionLog

    rows = (
        db.query(DecisionLog.bias)
        .order_by(DecisionLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    # rows come back newest-first; reverse so oldest is index-0
    return [r.bias for r in reversed(rows)]


def get_recent_vol_history(db, limit: int) -> list[str]:
    """Pull vol_state from the last `limit` DecisionLog metrics."""
    from ..models import DecisionLog

    rows = (
        db.query(DecisionLog.metrics)
        .order_by(DecisionLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    states = []
    for (m,) in reversed(rows):
        if m and isinstance(m, dict):
            states.append(m.get("vol_state", ""))
    return states
