def detect_confirmation(candles, bias):
    if len(candles) < 2:
        return False, "NO_DATA"

    c1 = candles[-2]
    c2 = candles[-1]

    # bullish engulfing
    if bias == "BUY":
        if c1["close"] < c1["open"] and c2["close"] > c2["open"]:
            if c2["close"] > c1["open"]:
                return True, "BULLISH_ENGULFING"

        # rejection wick (lower wick strong)
        if (c2["low"] < c2["open"] and c2["close"] > c2["open"]):
            return True, "BULLISH_REJECTION"

    # bearish engulfing
    if bias == "SELL":
        if c1["close"] > c1["open"] and c2["close"] < c2["open"]:
            if c2["close"] < c1["open"]:
                return True, "BEARISH_ENGULFING"

        # rejection wick (upper wick strong)
        if (c2["high"] > c2["open"] and c2["close"] < c2["open"]):
            return True, "BEARISH_REJECTION"

    return False, "NONE"
