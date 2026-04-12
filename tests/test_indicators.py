"""Tests for feature engineering indicators."""

import pandas as pd
import numpy as np
from project.features.indicators import (
    gap_percentage, relative_volume, vwap, ema, rsi, first_candle_range,
)


def test_gap_percentage():
    assert gap_percentage(102, 100) == 2.0
    assert gap_percentage(98, 100) == -2.0
    assert gap_percentage(100, 100) == 0.0
    assert gap_percentage(100, 0) == 0.0  # edge case


def test_relative_volume():
    assert relative_volume(150, 100) == 1.5
    assert relative_volume(0, 100) == 0.0
    assert relative_volume(100, 0) == 0.0  # edge case


def test_vwap():
    idx = pd.date_range("2024-01-01 09:15", periods=4, freq="15min")
    df = pd.DataFrame({
        "High":   [105, 107, 106, 108],
        "Low":    [100, 102, 101, 103],
        "Close":  [103, 105, 104, 106],
        "Volume": [1000, 1500, 1200, 1800],
    }, index=idx)
    result = vwap(df)
    assert len(result) == 4
    assert not result.isna().any()
    # VWAP should be between low and high
    assert result.iloc[-1] >= 100
    assert result.iloc[-1] <= 108


def test_ema():
    series = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    ema_5 = ema(series, 5)
    assert len(ema_5) == 10
    # EMA should lag behind the raw values
    assert ema_5.iloc[-1] < 10
    assert ema_5.iloc[-1] > 5


def test_rsi():
    # Trending up → RSI should be high
    series = pd.Series(range(1, 30))
    result = rsi(series, 14)
    assert result.iloc[-1] > 70  # strongly bullish


def test_first_candle_range():
    idx = pd.date_range("2024-01-01 09:15", periods=3, freq="15min")
    df = pd.DataFrame({
        "Open": [100, 105, 108],
        "High": [110, 115, 112],
        "Low": [98, 102, 106],
        "Close": [105, 108, 110],
        "Volume": [1000, 1500, 1200],
    }, index=idx)
    result = first_candle_range(df)
    assert result["high"] == 110
    assert result["low"] == 98
    assert result["range"] == 12

    # Empty DataFrame
    empty = first_candle_range(pd.DataFrame())
    assert empty["range"] == 0.0
