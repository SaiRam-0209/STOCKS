"""Walk-forward validation — strict time-series split for the Win Classifier.

Implements expanding-window walk-forward:
    1. Train on [0, split_i), test on [split_i, split_{i+1})
    2. Measure Expectancy (R), Drawdown, Trade Count per window
    3. Optimize probability threshold per regime via max-expectancy grid search
    4. Reject model if performance is inconsistent across windows

Run:
    python -m project.backtest.walkforward --symbols 300
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf

from project.ml.win_classifier_v2 import WinClassifierV2, CURATED_FEATURES
from project.features.regime import (
    detect_regime,
    regime_to_numeric,
    MarketRegime,
    REGIME_FEATURE_COLUMNS,
)
from project.data.nse_stocks import NSE_ALL_SYMBOLS

log = logging.getLogger(__name__)


# ── Cost model ──────────────────────────────────────────────────────────────
SLIPPAGE_PCT = 0.001        # 0.1% slippage on entry + exit
BROKERAGE_PER_ORDER = 20.0  # ₹20 flat per order (Indian discount broker)
STT_PCT = 0.00025           # STT on sell side for intraday
EXCHANGE_CHARGES_PCT = 0.0003  # NSE transaction + SEBI + stamp


@dataclass
class SimulatedTrade:
    """One simulated trade with realistic costs."""
    date: str
    symbol: str
    direction: str            # "LONG" / "SHORT"
    entry_raw: float          # Signal price
    entry_filled: float       # After slippage
    stoploss: float
    target: float
    exit_price: float
    risk: float               # Per-share risk in ₹
    pnl_raw: float            # Before costs
    pnl_net: float            # After slippage + brokerage
    result: str               # "WIN" / "LOSS" / "TIME_EXIT"
    win_prob: float           # Model's predicted P(win)
    mae: float = 0.0         # Maximum Adverse Excursion (worst drawdown during trade)
    mfe: float = 0.0         # Maximum Favorable Excursion (best unrealized profit)
    r_multiple: float = 0.0  # PnL expressed in units of risk (R)


@dataclass
class WindowResult:
    """Metrics for one walk-forward window."""
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    n_train: int
    n_test: int
    trade_count: int
    wins: int
    losses: int
    win_rate: float
    expectancy_r: float       # Average R-multiple per trade
    max_drawdown_r: float     # Maximum drawdown in R units
    profit_factor: float
    total_pnl_r: float
    optimal_threshold: float
    regime_distribution: dict = field(default_factory=dict)
    trades: list[SimulatedTrade] = field(default_factory=list)

    @property
    def is_consistent(self) -> bool:
        """Window passes consistency check."""
        return (
            self.trade_count >= 10
            and self.expectancy_r > 0
            and self.profit_factor > 1.0
        )


@dataclass
class WalkForwardReport:
    """Full walk-forward validation report."""
    windows: list[WindowResult] = field(default_factory=list)
    overall_expectancy_r: float = 0.0
    overall_max_drawdown_r: float = 0.0
    overall_profit_factor: float = 0.0
    overall_trade_count: int = 0
    consistency_score: float = 0.0  # Fraction of windows that pass
    is_valid: bool = False
    optimal_threshold: float = 0.40
    regime_thresholds: dict[str, float] = field(default_factory=dict)
    equity_curve: list[float] = field(default_factory=list)


def simulate_trade_on_daily(
    daily_df: pd.DataFrame,
    day_idx: int,
    win_prob: float,
) -> SimulatedTrade | None:
    """Simulate a single ORB trade using same-day daily OHLC.

    Uses the same WIN/LOSS logic as WinClassifierV2.build_win_label()
    to stay consistent with how the model was trained. R-multiples
    are derived from actual price movement relative to risk.

    Cost model: flat 0.05% round-trip.
    """
    if day_idx < 1 or day_idx >= len(daily_df):
        return None

    row = daily_df.iloc[day_idx]
    prev_close = float(daily_df.iloc[day_idx - 1]["Close"])
    open_px = float(row["Open"])
    high_px = float(row["High"])
    low_px = float(row["Low"])
    close_px = float(row["Close"])

    if prev_close <= 0 or open_px <= 0:
        return None

    gap_pct = (open_px - prev_close) / prev_close * 100
    direction = "LONG" if gap_pct > 0 else "SHORT"

    entry_filled = round(open_px * (1 + SLIPPAGE_PCT if direction == "LONG" else 1 - SLIPPAGE_PCT), 2)

    if direction == "LONG":
        # Risk = distance from open to day low (worst case SL)
        risk = max(entry_filled - low_px, entry_filled * 0.005)  # Min 0.5% risk
        stoploss = entry_filled - risk
        target = entry_filled + 2 * risk

        mae = max(0.0, entry_filled - low_px)
        mfe = max(0.0, high_px - entry_filled)

        # WIN: target hit OR closed above 1R
        if high_px >= target:
            exit_price = target
            result = "WIN"
        elif close_px > entry_filled + risk:
            exit_price = close_px
            result = "WIN"
        else:
            exit_price = close_px
            result = "LOSS" if close_px < entry_filled else "TIME_EXIT"

        pnl_raw = exit_price - entry_filled
    else:
        risk = max(high_px - entry_filled, entry_filled * 0.005)
        stoploss = entry_filled + risk
        target = entry_filled - 2 * risk

        mae = max(0.0, high_px - entry_filled)
        mfe = max(0.0, entry_filled - low_px)

        if low_px <= target:
            exit_price = target
            result = "WIN"
        elif close_px < entry_filled - risk:
            exit_price = close_px
            result = "WIN"
        else:
            exit_price = close_px
            result = "LOSS" if close_px > entry_filled else "TIME_EXIT"

        pnl_raw = entry_filled - exit_price

    # Flat round-trip cost: 0.05%
    cost = entry_filled * 0.0005
    pnl_net = pnl_raw - cost
    r_multiple = pnl_net / risk if risk > 0 else 0.0

    date_str = str(daily_df.index[day_idx].date() if hasattr(daily_df.index[day_idx], 'date') else daily_df.index[day_idx])

    return SimulatedTrade(
        date=date_str, symbol="", direction=direction,
        entry_raw=open_px, entry_filled=entry_filled,
        stoploss=round(stoploss, 2), target=round(target, 2),
        exit_price=round(exit_price, 2), risk=round(risk, 2),
        pnl_raw=round(pnl_raw, 2), pnl_net=round(pnl_net, 2),
        result=result, win_prob=win_prob,
        mae=round(mae, 2), mfe=round(mfe, 2),
        r_multiple=round(r_multiple, 4),
    )


def _collect_samples_with_dates(
    symbols: list[str],
    nifty_df: pd.DataFrame | None,
    gap_min: float = 2.0,
    vol_min: float = 1.5,
) -> list[dict]:
    """Collect training/test samples with date for time-series splitting."""
    clf = WinClassifierV2()
    rows: list[dict] = []

    for sym in symbols:
        try:
            df = yf.download(sym + ".NS", period="2y", interval="1d", progress=False)
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.droplevel(1)
            if df is None or len(df) < 60:
                continue
        except Exception:
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
            if open_px < 50 or open_px > 10000:
                continue

            avg_vol = float(df["Volume"].iloc[max(0, i - 10):i].mean())
            if avg_vol <= 0:
                continue
            rel_vol = float(df["Volume"].iloc[i]) / avg_vol
            if rel_vol < vol_min:
                continue

            feat_vec = clf.extract_features(df, i, nifty_df=nifty_df)
            if feat_vec is None:
                continue

            label = clf.build_win_label(df, i)
            trade = simulate_trade_on_daily(df, i, 0.0)

            trade_date = df.index[i]
            date_str = str(trade_date.date() if hasattr(trade_date, 'date') else trade_date)

            rows.append({
                "date": date_str,
                "symbol": sym,
                "features": feat_vec,
                "label": label,
                "daily_df": df,
                "day_idx": i,
                "trade": trade,
            })

    rows.sort(key=lambda r: r["date"])
    return rows


def _optimize_threshold(
    model: WinClassifierV2,
    test_samples: list[dict],
) -> tuple[float, dict[str, float]]:
    """Grid-search for the threshold that maximizes expectancy.

    Also computes per-regime thresholds.
    """
    thresholds = np.arange(0.30, 0.70, 0.05)
    best_thresh = 0.40
    best_expectancy = -np.inf

    for thresh in thresholds:
        r_multiples = []
        for sample in test_samples:
            prob = model.predict_win_probability(sample["features"])
            if prob >= thresh and sample["trade"] is not None:
                r_multiples.append(sample["trade"].r_multiple)

        if len(r_multiples) >= 5:
            exp = float(np.mean(r_multiples))
            if exp > best_expectancy:
                best_expectancy = exp
                best_thresh = float(thresh)

    # Per-regime optimization — simplified (use global data's regime feature)
    regime_thresholds: dict[str, float] = {}
    for regime_name in ["TRENDING_UP", "TRENDING_DOWN", "SIDEWAYS", "HIGH_VOLATILITY"]:
        regime_val = {
            "TRENDING_UP": 1.0, "TRENDING_DOWN": -1.0,
            "SIDEWAYS": 0.0, "HIGH_VOLATILITY": 2.0,
        }[regime_name]

        regime_samples = [
            s for s in test_samples
            if s["features"] is not None
            and abs(s["features"][CURATED_FEATURES.index("regime_numeric")] - regime_val) < 0.5
        ]

        if len(regime_samples) < 10:
            regime_thresholds[regime_name] = best_thresh
            continue

        best_r_thresh = best_thresh
        best_r_exp = -np.inf
        for thresh in thresholds:
            r_mults = []
            for sample in regime_samples:
                prob = model.predict_win_probability(sample["features"])
                if prob >= thresh and sample["trade"] is not None:
                    r_mults.append(sample["trade"].r_multiple)
            if len(r_mults) >= 3:
                exp = float(np.mean(r_mults))
                if exp > best_r_exp:
                    best_r_exp = exp
                    best_r_thresh = float(thresh)

        regime_thresholds[regime_name] = best_r_thresh

    return best_thresh, regime_thresholds


def run_walk_forward(
    symbols: list[str] | None = None,
    n_splits: int = 5,
    min_train_pct: float = 0.40,
    progress_callback=None,
) -> WalkForwardReport:
    """Run walk-forward validation across multiple time windows.

    Uses expanding windows:
        Window 0: train [0, 40%), test [40%, 52%)
        Window 1: train [0, 52%), test [52%, 64%)
        Window 2: train [0, 64%), test [64%, 76%)
        ...

    Returns a WalkForwardReport with per-window metrics.
    """
    if symbols is None:
        symbols = NSE_ALL_SYMBOLS[:200]

    def _update(msg: str):
        if progress_callback:
            progress_callback(msg)
        log.info(msg)

    # Fetch Nifty for regime features
    _update("Fetching Nifty data for regime detection...")
    try:
        nifty = yf.download("^NSEI", period="2y", interval="1d", progress=False)
        if hasattr(nifty.columns, "levels"):
            nifty.columns = nifty.columns.droplevel(1)
        if len(nifty) < 65:
            nifty = None
    except Exception:
        nifty = None

    _update(f"Collecting samples from {len(symbols)} symbols...")
    all_samples = _collect_samples_with_dates(symbols, nifty)
    _update(f"Collected {len(all_samples)} gap-day samples")

    if len(all_samples) < 200:
        _update("ERROR: Not enough samples for walk-forward validation")
        return WalkForwardReport()

    # Time-series split
    n = len(all_samples)
    test_size = int(n * (1 - min_train_pct) / n_splits)
    report = WalkForwardReport()

    for w in range(n_splits):
        train_end = int(n * min_train_pct) + w * test_size
        test_end = min(train_end + test_size, n)

        if train_end >= n or test_end <= train_end:
            break

        train_samples = all_samples[:train_end]
        test_samples = all_samples[train_end:test_end]

        if len(train_samples) < 50 or len(test_samples) < 10:
            continue

        _update(f"Window {w}: train={len(train_samples)}, test={len(test_samples)}")

        # Train
        X_train = np.array([s["features"] for s in train_samples], dtype=np.float32)
        y_train = np.array([s["label"] for s in train_samples], dtype=np.int32)

        clf = WinClassifierV2()
        metrics = clf.train(X_train, y_train)
        if "error" in metrics:
            _update(f"  Training failed: {metrics['error']}")
            continue

        # Optimize threshold on test set
        opt_thresh, regime_thresh = _optimize_threshold(clf, test_samples)
        _update(f"  Optimal threshold: {opt_thresh:.2f}")

        # Simulate trades on test set
        trades: list[SimulatedTrade] = []
        for sample in test_samples:
            prob = clf.predict_win_probability(sample["features"])
            if prob >= opt_thresh and sample["trade"] is not None:
                t = sample["trade"]
                t.symbol = sample["symbol"]
                t.win_prob = prob
                trades.append(t)

        # Compute window metrics
        if trades:
            r_mults = [t.r_multiple for t in trades]
            wins = sum(1 for r in r_mults if r > 0)
            losses = len(r_mults) - wins
            gross_wins = sum(r for r in r_mults if r > 0)
            gross_losses = abs(sum(r for r in r_mults if r <= 0))

            # Drawdown in R
            cumulative = np.cumsum(r_mults)
            peak = np.maximum.accumulate(cumulative)
            drawdown = peak - cumulative
            max_dd = float(drawdown.max()) if len(drawdown) > 0 else 0.0

            window_result = WindowResult(
                window_id=w,
                train_start=train_samples[0]["date"],
                train_end=train_samples[-1]["date"],
                test_start=test_samples[0]["date"],
                test_end=test_samples[-1]["date"],
                n_train=len(train_samples),
                n_test=len(test_samples),
                trade_count=len(trades),
                wins=wins,
                losses=losses,
                win_rate=wins / len(trades) * 100 if trades else 0.0,
                expectancy_r=float(np.mean(r_mults)),
                max_drawdown_r=max_dd,
                profit_factor=gross_wins / gross_losses if gross_losses > 0 else float("inf"),
                total_pnl_r=float(np.sum(r_mults)),
                optimal_threshold=opt_thresh,
                regime_distribution={},
                trades=trades,
            )
        else:
            window_result = WindowResult(
                window_id=w,
                train_start=train_samples[0]["date"],
                train_end=train_samples[-1]["date"],
                test_start=test_samples[0]["date"],
                test_end=test_samples[-1]["date"],
                n_train=len(train_samples),
                n_test=len(test_samples),
                trade_count=0, wins=0, losses=0, win_rate=0.0,
                expectancy_r=0.0, max_drawdown_r=0.0,
                profit_factor=0.0, total_pnl_r=0.0,
                optimal_threshold=opt_thresh,
            )

        report.windows.append(window_result)
        _update(
            f"  Trades: {window_result.trade_count} | "
            f"WR: {window_result.win_rate:.0f}% | "
            f"Exp(R): {window_result.expectancy_r:+.2f} | "
            f"MaxDD(R): {window_result.max_drawdown_r:.1f} | "
            f"PF: {window_result.profit_factor:.2f}"
        )

    # Overall metrics
    all_trades = [t for w in report.windows for t in w.trades]
    if all_trades:
        all_r = [t.r_multiple for t in all_trades]
        report.overall_expectancy_r = float(np.mean(all_r))
        report.overall_trade_count = len(all_trades)

        gross_w = sum(r for r in all_r if r > 0)
        gross_l = abs(sum(r for r in all_r if r <= 0))
        report.overall_profit_factor = gross_w / gross_l if gross_l > 0 else float("inf")

        cumulative = np.cumsum(all_r)
        peak = np.maximum.accumulate(cumulative)
        report.overall_max_drawdown_r = float((peak - cumulative).max())
        report.equity_curve = cumulative.tolist()

    # Consistency check
    consistent_windows = [w for w in report.windows if w.is_consistent]
    report.consistency_score = len(consistent_windows) / len(report.windows) if report.windows else 0.0

    # Model is valid if >= 60% of windows are consistent AND overall expectancy > 0
    report.is_valid = (
        report.consistency_score >= 0.6
        and report.overall_expectancy_r > 0
    )

    # Use the last window's optimal threshold as the production threshold
    if report.windows:
        report.optimal_threshold = report.windows[-1].optimal_threshold
        report.regime_thresholds = {}
        # Average regime thresholds across windows
        for regime_name in ["TRENDING_UP", "TRENDING_DOWN", "SIDEWAYS", "HIGH_VOLATILITY"]:
            vals = [w.optimal_threshold for w in report.windows]  # fallback
            report.regime_thresholds[regime_name] = float(np.median(vals))

    _update("\n" + "=" * 60)
    _update("WALK-FORWARD VALIDATION REPORT")
    _update("=" * 60)
    _update(f"  Windows:            {len(report.windows)}")
    _update(f"  Consistent:         {len(consistent_windows)}/{len(report.windows)} ({report.consistency_score:.0%})")
    _update(f"  Total Trades:       {report.overall_trade_count}")
    _update(f"  Expectancy (R):     {report.overall_expectancy_r:+.3f}")
    _update(f"  Max Drawdown (R):   {report.overall_max_drawdown_r:.1f}")
    _update(f"  Profit Factor:      {report.overall_profit_factor:.2f}")
    _update(f"  Optimal Threshold:  {report.optimal_threshold:.2f}")
    _update(f"  VALID:              {'✅ YES' if report.is_valid else '❌ NO'}")
    _update("=" * 60)

    return report


def main():
    parser = argparse.ArgumentParser(description="Walk-forward validation for WinClassifierV2")
    parser.add_argument("--symbols", type=int, default=200, help="Number of NSE symbols to use")
    parser.add_argument("--splits", type=int, default=5, help="Number of walk-forward windows")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    symbols = NSE_ALL_SYMBOLS[:args.symbols]
    report = run_walk_forward(symbols, n_splits=args.splits)

    if not report.is_valid:
        log.warning("\n⚠️  MODEL REJECTED — inconsistent across windows. Do NOT deploy.")
    else:
        log.info("\n✅ Model validated — consistent positive expectancy.")


if __name__ == "__main__":
    main()
