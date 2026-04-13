"""Earnings detection — identifies if a stock's gap is likely earnings-driven.

Since there's no free reliable earnings calendar API, we use heuristics:
1. Gap size + volume spike together suggest earnings
2. Quarterly patterns (Jan/Apr/Jul/Oct are result seasons)
3. News headline matching for "results", "earnings", "profit", "revenue"

This gives us a 0-1 score: how likely is this gap earnings-driven?
"""

import re
from datetime import date


# Indian quarterly result months (approximate announcement periods)
_RESULT_MONTHS = {1, 2, 4, 5, 7, 8, 10, 11}  # Results come in these months

# Keywords that signal earnings in news headlines
_EARNINGS_KEYWORDS = re.compile(
    r"\b(results?|earnings?|profit|revenue|quarter|Q[1-4]|net income|"
    r"PAT|EBITDA|topline|bottomline|dividend|EPS|guidance|outlook|"
    r"fiscal|annual|quarterly|YoY|QoQ|beat|miss|report)\b",
    re.IGNORECASE,
)


def earnings_likelihood(
    gap_pct: float,
    rel_vol: float,
    today: date | None = None,
    news_headlines: list[str] | None = None,
) -> float:
    """Estimate probability (0-1) that a gap is earnings-driven.

    Combines:
        - Gap magnitude (bigger = more likely earnings)
        - Volume spike (earnings days have extreme volume)
        - Calendar month (result season or not)
        - News keyword matching

    Returns:
        Float 0.0 to 1.0: likelihood of earnings-driven gap
    """
    score = 0.0
    today = today or date.today()

    # Factor 1: Gap size — earnings gaps tend to be large
    abs_gap = abs(gap_pct)
    if abs_gap >= 10:
        score += 0.3
    elif abs_gap >= 5:
        score += 0.2
    elif abs_gap >= 3:
        score += 0.1

    # Factor 2: Volume — earnings days often have 3-5x+ volume
    if rel_vol >= 5.0:
        score += 0.3
    elif rel_vol >= 3.0:
        score += 0.2
    elif rel_vol >= 2.0:
        score += 0.1

    # Factor 3: Result season
    if today.month in _RESULT_MONTHS:
        score += 0.2

    # Factor 4: News headlines
    if news_headlines:
        matches = sum(1 for h in news_headlines if _EARNINGS_KEYWORDS.search(h))
        if matches >= 2:
            score += 0.3
        elif matches >= 1:
            score += 0.2

    return min(score, 1.0)


def is_result_season(today: date | None = None) -> bool:
    """Check if we're in a quarterly result season."""
    today = today or date.today()
    return today.month in _RESULT_MONTHS
