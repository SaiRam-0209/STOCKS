"""Filtering engine: applies primary/secondary filters and scores candidates."""

from project.data.symbols import RANK_MAP


def passes_primary_filters(features: dict) -> bool:
    """Check if stock passes ALL primary filter conditions.

    Primary filters:
        - gap >= 2% (gap up or gap down)
        - relative volume >= 1.5
        - price > VWAP (bullish bias)
    """
    return (
        abs(features["gap_pct"]) >= 2.0
        and features["rel_vol"] >= 1.5
        and features["price_above_vwap"]
    )


def compute_score(features: dict) -> int:
    """Score a stock based on filter criteria.

    Scoring:
        gap >= 2%       → +2
        rel_vol >= 1.5  → +3
        price > VWAP    → +2
        EMA bullish     → +2
        Max possible    → 9
    """
    score = 0
    if abs(features["gap_pct"]) >= 2.0:
        score += 2
    if features["rel_vol"] >= 1.5:
        score += 3
    if features["price_above_vwap"]:
        score += 2
    if features["ema_bullish"]:
        score += 2
    return score


def build_reason(features: dict) -> str:
    """Build a human-readable reason string for why this stock was selected."""
    reasons = []
    if abs(features["gap_pct"]) >= 2.0:
        direction = "Up" if features["gap_pct"] > 0 else "Down"
        reasons.append(f"Gap {direction} {abs(features['gap_pct']):.1f}%")
    if features["rel_vol"] >= 1.5:
        reasons.append(f"Volume {features['rel_vol']:.1f}x avg")
    if features["price_above_vwap"]:
        reasons.append("Above VWAP")
    if features["ema_bullish"]:
        reasons.append("EMA Trend Bullish")
    return " + ".join(reasons) if reasons else "No strong signals"


def filter_and_rank(all_features: list[dict], top_n: int = 5) -> list[dict]:
    """Filter stocks through primary conditions, score, and rank.

    Args:
        all_features: List of feature dicts from build_features().
        top_n: Number of top candidates to return.

    Returns:
        Top N candidates sorted by score (descending), each enriched
        with 'score' and 'reason' fields.
    """
    candidates = []
    for f in all_features:
        if passes_primary_filters(f):
            f["score"] = compute_score(f)
            f["reason"] = build_reason(f)
            f["index_rank"] = RANK_MAP.get(f["symbol"], 999)
            candidates.append(f)

    # Sort by score (desc), then by index rank (asc) as tiebreaker
    candidates.sort(key=lambda x: (-x["score"], x["index_rank"]))
    return candidates[:top_n]
