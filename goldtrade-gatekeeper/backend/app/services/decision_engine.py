def get_dxy_bias(dxy_candles):
    if len(dxy_candles) < 3:
        return "NEUTRAL"

    last = dxy_candles[-1]
    prev = dxy_candles[-2]

    if last["close"] > prev["high"]:
        return "USD_STRONG"
    elif last["close"] < prev["low"]:
        return "USD_WEAK"
    
    return "NEUTRAL"


def get_structure_bias(candles):
    if len(candles) < 3:
        return "NEUTRAL"

    highs = [c["high"] for c in candles[-3:]]
    lows = [c["low"] for c in candles[-3:]]

    if highs[-1] > highs[-2] and lows[-1] > lows[-2]:
        return "BULLISH"
    elif highs[-1] < highs[-2] and lows[-1] < lows[-2]:
        return "BEARISH"

    return "RANGE"


def get_final_bias(dxy_bias, structure_bias):
    if dxy_bias == "USD_STRONG" and structure_bias == "BEARISH":
        return "SELL"
    elif dxy_bias == "USD_WEAK" and structure_bias == "BULLISH":
        return "BUY"
    
    return "NEUTRAL"


def get_entry_zone(price, candles):
    recent_high = max(c["high"] for c in candles[-10:])
    recent_low = min(c["low"] for c in candles[-10:])

    mid = (recent_high + recent_low) / 2

    if price > mid:
        return "PREMIUM"
    else:
        return "DISCOUNT"


def get_trade_decision(env_ok, bias, zone):
    if not env_ok:
        return "NO TRADE"

    if bias == "BUY" and zone == "DISCOUNT":
        return "BUY"
    elif bias == "SELL" and zone == "PREMIUM":
        return "SELL"

    return "WAIT"
