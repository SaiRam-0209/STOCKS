"""Main entry point for the Intraday Stock Scanner."""

from __future__ import annotations

import sys

from project.data.fetcher import fetch_all_stocks, fetch_daily
from project.data.symbols import ALL_STOCKS
from project.features.builder import build_features
from project.strategy.filter import filter_and_rank
from project.strategy.signals import enrich_candidates
from project.backtest.engine import run_backtest
from project.output import print_results, save_to_csv


def scan(symbols: list[str] | None = None, top_n: int = 5, save: bool = True) -> list[dict]:
    """Run the full scan pipeline.

    1. Fetch intraday data for all stocks
    2. Build features for each stock
    3. Filter and rank by score
    4. Generate trade signals (entry/SL/target)
    5. Output results

    Args:
        symbols: List of tickers to scan (defaults to NIFTY 50).
        top_n: Number of top candidates to return.
        save: Whether to save results to CSV.

    Returns:
        List of enriched candidate dicts.
    """
    if symbols is None:
        symbols = ALL_STOCKS

    print(f"\n  Scanning {len(symbols)} stocks...")

    # Step 1: Fetch data
    print("  [1/4] Fetching intraday data...")
    stock_data = fetch_all_stocks(symbols)
    print(f"         Fetched {len(stock_data)} / {len(symbols)} stocks")

    # Step 2: Build features
    print("  [2/4] Computing features...")
    all_features = []
    for symbol, df in stock_data.items():
        features = build_features(symbol, df)
        if features is not None:
            all_features.append(features)
    print(f"         Computed features for {len(all_features)} stocks")

    # Step 3: Filter and rank
    print("  [3/4] Filtering and ranking...")
    candidates = filter_and_rank(all_features, top_n=top_n)
    print(f"         Found {len(candidates)} candidates")

    # Step 4: Generate trade signals
    print("  [4/4] Generating trade signals...")
    candidates = enrich_candidates(candidates)

    # Output
    print_results(candidates)
    if save and candidates:
        save_to_csv(candidates)

    return candidates


def backtest(symbols: list[str] | None = None) -> None:
    """Run backtest on historical data and print report.

    Uses ~60 days of intraday data available from yfinance.
    """
    if symbols is None:
        symbols = ALL_STOCKS

    print(f"\n  Running backtest on {len(symbols)} stocks...")

    # Fetch intraday (15m, max ~60 days) and daily data
    print("  [1/2] Fetching historical data...")
    stock_intraday = fetch_all_stocks(symbols, interval="15m", period="60d")
    stock_daily = {}
    for symbol in symbols:
        try:
            df = fetch_daily(symbol, days=90)
            if not df.empty:
                stock_daily[symbol] = df
        except Exception as e:
            print(f"  [WARN] Daily fetch failed for {symbol}: {e}")

    print(f"         Got intraday for {len(stock_intraday)}, daily for {len(stock_daily)} stocks")

    # Run backtest
    print("  [2/2] Simulating trades...")
    report = run_backtest(symbols, stock_intraday, stock_daily)
    print(report.summary())

    if report.wins + report.losses == 0:
        print("  ⚠ No trades were triggered. Consider relaxing filter thresholds.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        backtest()
    else:
        top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
        scan(top_n=top_n)
