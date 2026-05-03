"""Lightweight fundamental filter — bias adjustment for intraday trades.

This does NOT predict direction from fundamentals.
It only slightly reduces confidence for stocks with weak fundamentals.

Uses:
    - YoY profit growth (from Yahoo Finance financials)
    - Revenue trend (growth vs contraction)

If weak fundamentals are detected, the confidence score is reduced
by a small penalty (5-10% reduction in position sizing).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

log = logging.getLogger(__name__)


@dataclass
class FundamentalResult:
    """Fundamental quality assessment."""
    quality: str               # "STRONG" / "NEUTRAL" / "WEAK"
    confidence_penalty: float  # 0.0 (no penalty) to 0.15 (weak fundamentals)
    profit_growth_yoy: float | None = None
    revenue_growth_yoy: float | None = None
    details: str = ""


@lru_cache(maxsize=512)
def assess_fundamentals(symbol: str) -> FundamentalResult:
    """Assess fundamental quality for position sizing bias.

    Uses Yahoo Finance quarterly financials data.
    Cached for the trading session (avoid redundant API calls).

    Args:
        symbol: Stock symbol (e.g., "RELIANCE.NS").

    Returns:
        FundamentalResult with quality grade and confidence penalty.
    """
    yf_ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"

    try:
        import yfinance as yf
        tk = yf.Ticker(yf_ticker)

        # Get quarterly financials
        financials = tk.quarterly_financials
        if financials is None or financials.empty or financials.shape[1] < 2:
            return FundamentalResult(
                quality="NEUTRAL",
                confidence_penalty=0.0,
                details="Insufficient financial data",
            )

        # YoY profit growth (compare latest quarter vs same quarter last year)
        profit_growth = _compute_yoy_growth(financials, "Net Income")

        # Revenue trend
        revenue_growth = _compute_yoy_growth(financials, "Total Revenue")

        # Classify
        return _classify(profit_growth, revenue_growth)

    except Exception as exc:
        log.debug("Fundamental check failed for %s: %s", symbol, exc)
        return FundamentalResult(
            quality="NEUTRAL",
            confidence_penalty=0.0,
            details=f"Data unavailable: {exc}",
        )


def _compute_yoy_growth(financials, row_name: str) -> float | None:
    """Compute YoY growth for a specific metric."""
    try:
        if row_name not in financials.index:
            # Try alternate names
            alternates = {
                "Net Income": ["Net Income", "Net Income From Continuing Operations"],
                "Total Revenue": ["Total Revenue", "Operating Revenue"],
            }
            found = False
            for alt in alternates.get(row_name, []):
                if alt in financials.index:
                    row_name = alt
                    found = True
                    break
            if not found:
                return None

        row = financials.loc[row_name]
        latest = float(row.iloc[0])

        # Try to find same quarter last year (4 quarters ago)
        if len(row) >= 5:
            last_year = float(row.iloc[4])
        elif len(row) >= 2:
            last_year = float(row.iloc[-1])
        else:
            return None

        if last_year == 0 or abs(last_year) < 1e-6:
            return None

        return (latest - last_year) / abs(last_year) * 100

    except Exception:
        return None


def _classify(
    profit_growth: float | None,
    revenue_growth: float | None,
) -> FundamentalResult:
    """Classify into STRONG / NEUTRAL / WEAK based on growth metrics."""
    signals = 0  # Negative = weak, positive = strong

    if profit_growth is not None:
        if profit_growth > 20:
            signals += 1
        elif profit_growth < -20:
            signals -= 1

    if revenue_growth is not None:
        if revenue_growth > 10:
            signals += 1
        elif revenue_growth < -10:
            signals -= 1

    if signals >= 2:
        return FundamentalResult(
            quality="STRONG",
            confidence_penalty=0.0,
            profit_growth_yoy=profit_growth,
            revenue_growth_yoy=revenue_growth,
            details="Strong fundamentals — no penalty",
        )
    elif signals <= -1:
        return FundamentalResult(
            quality="WEAK",
            confidence_penalty=0.10,  # 10% reduction in confidence
            profit_growth_yoy=profit_growth,
            revenue_growth_yoy=revenue_growth,
            details="Weak fundamentals — confidence reduced by 10%",
        )
    else:
        return FundamentalResult(
            quality="NEUTRAL",
            confidence_penalty=0.0,
            profit_growth_yoy=profit_growth,
            revenue_growth_yoy=revenue_growth,
            details="Neutral fundamentals",
        )
