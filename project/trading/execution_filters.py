"""Execution filters — pre-trade safety checks to avoid bad entries.

Prevents trades when:
    1. Spread is too high (illiquid stock — wide bid/ask)
    2. First candle is extremely volatile (news spike — no edge)
    3. Volume spike is abnormal (possible manipulation)

These are NOT feature-based ML filters — they are hard rules
to prevent mechanical execution problems.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from project.features.indicators import atr

log = logging.getLogger(__name__)


@dataclass
class ExecutionFilterConfig:
    """Configurable thresholds for execution filters."""
    max_spread_bps: float = 100.0          # Max spread in basis points (1% = 100 bps)
    max_candle_atr_ratio: float = 3.0      # First candle range / ATR14 — skip above this
    max_volume_spike_ratio: float = 15.0   # Today vol / 10d avg — skip manipulation
    min_volume_spike_ratio: float = 0.3    # Below this = dead stock, skip
    min_stock_price: float = 50.0          # Avoid penny stocks
    max_stock_price: float = 10000.0       # Position sizing handles expensive stocks


@dataclass
class FilterResult:
    """Result of running execution filters on a trade candidate."""
    passed: bool
    reason: str = ""
    spread_bps: float = 0.0
    candle_atr_ratio: float = 0.0
    volume_spike: float = 0.0


def check_execution_filters(
    today_open: float,
    today_high: float,
    today_low: float,
    today_volume: float,
    daily_before: pd.DataFrame,
    config: ExecutionFilterConfig | None = None,
) -> FilterResult:
    """Run all execution filters on a single trade candidate.

    Args:
        today_open: Today's opening price.
        today_high: Today's (or first candle's) high.
        today_low: Today's (or first candle's) low.
        today_volume: Today's (or first candle's) volume.
        daily_before: Historical daily OHLCV (excluding today).
        config: Filter thresholds.

    Returns:
        FilterResult with pass/fail and diagnostic values.
    """
    if config is None:
        config = ExecutionFilterConfig()

    result = FilterResult(passed=True)

    # ── Price filter ──────────────────────────────────────────────────────
    if today_open < config.min_stock_price:
        result.passed = False
        result.reason = f"Price too low: ₹{today_open:.0f} < ₹{config.min_stock_price:.0f}"
        return result

    if today_open > config.max_stock_price:
        result.passed = False
        result.reason = f"Price too high: ₹{today_open:.0f} > ₹{config.max_stock_price:.0f}"
        return result

    # ── Spread proxy (high-low / close as bps) ────────────────────────────
    candle_range = today_high - today_low
    if today_open > 0:
        spread_bps = candle_range / today_open * 10_000
        result.spread_bps = round(spread_bps, 1)

        if spread_bps > config.max_spread_bps:
            result.passed = False
            result.reason = f"Spread too wide: {spread_bps:.0f} bps > {config.max_spread_bps:.0f} bps"
            return result

    # ── First candle vs ATR (extreme volatility) ──────────────────────────
    if len(daily_before) >= 14:
        atr_series = atr(daily_before, 14)
        if len(atr_series) > 0:
            current_atr = float(atr_series.iloc[-1])
            if current_atr > 0:
                ratio = candle_range / current_atr
                result.candle_atr_ratio = round(ratio, 2)

                if ratio > config.max_candle_atr_ratio:
                    result.passed = False
                    result.reason = (
                        f"First candle too volatile: {ratio:.1f}x ATR "
                        f"(max: {config.max_candle_atr_ratio:.1f}x)"
                    )
                    return result

    # ── Volume spike (manipulation detection) ─────────────────────────────
    if len(daily_before) >= 10:
        avg_vol = float(daily_before["Volume"].tail(10).mean())
        if avg_vol > 0:
            vol_spike = today_volume / avg_vol
            result.volume_spike = round(vol_spike, 1)

            if vol_spike > config.max_volume_spike_ratio:
                result.passed = False
                result.reason = (
                    f"Abnormal volume spike: {vol_spike:.1f}x avg "
                    f"(max: {config.max_volume_spike_ratio:.1f}x — possible manipulation)"
                )
                return result

            if vol_spike < config.min_volume_spike_ratio:
                result.passed = False
                result.reason = (
                    f"Dead volume: {vol_spike:.1f}x avg "
                    f"(min: {config.min_volume_spike_ratio:.1f}x)"
                )
                return result

    return result
