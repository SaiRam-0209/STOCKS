"""Technical indicator calculations for feature engineering."""

import pandas as pd
import numpy as np


def gap_percentage(today_open: float, prev_close: float) -> float:
    """Calculate gap percentage between today's open and previous close."""
    if prev_close == 0:
        return 0.0
    return ((today_open - prev_close) / prev_close) * 100


def relative_volume(current_volume: float, avg_volume_10d: float) -> float:
    """Calculate relative volume vs 10-day average."""
    if avg_volume_10d == 0:
        return 0.0
    return current_volume / avg_volume_10d


def vwap(df: pd.DataFrame) -> pd.Series:
    """Calculate intraday VWAP (resets daily).

    Args:
        df: DataFrame with Open, High, Low, Close, Volume columns.
            Index must be DatetimeIndex.

    Returns:
        Series of VWAP values aligned to df index.
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    tp_volume = typical_price * df["Volume"]

    # Group by date so VWAP resets each day
    dates = df.index.date
    cum_tp_vol = tp_volume.groupby(dates).cumsum()
    cum_vol = df["Volume"].groupby(dates).cumsum()

    result = cum_tp_vol / cum_vol
    result = result.replace([np.inf, -np.inf], np.nan).fillna(typical_price)
    return result


def ema(series: pd.Series, span: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift(1)).abs()
    low_close = (df["Low"] - df["Close"].shift(1)).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(window=period).mean()


def first_candle_range(df_today: pd.DataFrame) -> dict:
    """Extract the first 15-min candle's high and low for today's session.

    Args:
        df_today: Intraday DataFrame for today only (15m interval).

    Returns:
        Dict with 'high', 'low', 'range' of the first candle.
    """
    if df_today.empty:
        return {"high": 0.0, "low": 0.0, "range": 0.0}

    first = df_today.iloc[0]
    return {
        "high": float(first["High"]),
        "low": float(first["Low"]),
        "range": float(first["High"] - first["Low"]),
    }
