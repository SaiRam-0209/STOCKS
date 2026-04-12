"""ML feature pipeline: combines technical, sentiment, and macro features."""

import numpy as np
import pandas as pd
from project.features.indicators import (
    gap_percentage, relative_volume, vwap, ema, rsi, atr,
)


def build_ml_features_for_day(daily_df: pd.DataFrame, day_idx: int,
                              sentiment_score: float = 0.0,
                              macro_score: float = 0.0,
                              sector_score: float = 0.0) -> dict | None:
    """Build a single feature vector for one stock on one day.

    Args:
        daily_df: Full daily OHLCV DataFrame for the stock.
        day_idx: Index position of the target day in daily_df.
        sentiment_score: News sentiment score (-1 to 1).
        macro_score: Global macro score (-10 to 10).
        sector_score: Sector rotation score.

    Returns:
        Dict of features, or None if insufficient data.
    """
    if day_idx < 20 or day_idx >= len(daily_df):
        return None

    row = daily_df.iloc[day_idx]
    prev = daily_df.iloc[day_idx - 1]

    close = float(row["Close"])
    prev_close = float(prev["Close"])
    volume = float(row["Volume"])

    # --- Price features ---
    gap_pct = gap_percentage(float(row["Open"]), prev_close)
    daily_return = ((close - prev_close) / prev_close) * 100
    daily_range = ((float(row["High"]) - float(row["Low"])) / prev_close) * 100

    # --- Volume features ---
    avg_vol_10 = float(daily_df["Volume"].iloc[day_idx - 10:day_idx].mean())
    avg_vol_5 = float(daily_df["Volume"].iloc[day_idx - 5:day_idx].mean())
    rel_vol = relative_volume(volume, avg_vol_10)
    vol_trend = (avg_vol_5 / avg_vol_10) if avg_vol_10 > 0 else 1.0

    # --- Moving averages ---
    close_series = daily_df["Close"].iloc[:day_idx + 1]
    ema_9 = float(ema(close_series, 9).iloc[-1])
    ema_20 = float(ema(close_series, 20).iloc[-1])
    ema_50 = float(ema(close_series, 50).iloc[-1]) if day_idx >= 50 else ema_20
    sma_20 = float(close_series.tail(20).mean())

    price_vs_ema9 = ((close - ema_9) / ema_9) * 100
    price_vs_ema20 = ((close - ema_20) / ema_20) * 100
    ema_bullish = 1.0 if ema_9 > ema_20 else 0.0

    # --- VWAP proxy (using daily typical price) ---
    tp = (float(row["High"]) + float(row["Low"]) + close) / 3
    above_tp = 1.0 if close > tp else 0.0

    # --- RSI ---
    rsi_series = rsi(close_series, 14)
    current_rsi = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 else 50.0

    # --- ATR (volatility) ---
    atr_series = atr(daily_df.iloc[:day_idx + 1], 14)
    current_atr = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0.0
    atr_pct = (current_atr / close) * 100 if close > 0 else 0.0

    # --- Momentum features ---
    returns_5d = ((close - float(daily_df["Close"].iloc[day_idx - 5])) /
                  float(daily_df["Close"].iloc[day_idx - 5])) * 100
    returns_10d = ((close - float(daily_df["Close"].iloc[day_idx - 10])) /
                   float(daily_df["Close"].iloc[day_idx - 10])) * 100

    # --- Pattern features ---
    # Count green/red days in last 5
    last_5_returns = []
    for j in range(1, 6):
        if day_idx - j >= 0:
            c = float(daily_df["Close"].iloc[day_idx - j + 1])
            p = float(daily_df["Close"].iloc[day_idx - j])
            last_5_returns.append(1 if c > p else 0)
    green_days_5 = sum(last_5_returns)

    # Higher highs / higher lows (trend)
    highs = [float(daily_df["High"].iloc[day_idx - i]) for i in range(3)]
    lows = [float(daily_df["Low"].iloc[day_idx - i]) for i in range(3)]
    higher_highs = 1.0 if highs[0] > highs[1] > highs[2] else 0.0
    higher_lows = 1.0 if lows[0] > lows[1] > lows[2] else 0.0

    return {
        # Price
        "gap_pct": round(gap_pct, 4),
        "daily_return": round(daily_return, 4),
        "daily_range": round(daily_range, 4),
        # Volume
        "rel_vol": round(rel_vol, 4),
        "vol_trend": round(vol_trend, 4),
        # Moving averages
        "price_vs_ema9": round(price_vs_ema9, 4),
        "price_vs_ema20": round(price_vs_ema20, 4),
        "ema_bullish": ema_bullish,
        # RSI / ATR
        "rsi": round(current_rsi, 4),
        "atr_pct": round(atr_pct, 4),
        # Momentum
        "returns_5d": round(returns_5d, 4),
        "returns_10d": round(returns_10d, 4),
        "green_days_5": green_days_5,
        # Patterns
        "higher_highs": higher_highs,
        "higher_lows": higher_lows,
        "above_typical_price": above_tp,
        # External
        "sentiment_score": round(sentiment_score, 4),
        "macro_score": round(macro_score, 4),
        "sector_score": round(sector_score, 4),
    }


FEATURE_COLUMNS = [
    "gap_pct", "daily_return", "daily_range", "rel_vol", "vol_trend",
    "price_vs_ema9", "price_vs_ema20", "ema_bullish", "rsi", "atr_pct",
    "returns_5d", "returns_10d", "green_days_5", "higher_highs", "higher_lows",
    "above_typical_price", "sentiment_score", "macro_score", "sector_score",
]


def build_training_data(daily_df: pd.DataFrame,
                        sentiment_score: float = 0.0,
                        macro_score: float = 0.0,
                        sector_score: float = 0.0,
                        target_horizon: int = 1,
                        boom_threshold: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """Build training dataset from historical daily data.

    For each day, features are computed from data up to that day,
    and the label is whether the stock "boomed" (gained >= threshold%)
    in the next `target_horizon` days.

    Args:
        daily_df: Historical daily OHLCV data.
        sentiment_score: Default sentiment (0 for historical).
        macro_score: Default macro score (0 for historical).
        sector_score: Default sector score (0 for historical).
        target_horizon: Number of days forward to check.
        boom_threshold: Min % gain to classify as "boom".

    Returns:
        (X, y) where X is feature matrix, y is binary labels.
    """
    features_list = []
    labels = []

    for i in range(20, len(daily_df) - target_horizon):
        feat = build_ml_features_for_day(daily_df, i, sentiment_score,
                                          macro_score, sector_score)
        if feat is None:
            continue

        # Label: did stock gain >= threshold% in next N days?
        current_close = float(daily_df["Close"].iloc[i])
        future_high = float(daily_df["High"].iloc[i + 1:i + 1 + target_horizon].max())
        future_return = ((future_high - current_close) / current_close) * 100

        row = [feat[col] for col in FEATURE_COLUMNS]
        # Skip rows with any NaN/inf — these come from insufficient history
        if any(v != v or abs(v) == float('inf') for v in row):
            continue
        features_list.append(row)
        labels.append(1 if future_return >= boom_threshold else 0)

    return np.array(features_list), np.array(labels)
