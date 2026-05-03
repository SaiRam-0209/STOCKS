"""Tests for resilient symbol loading."""

from project.data import symbols_fetcher


def test_get_all_nse_stocks_uses_baked_fallback(monkeypatch):
    monkeypatch.setattr(symbols_fetcher, "fetch_all_nse_symbols", lambda: [])

    result = symbols_fetcher.get_all_nse_stocks()

    assert len(result) > 500
    assert all(symbol.endswith(".NS") for symbol in result[:20])
