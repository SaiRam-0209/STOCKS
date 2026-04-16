"""V2 features — the gaps identified vs. "what actually moves a stock".

Three groups added here:
    1. Market-context features (stock vs. Nifty)  — fixes "model sees stock in isolation"
    2. Liquidity / microstructure features         — fixes "no spread/ADV/circuit awareness"
    3. Prev-candle wick geometry                   — fixes "doesn't see failed moves"

All inputs are OHLCV-derivable; no external data fetches required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


V2_FEATURE_COLUMNS = [
    # Market context (stock vs Nifty)
    "stock_vs_nifty_1d",      # today's return minus nifty return (pct pts)
    "stock_vs_nifty_5d",      # 5-day relative strength
    "stock_vs_nifty_20d",     # 20-day relative strength
    "beta_60d",               # regression slope vs nifty, 60d
    "corr_nifty_20d",         # correlation with nifty, 20d
    "nifty_trend_5d",         # nifty's own 5-day move (regime signal)
    # Liquidity / microstructure
    "avg_daily_value_cr",     # avg(close*volume) over 20d in crores
    "liquidity_rank_20d",     # liquidity percentile within own history (0-1)
    "spread_proxy_bps",       # (high-low)/close as bps — intraday range proxy
    "circuit_distance_pct",   # min(%up, %down) from 20% daily move cap
    "range_expansion_5d",     # today's range / avg 5d range
    # Prev-candle geometry (failed-move detection)
    "upper_wick_ratio_prev",  # upper wick / total range of prev candle
    "lower_wick_ratio_prev",  # lower wick / total range of prev candle
]


def build_v2_features(
    daily_df: pd.DataFrame,
    day_idx: int,
    nifty_df: pd.DataFrame | None = None,
) -> dict:
    """Compute V2 features for a single day.

    `nifty_df` should be a daily-OHLCV DataFrame for ^NSEI aligned by date.
    If absent, nifty-dependent features fall back to neutral defaults (0.0).
    """
    if day_idx < 2 or day_idx >= len(daily_df):
        return _defaults()

    row = daily_df.iloc[day_idx]
    prev = daily_df.iloc[day_idx - 1]
    today_high = float(row["High"])
    today_low = float(row["Low"])
    today_close = float(row["Close"])
    prev_close = float(prev["Close"])
    prev_open = float(prev["Open"])
    prev_high = float(prev["High"])
    prev_low = float(prev["Low"])

    today_return = (today_close - prev_close) / prev_close * 100 if prev_close > 0 else 0.0

    # ── Market-context features ──────────────────────────────────────
    nifty_feats = _nifty_relative(daily_df, day_idx, nifty_df, today_return)

    # ── Liquidity / structure ────────────────────────────────────────
    window = daily_df.iloc[max(0, day_idx - 20):day_idx]
    if len(window) >= 5:
        daily_value = window["Close"] * window["Volume"]
        avg_value_cr = float(daily_value.mean()) / 1e7  # rupees → crores
        today_value = today_close * float(row["Volume"])
        liquidity_rank = float((daily_value <= today_value).mean())
    else:
        avg_value_cr = 0.0
        liquidity_rank = 0.5

    spread_proxy_bps = ((today_high - today_low) / today_close * 10_000) if today_close > 0 else 0.0

    # NSE default circuit is ±20% for most stocks vs prev close
    pct_up = (today_high - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
    pct_down = (prev_close - today_low) / prev_close * 100 if prev_close > 0 else 0.0
    circuit_distance_pct = 20.0 - max(pct_up, pct_down)

    today_range = today_high - today_low
    if day_idx >= 6:
        recent = daily_df.iloc[day_idx - 5:day_idx]
        avg_range = float((recent["High"] - recent["Low"]).mean())
        range_expansion_5d = today_range / avg_range if avg_range > 0 else 1.0
    else:
        range_expansion_5d = 1.0

    # ── Prev-candle wick geometry ────────────────────────────────────
    prev_range = prev_high - prev_low
    if prev_range > 0:
        body_top = max(prev_open, prev_close)
        body_bottom = min(prev_open, prev_close)
        upper_wick_ratio_prev = (prev_high - body_top) / prev_range
        lower_wick_ratio_prev = (body_bottom - prev_low) / prev_range
    else:
        upper_wick_ratio_prev = 0.0
        lower_wick_ratio_prev = 0.0

    return {
        **nifty_feats,
        "avg_daily_value_cr": round(avg_value_cr, 4),
        "liquidity_rank_20d": round(liquidity_rank, 4),
        "spread_proxy_bps": round(spread_proxy_bps, 2),
        "circuit_distance_pct": round(circuit_distance_pct, 4),
        "range_expansion_5d": round(range_expansion_5d, 4),
        "upper_wick_ratio_prev": round(upper_wick_ratio_prev, 4),
        "lower_wick_ratio_prev": round(lower_wick_ratio_prev, 4),
    }


def _nifty_relative(
    daily_df: pd.DataFrame,
    day_idx: int,
    nifty_df: pd.DataFrame | None,
    today_return: float,
) -> dict:
    if nifty_df is None or len(nifty_df) < 20:
        return {
            "stock_vs_nifty_1d": 0.0,
            "stock_vs_nifty_5d": 0.0,
            "stock_vs_nifty_20d": 0.0,
            "beta_60d": 1.0,
            "corr_nifty_20d": 0.0,
            "nifty_trend_5d": 0.0,
        }

    trade_date = daily_df.index[day_idx]
    nifty_slice = nifty_df[nifty_df.index <= trade_date]
    if len(nifty_slice) < 20:
        return {
            "stock_vs_nifty_1d": 0.0, "stock_vs_nifty_5d": 0.0,
            "stock_vs_nifty_20d": 0.0, "beta_60d": 1.0,
            "corr_nifty_20d": 0.0, "nifty_trend_5d": 0.0,
        }

    n_close = nifty_slice["Close"].values
    n_today = float(n_close[-1])
    n_prev = float(n_close[-2])
    nifty_1d = (n_today - n_prev) / n_prev * 100 if n_prev > 0 else 0.0

    n_5d_ago = float(n_close[-6]) if len(n_close) >= 6 else n_prev
    nifty_5d = (n_today - n_5d_ago) / n_5d_ago * 100 if n_5d_ago > 0 else 0.0

    n_20d_ago = float(n_close[-21]) if len(n_close) >= 21 else n_5d_ago
    nifty_20d = (n_today - n_20d_ago) / n_20d_ago * 100 if n_20d_ago > 0 else 0.0

    # Stock N-day returns
    s_close = daily_df["Close"].values
    s_today = float(s_close[day_idx])
    s_5d_ago = float(s_close[day_idx - 5]) if day_idx >= 5 else float(s_close[0])
    s_20d_ago = float(s_close[day_idx - 20]) if day_idx >= 20 else float(s_close[0])
    stock_5d = (s_today - s_5d_ago) / s_5d_ago * 100 if s_5d_ago > 0 else 0.0
    stock_20d = (s_today - s_20d_ago) / s_20d_ago * 100 if s_20d_ago > 0 else 0.0

    # Beta + correlation (60d) — aligned returns
    lookback = min(60, day_idx, len(nifty_slice) - 1)
    if lookback >= 20:
        s_rets = np.diff(s_close[day_idx - lookback:day_idx + 1]) / s_close[day_idx - lookback:day_idx]
        n_rets = np.diff(n_close[-lookback - 1:]) / n_close[-lookback - 1:-1]
        # Guard for length mismatch from calendar misalignment
        m = min(len(s_rets), len(n_rets))
        if m >= 20 and np.std(n_rets[-m:]) > 0:
            beta = float(np.cov(s_rets[-m:], n_rets[-m:])[0, 1] / np.var(n_rets[-m:]))
            corr = float(np.corrcoef(s_rets[-m:], n_rets[-m:])[0, 1])
        else:
            beta, corr = 1.0, 0.0
    else:
        beta, corr = 1.0, 0.0

    return {
        "stock_vs_nifty_1d": round(today_return - nifty_1d, 4),
        "stock_vs_nifty_5d": round(stock_5d - nifty_5d, 4),
        "stock_vs_nifty_20d": round(stock_20d - nifty_20d, 4),
        "beta_60d": round(beta, 4) if np.isfinite(beta) else 1.0,
        "corr_nifty_20d": round(corr, 4) if np.isfinite(corr) else 0.0,
        "nifty_trend_5d": round(nifty_5d, 4),
    }


def _defaults() -> dict:
    return {k: 0.0 for k in V2_FEATURE_COLUMNS} | {"beta_60d": 1.0, "circuit_distance_pct": 20.0}
