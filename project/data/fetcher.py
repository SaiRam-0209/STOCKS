"""Data fetcher using yfinance for NSE stocks."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

from project.data.symbols import ALL_STOCKS


def fetch_intraday(symbol: str, interval: str = "15m", period: str = "5d") -> pd.DataFrame:
    """Fetch intraday OHLCV data for a single stock.

    Args:
        symbol: Yahoo Finance ticker (e.g. "RELIANCE.NS")
        interval: Candle interval — "1m", "5m", "15m"
        period: Lookback period — "1d", "5d", etc.

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(interval=interval, period=period)
    if df.empty:
        return df
    df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def fetch_daily(symbol: str, days: int = 30, max_data: bool = False) -> pd.DataFrame:
    """Fetch daily OHLCV data for historical calculations.

    Args:
        symbol: Yahoo Finance ticker.
        days: Calendar days of history (ignored if max_data=True).
        max_data: If True, fetch ALL available history (can be 20+ years).
    """
    ticker = yf.Ticker(symbol)
    if max_data:
        df = ticker.history(period="max", interval="1d")
    else:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = ticker.history(start=start, end=end, interval="1d")
    if df.empty:
        return df
    df.index = df.index.tz_localize(None)
    return df[["Open", "High", "Low", "Close", "Volume"]]


def fetch_prev_close(symbol: str) -> float | None:
    """Get previous trading day's close price."""
    df = fetch_daily(symbol, days=5)
    if len(df) < 2:
        return None
    return float(df["Close"].iloc[-2])


def fetch_all_stocks(symbols: list[str] | None = None,
                     interval: str = "15m",
                     period: str = "5d") -> dict[str, pd.DataFrame]:
    """Fetch intraday data for all stocks in the universe.

    Returns:
        Dict mapping symbol -> DataFrame
    """
    if symbols is None:
        symbols = ALL_STOCKS

    results = {}
    for symbol in symbols:
        try:
            df = fetch_intraday(symbol, interval=interval, period=period)
            if not df.empty:
                results[symbol] = df
        except Exception as e:
            print(f"[WARN] Failed to fetch {symbol}: {e}")
    return results
