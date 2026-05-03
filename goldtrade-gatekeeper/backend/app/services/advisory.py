"""
Advisory Engine  (non-controlling)
────────────────────────────────────
Provides structured market interpretation — NOT decisions.

Output shape:
  {
    summary:    str          # 1-2 sentence contextual read
    confidence: HIGH|MEDIUM|LOW
    playbook:   list[str]    # recommended behaviours (not orders)
  }

Language rules:
  • No prediction language ("will", "must", "guaranteed")
  • No forced decisions
  • Insight only — trader retains full autonomy
"""
from typing import Any


def generate_advisory(
    session: str,
    vol_state: str,
    bias: str,
    news_blocked: bool,
    strict_mode: bool = False,
) -> dict[str, Any]:

    lines: list[str] = []
    playbook: list[str] = []
    confidence = "LOW"

    # ── News override ──────────────────────────────────────────────────────────
    if news_blocked:
        lines.append(
            "High-impact news is scheduled nearby. Market structure tends to be "
            "unreliable and spreads may widen around these events."
        )
        playbook += [
            "Consider staying flat until the post-news candle closes.",
            "If already in a trade, tighten stops to protect open profit.",
        ]
        confidence = "LOW"
        return {"summary": " ".join(lines), "confidence": confidence, "playbook": playbook}

    # ── Outside session ────────────────────────────────────────────────────────
    if session == "OUTSIDE":
        lines.append(
            "Price is outside primary institutional sessions. "
            "Liquidity is reduced and spreads are typically wider."
        )
        playbook += [
            "Watch for session-open momentum setups rather than acting now.",
            "Mark key levels from the Asian session range for reference.",
        ]
        confidence = "LOW"
        return {"summary": " ".join(lines), "confidence": confidence, "playbook": playbook}

    # ── Session active ─────────────────────────────────────────────────────────
    vol_label = vol_state  # EXPANSION | LOW VOL
    bias_buy  = "BUY"  in bias
    bias_sell = "SELL" in bias
    bias_neutral = bias == "NEUTRAL"

    if vol_label == "EXPANSION":
        if bias_sell:
            lines.append(
                f"DXY is showing strength with volatility expanding during the {session} session. "
                "Gold faces potential headwinds from a strengthening dollar."
            )
            playbook += [
                "Look for bearish price structure on Gold at resistance zones.",
                "Confirm with a bearish close on the 5m candle before considering an entry.",
                "Keep risk defined — expansion phases can reverse sharply.",
            ]
            confidence = "HIGH" if not strict_mode else "MEDIUM"

        elif bias_buy:
            lines.append(
                f"DXY is showing weakness with volatility expanding during the {session} session. "
                "Gold may find support as the dollar softens."
            )
            playbook += [
                "Look for bullish price structure on Gold at key support zones.",
                "Confirm with a bullish close on the 5m candle before considering an entry.",
                "Keep risk defined — expansion phases can reverse sharply.",
            ]
            confidence = "HIGH" if not strict_mode else "MEDIUM"

        else:  # neutral bias
            lines.append(
                f"Volatility is expanding during the {session} session but DXY has not "
                "shown a clear directional break. The environment is active but lacking bias."
            )
            playbook += [
                "Wait for DXY to show directional conviction before positioning on Gold.",
                "Range-trade setups may be valid if price respects clear S/R boundaries.",
            ]
            confidence = "MEDIUM"

    else:  # LOW VOL
        lines.append(
            f"Volatility is contracted during the {session} session. "
            "The market may be coiling before its next directional move."
        )
        playbook += [
            "Avoid chasing price in low-volatility conditions — risk/reward is typically poor.",
            "Watch for a volatility expansion trigger (ATR breakout) before engaging.",
            "Mark range highs and lows — a break with momentum could signal the next leg.",
        ]
        confidence = "LOW"

    return {
        "summary": " ".join(lines),
        "confidence": confidence,
        "playbook": playbook,
    }
