"""Tests for the filtering engine."""

from project.strategy.filter import passes_primary_filters, compute_score, filter_and_rank


def _make_features(**overrides):
    """Create a feature dict with sensible defaults."""
    base = {
        "symbol": "TEST.NS",
        "gap_pct": 3.0,
        "rel_vol": 2.0,
        "price_above_vwap": True,
        "ema_bullish": True,
    }
    base.update(overrides)
    return base


def test_passes_primary_all_met():
    assert passes_primary_filters(_make_features()) is True


def test_fails_gap():
    assert passes_primary_filters(_make_features(gap_pct=1.0)) is False


def test_fails_volume():
    assert passes_primary_filters(_make_features(rel_vol=1.0)) is False


def test_fails_vwap():
    assert passes_primary_filters(_make_features(price_above_vwap=False)) is False


def test_gap_down_passes():
    # Gap down (negative) with abs >= 2% should pass
    assert passes_primary_filters(_make_features(gap_pct=-3.0)) is True


def test_score_max():
    assert compute_score(_make_features()) == 9


def test_score_partial():
    # Only gap met
    f = _make_features(rel_vol=1.0, price_above_vwap=False, ema_bullish=False)
    assert compute_score(f) == 2


def test_filter_and_rank():
    features_list = [
        _make_features(symbol="A.NS", gap_pct=5.0, rel_vol=3.0),  # score 9
        _make_features(symbol="B.NS", gap_pct=2.0, rel_vol=1.5, ema_bullish=False),  # score 7
        _make_features(symbol="C.NS", gap_pct=1.0),  # fails primary filter
    ]
    result = filter_and_rank(features_list, top_n=5)
    assert len(result) == 2
    assert result[0]["symbol"] == "A.NS"
    assert result[1]["symbol"] == "B.NS"
    assert result[0]["score"] >= result[1]["score"]
