"""Strategy engine: generates entry, stoploss, and target for each candidate."""


def generate_trade_signal(features: dict) -> dict:
    """Generate trade levels based on first 15-min candle breakout strategy.

    Entry:    Breakout above first 15-min high
    Stoploss: Below first 15-min low
    Target:   Entry + 2 × risk (1:2 R:R)

    Args:
        features: Feature dict with first_candle_high, first_candle_low, etc.

    Returns:
        Dict with entry, stoploss, target, risk, reward, and direction.
    """
    high = features["first_candle_high"]
    low = features["first_candle_low"]
    gap_pct = features["gap_pct"]

    # Determine direction based on gap
    if gap_pct > 0:
        # Gap up → bullish bias → long trade
        entry = high
        stoploss = low
        risk = entry - stoploss
        target = entry + (2 * risk)
        direction = "LONG"
    else:
        # Gap down → bearish bias → short trade
        entry = low
        stoploss = high
        risk = stoploss - entry
        target = entry - (2 * risk)
        direction = "SHORT"

    return {
        "direction": direction,
        "entry": round(entry, 2),
        "stoploss": round(stoploss, 2),
        "target": round(target, 2),
        "risk": round(risk, 2),
        "reward": round(2 * risk, 2),
    }


def enrich_candidates(candidates: list[dict]) -> list[dict]:
    """Add trade signals to each candidate.

    Args:
        candidates: List of filtered/ranked feature dicts.

    Returns:
        Same list, each dict enriched with trade signal fields.
    """
    for c in candidates:
        signal = generate_trade_signal(c)
        c.update(signal)
    return candidates
