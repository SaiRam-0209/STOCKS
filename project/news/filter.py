"""News & event risk filter — prevents trading during high-impact events.

This is a RISK CONTROL layer, NOT a directional predictor.
It does NOT use sentiment to predict price direction.

Actions when high-impact news is detected:
    1. SKIP trade entirely (for earnings, regulatory actions)
    2. REDUCE position size by 50% (for block deals, analyst downgrades)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


# ── High-impact event patterns ──────────────────────────────────────────────
_EARNINGS_PATTERN = re.compile(
    r"\b(results?\s+(announce|declar|report)|Q[1-4]\s+(results?|earnings?)|"
    r"quarterly\s+(results?|earnings?)|net\s+profit|PAT\s+(jumps?|falls?|rises?)|"
    r"EBITDA|revenue\s+(beats?|misses?)|EPS|annual\s+results?)\b",
    re.IGNORECASE,
)

_REGULATORY_PATTERN = re.compile(
    r"\b(SEBI\s+(order|ban|penalty|investigation)|RBI\s+(directive|action|penalty)|"
    r"suspended|delisted|insolvency|NCLT|fraud|scam|arrest|raid)\b",
    re.IGNORECASE,
)

_BLOCK_DEAL_PATTERN = re.compile(
    r"\b(block\s+deal|bulk\s+deal|promoter\s+(sell|buy|stake|pledg)|"
    r"stake\s+sale|OFS|rights?\s+issue)\b",
    re.IGNORECASE,
)

_ANALYST_PATTERN = re.compile(
    r"\b(downgrade|upgrade|target\s+price\s+(cut|raised)|"
    r"price\s+target|rating\s+(cut|raised|lowered))\b",
    re.IGNORECASE,
)


@dataclass
class NewsFilterResult:
    """Result of the news risk filter."""
    action: str             # "ALLOW" / "SKIP" / "REDUCE"
    reason: str = ""
    size_multiplier: float = 1.0  # 1.0 = normal, 0.5 = reduced
    event_type: str = ""    # "EARNINGS" / "REGULATORY" / "BLOCK_DEAL" / "ANALYST" / ""
    matched_headlines: list[str] | None = None


def filter_by_news(
    symbol: str,
    news_items: list[dict] | None = None,
    max_age_hours: float = 24.0,
) -> NewsFilterResult:
    """Check if recent news warrants skipping or reducing a trade.

    Args:
        symbol: Stock symbol (e.g., "RELIANCE.NS").
        news_items: List of news dicts with 'title', 'published' keys.
                    If None, no filtering is applied.
        max_age_hours: Only consider news from the last N hours.

    Returns:
        NewsFilterResult with action (ALLOW/SKIP/REDUCE).
    """
    if not news_items:
        return NewsFilterResult(action="ALLOW")

    sym_clean = symbol.replace(".NS", "").replace(".BO", "").lower()
    cutoff = datetime.now() - timedelta(hours=max_age_hours)

    relevant_news: list[str] = []
    for item in news_items:
        title = item.get("title", "")

        # Check if news is about this stock
        if sym_clean not in title.lower():
            continue

        # Check recency
        pub = item.get("published")
        if pub:
            try:
                if isinstance(pub, str):
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                elif isinstance(pub, datetime):
                    pub_dt = pub
                else:
                    pub_dt = cutoff  # Unknown format — include
                if pub_dt < cutoff:
                    continue
            except Exception:
                pass

        relevant_news.append(title)

    if not relevant_news:
        return NewsFilterResult(action="ALLOW")

    # Check for high-impact events (priority order: most dangerous first)
    for headline in relevant_news:
        if _REGULATORY_PATTERN.search(headline):
            return NewsFilterResult(
                action="SKIP",
                reason=f"Regulatory event detected: {headline[:80]}",
                size_multiplier=0.0,
                event_type="REGULATORY",
                matched_headlines=relevant_news,
            )

    for headline in relevant_news:
        if _EARNINGS_PATTERN.search(headline):
            return NewsFilterResult(
                action="SKIP",
                reason=f"Earnings event detected: {headline[:80]}",
                size_multiplier=0.0,
                event_type="EARNINGS",
                matched_headlines=relevant_news,
            )

    for headline in relevant_news:
        if _BLOCK_DEAL_PATTERN.search(headline):
            return NewsFilterResult(
                action="REDUCE",
                reason=f"Block/bulk deal detected: {headline[:80]}",
                size_multiplier=0.5,
                event_type="BLOCK_DEAL",
                matched_headlines=relevant_news,
            )

    for headline in relevant_news:
        if _ANALYST_PATTERN.search(headline):
            return NewsFilterResult(
                action="REDUCE",
                reason=f"Analyst action detected: {headline[:80]}",
                size_multiplier=0.5,
                event_type="ANALYST",
                matched_headlines=relevant_news,
            )

    # News exists but no high-impact pattern matched
    return NewsFilterResult(action="ALLOW", matched_headlines=relevant_news)
