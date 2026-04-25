"""Feature-ablation backtest: do V2/V3 features help pick profitable stocks?

Trains three models on identical historical data:
    (A) Old:  30 features (BREAKOUT + EXTRA)
    (B) V2:   43 features (+ market-context + microstructure)
    (C) V3:   50 features (+ VIX, DII, delivery, OI, PCR, blocks, peers)

Walks forward chronologically, predicts the held-out tail, and compares:
    - Precision@top-K (did the high-ranked picks actually win?)
    - Avg return of top-K picks (the "max profit" metric the user asked for)
    - Profit factor, Sharpe proxy

Run:
    python -m project.backtest.ablation --symbols 500 --top_k 4
"""

from __future__ import annotations

import argparse
import logging

import numpy as np
import pandas as pd
import yfinance as yf

from project.ml.features import (
    BREAKOUT_FEATURE_COLUMNS,
    build_breakout_features_for_day,
)
from project.ml.features_v2 import V2_FEATURE_COLUMNS, build_v2_features
from project.ml.features_v3 import V3_FEATURE_COLUMNS, build_v3_features
from project.ml.win_classifier import EXTRA_FEATURES, WinClassifier
from project.data.nse_stocks import NSE_ALL_SYMBOLS

log = logging.getLogger(__name__)

BASE_FEATURES = BREAKOUT_FEATURE_COLUMNS + EXTRA_FEATURES
FULL_FEATURES = BASE_FEATURES + V2_FEATURE_COLUMNS
V3_FEATURES = FULL_FEATURES + V3_FEATURE_COLUMNS


def collect_samples(
    symbols: list[str],
    nifty_df: pd.DataFrame | None,
    gap_min: float = 2.0,
    vol_min: float = 1.5,
    price_min: float = 50.0,
    price_max: float = 10000.0,
) -> pd.DataFrame:
    """Walk every symbol's history and emit one row per qualifying gap day."""
    clf = WinClassifier()
    rows: list[dict] = []

    for sym in symbols:
        try:
            df = yf.download(sym + ".NS", period="2y", interval="1d", progress=False)
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.droplevel(1)
            if df is None or len(df) < 50:
                continue
        except Exception as exc:
            log.debug("fetch failed for %s: %s", sym, exc)
            continue

        closes = df["Close"].values
        opens = df["Open"].values

        for i in range(30, len(df) - 1):
            prev_close = closes[i - 1]
            if prev_close <= 0:
                continue
            open_px = opens[i]
            gap_pct = (open_px - prev_close) / prev_close * 100
            if abs(gap_pct) < gap_min:
                continue
            if open_px < price_min or open_px > price_max:
                continue

            avg_vol = float(df["Volume"].iloc[max(0, i - 10):i].mean())
            if avg_vol <= 0:
                continue
            rel_vol = float(df["Volume"].iloc[i]) / avg_vol
            if rel_vol < vol_min:
                continue

            base = build_breakout_features_for_day(df, i)
            extra = clf.build_extra_features(df, i)
            if base is None or extra is None:
                continue
            v2 = build_v2_features(df, i, nifty_df=nifty_df)

            trade_date = df.index[i]
            td = trade_date.date() if hasattr(trade_date, "date") else trade_date
            v3 = build_v3_features(sym, td, df, i)

            label = clf.build_win_label(df, i)
            fwd_return_pct = (float(closes[i]) - open_px) / open_px * 100

            row = {"date": df.index[i], "symbol": sym, "label": label,
                   "fwd_return_pct": fwd_return_pct, **base, **extra, **v2, **v3}
            rows.append(row)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def score_feature_set(
    samples: pd.DataFrame,
    feature_cols: list[str],
    test_frac: float = 0.3,
    top_k: int = 4,
) -> dict:
    """Train on the first (1-test_frac), predict on the tail, measure outcomes."""
    from xgboost import XGBClassifier

    n = len(samples)
    split = int(n * (1 - test_frac))
    train, test = samples.iloc[:split], samples.iloc[split:]

    if len(train) < 100 or len(test) < 50:
        return {"error": f"insufficient data (train={len(train)}, test={len(test)})"}

    X_train = train[feature_cols].values.astype(np.float32)
    y_train = train["label"].values.astype(np.int32)
    X_test = test[feature_cols].values.astype(np.float32)

    pos_weight = max(1.0, (len(y_train) - y_train.sum()) / max(y_train.sum(), 1))
    model = XGBClassifier(
        n_estimators=500, max_depth=4, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.7, min_child_weight=10,
        reg_alpha=0.2, reg_lambda=2.0, scale_pos_weight=pos_weight,
        tree_method="hist", eval_metric="logloss", random_state=42,
    )
    model.fit(X_train, y_train, verbose=False)
    probs = model.predict_proba(X_test)[:, 1]

    test_with_pred = test.assign(p_win=probs)
    daily_top_returns: list[float] = []
    daily_hit_rate: list[float] = []
    for _, group in test_with_pred.groupby("date"):
        picks = group.nlargest(top_k, "p_win")
        daily_top_returns.append(picks["fwd_return_pct"].mean())
        daily_hit_rate.append(picks["label"].mean())

    returns = np.array(daily_top_returns, dtype=np.float64)
    wins = returns[returns > 0]
    losses = returns[returns < 0]

    return {
        "n_train": len(train),
        "n_test": len(test),
        "n_test_days": len(daily_top_returns),
        "top_k": top_k,
        "avg_daily_return_pct": float(np.mean(returns)) if len(returns) else 0.0,
        "median_daily_return_pct": float(np.median(returns)) if len(returns) else 0.0,
        "hit_rate": float(np.mean(daily_hit_rate)) if daily_hit_rate else 0.0,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf"),
        "sharpe_proxy": float(np.mean(returns) / np.std(returns)) if np.std(returns) > 0 else 0.0,
        "best_day_pct": float(returns.max()) if len(returns) else 0.0,
        "worst_day_pct": float(returns.min()) if len(returns) else 0.0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", type=int, default=200)
    parser.add_argument("--top_k", type=int, default=4)
    parser.add_argument("--test_frac", type=float, default=0.3)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    symbols = NSE_ALL_SYMBOLS[: args.symbols]
    log.info("Fetching Nifty...")
    nifty = yf.download("^NSEI", period="2y", interval="1d", progress=False)
    if hasattr(nifty.columns, "levels"):
        nifty.columns = nifty.columns.droplevel(1)

    log.info("Collecting samples across %d symbols...", len(symbols))
    samples = collect_samples(symbols, nifty_df=nifty)
    log.info("Collected %d gap-day samples (win rate %.1f%%)",
             len(samples), samples["label"].mean() * 100 if len(samples) else 0)

    if len(samples) < 200:
        log.error("Not enough samples for ablation. Try --symbols 500+")
        return

    log.info("\n== Model A: BASE features (%d) ==", len(BASE_FEATURES))
    a = score_feature_set(samples, BASE_FEATURES, args.test_frac, args.top_k)
    log.info("  avg daily return: %+.2f%% | hit rate: %.1f%% | PF: %.2f | Sharpe: %.2f",
             a["avg_daily_return_pct"], a["hit_rate"] * 100,
             a["profit_factor"], a["sharpe_proxy"])

    log.info("\n== Model B: V2 features (%d) ==", len(FULL_FEATURES))
    b = score_feature_set(samples, FULL_FEATURES, args.test_frac, args.top_k)
    log.info("  avg daily return: %+.2f%% | hit rate: %.1f%% | PF: %.2f | Sharpe: %.2f",
             b["avg_daily_return_pct"], b["hit_rate"] * 100,
             b["profit_factor"], b["sharpe_proxy"])

    log.info("\n== Model C: V3 features (%d) ==", len(V3_FEATURES))
    c = score_feature_set(samples, V3_FEATURES, args.test_frac, args.top_k)
    log.info("  avg daily return: %+.2f%% | hit rate: %.1f%% | PF: %.2f | Sharpe: %.2f",
             c["avg_daily_return_pct"], c["hit_rate"] * 100,
             c["profit_factor"], c["sharpe_proxy"])

    log.info("\n== Lift: V2 over BASE ==")
    lift_b = b["avg_daily_return_pct"] - a["avg_daily_return_pct"]
    lift_pf_b = b["profit_factor"] - a["profit_factor"]
    log.info("  return: %+.2f pp/day | PF: %+.2f | hit-rate: %+.1f pp",
             lift_b, lift_pf_b, (b["hit_rate"] - a["hit_rate"]) * 100)

    log.info("\n== Lift: V3 over V2 ==")
    lift_c = c["avg_daily_return_pct"] - b["avg_daily_return_pct"]
    lift_pf_c = c["profit_factor"] - b["profit_factor"]
    log.info("  return: %+.2f pp/day | PF: %+.2f | hit-rate: %+.1f pp",
             lift_c, lift_pf_c, (c["hit_rate"] - b["hit_rate"]) * 100)

    if lift_c > 0.1 and lift_pf_c > 0:
        log.info("  ✅ V3 features help — keep them")
    elif lift_c < -0.1:
        log.info("  ❌ V3 features hurt — consider removing")
    else:
        log.info("  ➖ V3 features ~ neutral — re-evaluate after more data")


if __name__ == "__main__":
    main()
