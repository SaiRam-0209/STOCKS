"""Multiple trading strategies — ORB, VWAP Bounce, Mean Reversion.

Each strategy has its own scan + entry/exit rules.
The executor picks the best strategy based on market conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import numpy as np
from project.features.indicators import vwap, ema, atr, rsi


@dataclass
class StrategySignal:
    strategy: str       # "ORB", "VWAP_BOUNCE", "MEAN_REVERSION"
    ticker: str
    direction: str      # "LONG" or "SHORT"
    entry: float
    stoploss: float
    target: float
    confidence: float   # 0-1
    reason: str


def scan_orb(daily_df: pd.DataFrame, intra_df: pd.DataFrame, ticker: str) -> StrategySignal | None:
    """Opening Range Breakout — our primary strategy.

    Entry: Break of first 15-min candle high/low
    SL: Opposite end of first candle
    Target: 2R
    """
    if intra_df.empty or len(intra_df) < 2:
        return None
    if daily_df.empty or len(daily_df) < 2:
        return None

    first = intra_df.iloc[0]
    prev_close = float(daily_df.iloc[-2]["Close"])
    today_open = float(first["Open"])

    gap_pct = (today_open - prev_close) / prev_close * 100
    if abs(gap_pct) < 2.0:
        return None

    candle_high = float(first["High"])
    candle_low = float(first["Low"])
    candle_range = candle_high - candle_low
    if candle_range <= 0:
        return None

    direction = "LONG" if gap_pct > 0 else "SHORT"
    if direction == "LONG":
        entry, stoploss = candle_high, candle_low
        risk = entry - stoploss
        target = entry + 2 * risk
    else:
        entry, stoploss = candle_low, candle_high
        risk = stoploss - entry
        target = entry - 2 * risk

    return StrategySignal(
        strategy="ORB", ticker=ticker, direction=direction,
        entry=round(entry, 2), stoploss=round(stoploss, 2),
        target=round(target, 2), confidence=min(abs(gap_pct) / 10, 1.0),
        reason=f"Gap {gap_pct:+.1f}% breakout",
    )


def scan_vwap_bounce(daily_df: pd.DataFrame, intra_df: pd.DataFrame, ticker: str) -> StrategySignal | None:
    """VWAP Bounce — buy/sell at VWAP support/resistance.

    Entry: Price touches VWAP and bounces
    SL: Below/above VWAP by 0.5%
    Target: Previous high/low (1.5R)
    Best in: Trending days with pullbacks
    """
    if intra_df.empty or len(intra_df) < 6:
        return None

    vwap_series = vwap(intra_df)
    if vwap_series.empty:
        return None

    current_price = float(intra_df.iloc[-1]["Close"])
    current_vwap = float(vwap_series.iloc[-1])

    if current_vwap <= 0:
        return None

    distance_pct = (current_price - current_vwap) / current_vwap * 100

    # Price near VWAP (within 0.3%) and bouncing
    if abs(distance_pct) > 0.5:
        return None

    # Check recent candles for bounce pattern
    last_3_closes = [float(intra_df.iloc[i]["Close"]) for i in range(-3, 0)]

    if last_3_closes[-1] > last_3_closes[-2] > current_vwap:
        # Bouncing up from VWAP
        entry = round(current_price, 2)
        stoploss = round(current_vwap * 0.995, 2)
        risk = entry - stoploss
        if risk <= 0:
            return None
        target = round(entry + 1.5 * risk, 2)
        return StrategySignal(
            strategy="VWAP_BOUNCE", ticker=ticker, direction="LONG",
            entry=entry, stoploss=stoploss, target=target,
            confidence=0.6, reason=f"VWAP bounce at ₹{current_vwap:.0f}",
        )

    if last_3_closes[-1] < last_3_closes[-2] < current_vwap:
        # Rejecting down from VWAP
        entry = round(current_price, 2)
        stoploss = round(current_vwap * 1.005, 2)
        risk = stoploss - entry
        if risk <= 0:
            return None
        target = round(entry - 1.5 * risk, 2)
        return StrategySignal(
            strategy="VWAP_BOUNCE", ticker=ticker, direction="SHORT",
            entry=entry, stoploss=stoploss, target=target,
            confidence=0.6, reason=f"VWAP rejection at ₹{current_vwap:.0f}",
        )

    return None


def scan_mean_reversion(daily_df: pd.DataFrame, ticker: str) -> StrategySignal | None:
    """Mean Reversion — buy oversold, sell overbought.

    Entry: RSI < 30 (oversold) or RSI > 70 (overbought) with EMA support
    SL: Below recent low / above recent high
    Target: EMA20 (mean)
    Best in: Sideways/range-bound markets
    """
    if daily_df.empty or len(daily_df) < 30:
        return None

    close = daily_df["Close"]
    rsi_series = rsi(close, 14)
    ema20_series = ema(close, 20)

    if rsi_series.empty or ema20_series.empty:
        return None

    current_rsi = float(rsi_series.iloc[-1])
    current_price = float(close.iloc[-1])
    current_ema20 = float(ema20_series.iloc[-1])
    recent_low = float(daily_df["Low"].tail(5).min())
    recent_high = float(daily_df["High"].tail(5).max())

    if current_rsi < 30 and current_price < current_ema20:
        # Oversold — look for bounce
        entry = round(current_price, 2)
        stoploss = round(recent_low * 0.99, 2)
        target = round(current_ema20, 2)
        risk = entry - stoploss
        if risk <= 0:
            return None
        return StrategySignal(
            strategy="MEAN_REVERSION", ticker=ticker, direction="LONG",
            entry=entry, stoploss=stoploss, target=target,
            confidence=0.5, reason=f"RSI {current_rsi:.0f} oversold, target EMA20",
        )

    if current_rsi > 70 and current_price > current_ema20:
        # Overbought — look for pullback
        entry = round(current_price, 2)
        stoploss = round(recent_high * 1.01, 2)
        target = round(current_ema20, 2)
        risk = stoploss - entry
        if risk <= 0:
            return None
        return StrategySignal(
            strategy="MEAN_REVERSION", ticker=ticker, direction="SHORT",
            entry=entry, stoploss=stoploss, target=target,
            confidence=0.5, reason=f"RSI {current_rsi:.0f} overbought, target EMA20",
        )

    return None


def recommend_strategy(macro_mood: str, vix_level: float) -> str:
    """Recommend the best strategy based on current market conditions."""
    if vix_level > 22:
        return "MEAN_REVERSION"  # High VIX = choppy, mean reversion works
    if macro_mood in ("BULLISH", "VERY_BULLISH"):
        return "ORB"             # Trending market = breakouts work
    if macro_mood in ("BEARISH", "VERY_BEARISH"):
        return "ORB"             # Strong trend down = short breakouts work
    return "VWAP_BOUNCE"         # Neutral = range-bound, VWAP bounces
