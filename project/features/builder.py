"""Build feature set for each stock from raw OHLCV data."""

from __future__ import annotations

import pandas as pd

from project.data.fetcher import fetch_daily, fetch_prev_close
from project.features.indicators import (
    gap_percentage,
    relative_volume,
    vwap,
    ema,
    rsi,
    first_candle_range,
)


def build_features(symbol: str, intraday_df: pd.DataFrame) -> dict | None:
    """Compute all features for a single stock.

    Args:
        symbol: Ticker symbol (e.g. "RELIANCE.NS")
        intraday_df: Intraday OHLCV DataFrame (15m candles, multiple days)

    Returns:
        Dict of computed features, or None if insufficient data.
    """
    if intraday_df.empty or len(intraday_df) < 2:
        return None

    # --- Previous close ---
    prev_close = fetch_prev_close(symbol)
    if prev_close is None:
        return None

    # --- Today's data ---
    today = intraday_df.index[-1].date()
    today_df = intraday_df[intraday_df.index.date == today]
    if today_df.empty:
        return None

    today_open = float(today_df.iloc[0]["Open"])
    current_price = float(today_df.iloc[-1]["Close"])
    current_volume = float(today_df["Volume"].sum())

    # --- Gap % ---
    gap_pct = gap_percentage(today_open, prev_close)

    # --- Relative volume (vs 10-day avg daily volume) ---
    daily_df = fetch_daily(symbol, days=15)
    if daily_df.empty or len(daily_df) < 2:
        return None
    avg_vol_10d = float(daily_df["Volume"].tail(10).mean())
    rel_vol = relative_volume(current_volume, avg_vol_10d)

    # --- VWAP (today only) ---
    vwap_series = vwap(today_df)
    current_vwap = float(vwap_series.iloc[-1])

    # --- EMAs (on daily close) ---
    ema_9 = float(ema(daily_df["Close"], 9).iloc[-1])
    ema_20 = float(ema(daily_df["Close"], 20).iloc[-1])

    # --- RSI (daily) ---
    rsi_series = rsi(daily_df["Close"], 14)
    current_rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None

    # --- First 15-min candle ---
    first_candle = first_candle_range(today_df)

    return {
        "symbol": symbol,
        "prev_close": prev_close,
        "today_open": today_open,
        "current_price": current_price,
        "current_volume": current_volume,
        "gap_pct": round(gap_pct, 2),
        "rel_vol": round(rel_vol, 2),
        "vwap": round(current_vwap, 2),
        "price_above_vwap": current_price > current_vwap,
        "ema_9": round(ema_9, 2),
        "ema_20": round(ema_20, 2),
        "ema_bullish": ema_9 > ema_20,
        "rsi": round(current_rsi, 2) if current_rsi is not None else None,
        "first_candle_high": first_candle["high"],
        "first_candle_low": first_candle["low"],
        "first_candle_range": round(first_candle["range"], 2),
    }
