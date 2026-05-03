"""Market regime detection — classifies current market conditions.

Uses Nifty 50 index data to determine the prevailing market regime:
    - TRENDING_UP:     Strong uptrend (EMA slope positive + ATR normal)
    - TRENDING_DOWN:   Strong downtrend (EMA slope negative + ATR normal)
    - SIDEWAYS:        Range-bound (EMA slope flat + ATR contracted)
    - HIGH_VOLATILITY: Volatile / chaotic (ATR expanded significantly)

Regime is used to:
    1. Adjust probability threshold dynamically
    2. Modulate position sizing
    3. Act as an input feature to the classifier
"""

from __future__ import annotations

import logging
from enum import Enum

import numpy as np
import pandas as pd

from project.features.indicators import ema, atr

log = logging.getLogger(__name__)


class MarketRegime(str, Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"


# ── Thresholds (calibrated on Nifty 50 daily data) ──────────────────────────
_EMA_SLOPE_THRESH = 0.15        # %/day over 10-day window — flat below this
_ATR_EXPANSION_THRESH = 1.4     # ATR14 / ATR60 — above this = high vol


def detect_regime(
    index_df: pd.DataFrame,
    ema_period: int = 20,
    slope_window: int = 10,
    atr_short: int = 14,
    atr_long: int = 60,
) -> MarketRegime:
    """Classify current market regime from index OHLCV data.

    Args:
        index_df: Daily OHLCV for a broad market index (e.g., Nifty 50).
                  Must have at least ``max(atr_long, ema_period + slope_window)`` rows.
        ema_period: EMA period for trend detection.
        slope_window: Number of days to measure EMA slope over.
        atr_short: Short ATR period for volatility expansion.
        atr_long: Long ATR period as baseline.

    Returns:
        MarketRegime enum value.
    """
    min_rows = max(atr_long + 5, ema_period + slope_window + 5)
    if len(index_df) < min_rows:
        log.warning("Not enough index data (%d rows) for regime detection", len(index_df))
        return MarketRegime.SIDEWAYS

    close = index_df["Close"]

    # ── EMA slope (trend direction + strength) ────────────────────────────
    ema_series = ema(close, ema_period)
    ema_now = float(ema_series.iloc[-1])
    ema_ago = float(ema_series.iloc[-slope_window])
    if ema_ago > 0:
        ema_slope_pct = (ema_now - ema_ago) / ema_ago * 100 / slope_window
    else:
        ema_slope_pct = 0.0

    # ── ATR expansion (volatility regime) ─────────────────────────────────
    atr_short_series = atr(index_df, atr_short)
    atr_long_series = atr(index_df, atr_long)

    atr_s = float(atr_short_series.iloc[-1]) if len(atr_short_series) >= atr_short else 0.0
    atr_l = float(atr_long_series.iloc[-1]) if len(atr_long_series) >= atr_long else 1.0
    atr_ratio = atr_s / atr_l if atr_l > 0 else 1.0

    # ── Classification ────────────────────────────────────────────────────
    if atr_ratio >= _ATR_EXPANSION_THRESH:
        return MarketRegime.HIGH_VOLATILITY

    if abs(ema_slope_pct) < _EMA_SLOPE_THRESH:
        return MarketRegime.SIDEWAYS

    if ema_slope_pct > 0:
        return MarketRegime.TRENDING_UP
    else:
        return MarketRegime.TRENDING_DOWN


def regime_to_numeric(regime: MarketRegime) -> float:
    """Convert regime enum to a numeric feature for the classifier.

    Encoding:
        TRENDING_UP     → 1.0
        TRENDING_DOWN   → -1.0
        SIDEWAYS        → 0.0
        HIGH_VOLATILITY → 2.0  (distinct — model should learn to be cautious)
    """
    return {
        MarketRegime.TRENDING_UP: 1.0,
        MarketRegime.TRENDING_DOWN: -1.0,
        MarketRegime.SIDEWAYS: 0.0,
        MarketRegime.HIGH_VOLATILITY: 2.0,
    }[regime]


def compute_regime_features(index_df: pd.DataFrame) -> dict:
    """Compute all regime-related features for the classifier.

    Returns a dict with:
        regime_numeric:   Encoded regime (-1 to 2)
        ema20_slope_idx:  Raw EMA slope of the index (% per day)
        atr_expansion:    ATR14/ATR60 ratio
        index_momentum_5d: 5-day return of the index (%)
    """
    min_rows = 65
    if len(index_df) < min_rows:
        return _regime_defaults()

    close = index_df["Close"]
    ema_series = ema(close, 20)
    ema_now = float(ema_series.iloc[-1])
    ema_10ago = float(ema_series.iloc[-10])
    slope = (ema_now - ema_10ago) / ema_10ago * 100 / 10 if ema_10ago > 0 else 0.0

    atr14 = atr(index_df, 14)
    atr60 = atr(index_df, 60)
    atr_s = float(atr14.iloc[-1]) if len(atr14) >= 14 else 0.0
    atr_l = float(atr60.iloc[-1]) if len(atr60) >= 60 else 1.0
    atr_expansion = atr_s / atr_l if atr_l > 0 else 1.0

    c_now = float(close.iloc[-1])
    c_5ago = float(close.iloc[-6]) if len(close) >= 6 else c_now
    index_momentum_5d = (c_now - c_5ago) / c_5ago * 100 if c_5ago > 0 else 0.0

    regime = detect_regime(index_df)

    return {
        "regime_numeric": regime_to_numeric(regime),
        "ema20_slope_idx": round(slope, 4),
        "atr_expansion": round(atr_expansion, 4),
        "index_momentum_5d": round(index_momentum_5d, 4),
    }


def _regime_defaults() -> dict:
    return {
        "regime_numeric": 0.0,
        "ema20_slope_idx": 0.0,
        "atr_expansion": 1.0,
        "index_momentum_5d": 0.0,
    }


REGIME_FEATURE_COLUMNS = [
    "regime_numeric",
    "ema20_slope_idx",
    "atr_expansion",
    "index_momentum_5d",
]
"""Feature columns exported for use in the classifier."""
