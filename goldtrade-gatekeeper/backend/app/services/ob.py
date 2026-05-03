def detect_ob(candles):
    if len(candles) < 3:
        return None

    c2 = candles[-2]
    c3 = candles[-1]

    # bullish OB
    if c2["close"] < c2["open"] and c3["close"] > c3["open"]:
        return {
            "type": "BULLISH_OB",
            "zone": [c2["low"], c2["high"]]
        }

    # bearish OB
    if c2["close"] > c2["open"] and c3["close"] < c3["open"]:
        return {
            "type": "BEARISH_OB",
            "zone": [c2["low"], c2["high"]]
        }

    return None
