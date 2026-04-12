"""Tests for the strategy / signal engine."""

from project.strategy.signals import generate_trade_signal


def test_long_signal():
    features = {
        "first_candle_high": 110,
        "first_candle_low": 100,
        "gap_pct": 3.0,
    }
    signal = generate_trade_signal(features)
    assert signal["direction"] == "LONG"
    assert signal["entry"] == 110
    assert signal["stoploss"] == 100
    assert signal["risk"] == 10
    assert signal["target"] == 130  # entry + 2*risk
    assert signal["reward"] == 20


def test_short_signal():
    features = {
        "first_candle_high": 110,
        "first_candle_low": 100,
        "gap_pct": -3.0,
    }
    signal = generate_trade_signal(features)
    assert signal["direction"] == "SHORT"
    assert signal["entry"] == 100
    assert signal["stoploss"] == 110
    assert signal["risk"] == 10
    assert signal["target"] == 80  # entry - 2*risk
    assert signal["reward"] == 20
