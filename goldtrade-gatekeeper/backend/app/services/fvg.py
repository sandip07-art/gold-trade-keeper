def detect_fvg(candles):
    if len(candles) < 3:
        return None

    c1 = candles[-3]
    c2 = candles[-2]
    c3 = candles[-1]

    # bullish FVG
    if c1["high"] < c3["low"]:
        return {
            "type": "BULLISH_FVG",
            "zone": [c1["high"], c3["low"]]
        }

    # bearish FVG
    if c1["low"] > c3["high"]:
        return {
            "type": "BEARISH_FVG",
            "zone": [c3["high"], c1["low"]]
        }

    return None
