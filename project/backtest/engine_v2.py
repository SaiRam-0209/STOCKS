"""Backtesting engine v2 — execution-aware simulation with full cost model.

Key upgrades over the original engine:
    1. Entry on next-candle open (not signal candle)
    2. Slippage (0.1% default)
    3. Brokerage + STT + exchange charges
    4. Time-based exit at 15:15 PM
    5. MAE/MFE tracking per trade
    6. Expectancy (R), equity curve, profit factor
    7. Integration with WinClassifierV2 for AI-filtered backtesting
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from project.features.indicators import gap_percentage, relative_volume, atr

log = logging.getLogger(__name__)

# ── Cost model ───────────────────────────────────────────────────────────────
SLIPPAGE_PCT = 0.001            # 0.1% per side
BROKERAGE_PER_ORDER = 20.0      # ₹20 flat (Zerodha/Angel)
STT_INTRADAY_PCT = 0.00025     # STT on sell side intraday
EXCHANGE_CHARGES_PCT = 0.0003   # NSE txn + SEBI + stamp duty


@dataclass
class TradeResultV2:
    """A single backtested trade with full execution details."""
    symbol: str
    date: str
    direction: str             # "LONG" / "SHORT"
    entry_signal: float        # Price at signal generation
    entry_filled: float        # Actual fill price (after slippage)
    stoploss: float
    target: float
    exit_price: float
    risk: float                # Per-share risk ₹
    pnl_gross: float           # Before costs
    pnl_net: float             # After all costs
    costs: float               # Total round-trip cost per share
    result: str                # "WIN" / "LOSS" / "TIME_EXIT" / "NO_TRIGGER"
    r_multiple: float          # PnL in units of risk
    mae: float = 0.0          # Maximum Adverse Excursion
    mfe: float = 0.0          # Maximum Favorable Excursion
    win_prob: float = 0.0     # Model-predicted P(win), 0 if no model used
    confidence: str = ""       # "LOW" / "MEDIUM" / "HIGH"


@dataclass
class BacktestReportV2:
    """Comprehensive backtest metrics."""
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    time_exits: int = 0
    no_trigger: int = 0
    total_pnl_net: float = 0.0

    # R-multiple tracking
    total_r: float = 0.0
    r_multiples: list[float] = field(default_factory=list)
    trades: list[TradeResultV2] = field(default_factory=list)

    # Per-trade costs
    total_costs: float = 0.0

    @property
    def triggered_trades(self) -> int:
        return self.wins + self.losses + self.time_exits

    @property
    def win_rate(self) -> float:
        t = self.triggered_trades
        return (self.wins / t * 100) if t > 0 else 0.0

    @property
    def expectancy_r(self) -> float:
        return float(np.mean(self.r_multiples)) if self.r_multiples else 0.0

    @property
    def profit_factor(self) -> float:
        gains = sum(r for r in self.r_multiples if r > 0)
        losses = abs(sum(r for r in self.r_multiples if r <= 0))
        return gains / losses if losses > 0 else float("inf")

    @property
    def max_drawdown_r(self) -> float:
        if not self.r_multiples:
            return 0.0
        cumulative = np.cumsum(self.r_multiples)
        peak = np.maximum.accumulate(cumulative)
        return float((peak - cumulative).max())

    @property
    def equity_curve(self) -> list[float]:
        if not self.r_multiples:
            return []
        return np.cumsum(self.r_multiples).tolist()

    @property
    def avg_mae(self) -> float:
        maes = [t.mae for t in self.trades if t.result != "NO_TRIGGER"]
        return float(np.mean(maes)) if maes else 0.0

    @property
    def avg_mfe(self) -> float:
        mfes = [t.mfe for t in self.trades if t.result != "NO_TRIGGER"]
        return float(np.mean(mfes)) if mfes else 0.0

    def summary(self) -> str:
        lines = [
            f"\n{'='*55}",
            f"  BACKTEST REPORT V2 (Execution-Aware)",
            f"{'='*55}",
            f"  Trades triggered:  {self.triggered_trades}",
            f"  Wins:              {self.wins}",
            f"  Losses:            {self.losses}",
            f"  Time Exits:        {self.time_exits}",
            f"  Win Rate:          {self.win_rate:.1f}%",
            f"  ──────────────────────────────────",
            f"  Expectancy (R):    {self.expectancy_r:+.3f}",
            f"  Profit Factor:     {self.profit_factor:.3f}",
            f"  Max Drawdown (R):  {self.max_drawdown_r:.1f}",
            f"  Total P&L (net):   ₹{self.total_pnl_net:+,.2f}",
            f"  Total Costs:       ₹{self.total_costs:,.2f}",
            f"  ──────────────────────────────────",
            f"  Avg MAE:           ₹{self.avg_mae:.2f}",
            f"  Avg MFE:           ₹{self.avg_mfe:.2f}",
            f"{'='*55}\n",
        ]
        return "\n".join(lines)


def _compute_costs(entry_price: float, quantity: int = 1) -> float:
    """Compute round-trip costs per share."""
    brokerage = BROKERAGE_PER_ORDER * 2 / max(quantity, 1)  # Amortized per share
    stt = entry_price * STT_INTRADAY_PCT
    exchange = entry_price * EXCHANGE_CHARGES_PCT * 2
    return brokerage + stt + exchange


def _simulate_day_v2(
    symbol: str,
    day_df: pd.DataFrame,
    direction: str,
    daily_atr: float | None = None,
    max_candle_atr_ratio: float | None = None,
    win_prob: float = 0.0,
    confidence: str = "",
) -> TradeResultV2:
    """Simulate a single day's ORB trade with realistic execution.

    Entry: next candle open after first candle signal.
    Slippage, costs, MAE/MFE all tracked.
    """
    date_str = str(day_df.index[0].date())
    first_candle = day_df.iloc[0]
    candle_high = float(first_candle["High"])
    candle_low = float(first_candle["Low"])
    candle_range = candle_high - candle_low

    # Skip if opening candle is too wide
    if max_candle_atr_ratio is not None and daily_atr and daily_atr > 0:
        if candle_range > max_candle_atr_ratio * daily_atr:
            return TradeResultV2(
                symbol=symbol, date=date_str, direction=direction,
                entry_signal=0, entry_filled=0, stoploss=0, target=0,
                exit_price=0, risk=0, pnl_gross=0, pnl_net=0, costs=0,
                result="NO_TRIGGER", r_multiple=0, win_prob=win_prob,
                confidence=confidence,
            )

    if len(day_df) < 2:
        return TradeResultV2(
            symbol=symbol, date=date_str, direction=direction,
            entry_signal=0, entry_filled=0, stoploss=0, target=0,
            exit_price=0, risk=0, pnl_gross=0, pnl_net=0, costs=0,
            result="NO_TRIGGER", r_multiple=0, win_prob=win_prob,
            confidence=confidence,
        )

    # Entry is on NEXT candle open (not signal candle)
    next_candle = day_df.iloc[1]
    entry_signal = candle_high if direction == "LONG" else candle_low
    entry_raw = float(next_candle["Open"])

    if direction == "LONG":
        entry_filled = round(entry_raw * (1 + SLIPPAGE_PCT), 2)
        stoploss = candle_low
        risk = entry_filled - stoploss
        target = entry_filled + 2 * risk
    else:
        entry_filled = round(entry_raw * (1 - SLIPPAGE_PCT), 2)
        stoploss = candle_high
        risk = stoploss - entry_filled
        target = entry_filled - 2 * risk

    if risk <= 0:
        return TradeResultV2(
            symbol=symbol, date=date_str, direction=direction,
            entry_signal=entry_signal, entry_filled=entry_filled,
            stoploss=stoploss, target=target, exit_price=0, risk=0,
            pnl_gross=0, pnl_net=0, costs=0, result="NO_TRIGGER",
            r_multiple=0, win_prob=win_prob, confidence=confidence,
        )

    costs = _compute_costs(entry_filled)

    # Track MAE and MFE
    mae = 0.0
    mfe = 0.0
    exit_price = 0.0
    result = "TIME_EXIT"

    # Walk through subsequent candles (skip first 2: signal + entry)
    for _, candle in day_df.iloc[2:].iterrows():
        high = float(candle["High"])
        low = float(candle["Low"])

        if direction == "LONG":
            mae = max(mae, entry_filled - low)
            mfe = max(mfe, high - entry_filled)

            if low <= stoploss:
                exit_price = stoploss
                result = "LOSS"
                break
            if high >= target:
                exit_price = target
                result = "WIN"
                break
        else:
            mae = max(mae, high - entry_filled)
            mfe = max(mfe, entry_filled - low)

            if high >= stoploss:
                exit_price = stoploss
                result = "LOSS"
                break
            if low <= target:
                exit_price = target
                result = "WIN"
                break

    # Time exit: use last candle close (simulates 3:15 PM exit)
    if result == "TIME_EXIT":
        exit_price = float(day_df.iloc[-1]["Close"])

    if direction == "LONG":
        pnl_gross = exit_price - entry_filled
    else:
        pnl_gross = entry_filled - exit_price

    pnl_net = pnl_gross - costs
    r_multiple = pnl_net / risk if risk > 0 else 0.0

    return TradeResultV2(
        symbol=symbol,
        date=date_str,
        direction=direction,
        entry_signal=round(entry_signal, 2),
        entry_filled=round(entry_filled, 2),
        stoploss=round(stoploss, 2),
        target=round(target, 2),
        exit_price=round(exit_price, 2),
        risk=round(risk, 2),
        pnl_gross=round(pnl_gross, 2),
        pnl_net=round(pnl_net, 2),
        costs=round(costs, 2),
        result=result,
        r_multiple=round(r_multiple, 4),
        mae=round(mae, 2),
        mfe=round(mfe, 2),
        win_prob=round(win_prob, 4),
        confidence=confidence,
    )


def backtest_symbol_v2(
    symbol: str,
    intraday_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    gap_threshold: float = 2.0,
    vol_threshold: float = 1.5,
    max_candle_atr_ratio: float | None = None,
) -> list[TradeResultV2]:
    """Backtest the ORB strategy on one symbol with realistic execution."""
    results = []
    dates = sorted(set(intraday_df.index.date))

    for trade_date in dates:
        day_df = intraday_df[intraday_df.index.date == trade_date]
        if len(day_df) < 3:
            continue

        today_open = float(day_df.iloc[0]["Open"])
        daily_before = daily_df[daily_df.index.date < trade_date]
        if daily_before.empty:
            continue
        prev_close = float(daily_before.iloc[-1]["Close"])

        gap_pct = gap_percentage(today_open, prev_close)
        today_vol = float(day_df["Volume"].sum())
        prior_vols = daily_before["Volume"].tail(10)
        if prior_vols.empty:
            continue
        avg_vol = float(prior_vols.mean())
        rel_vol = relative_volume(today_vol, avg_vol)

        if abs(gap_pct) < gap_threshold or rel_vol < vol_threshold:
            continue

        direction = "LONG" if gap_pct > 0 else "SHORT"

        # ATR for wide-candle filter
        daily_atr_val = None
        if max_candle_atr_ratio is not None:
            atr_series = atr(daily_before, 14)
            if len(atr_series) > 0:
                daily_atr_val = float(atr_series.iloc[-1])

        trade = _simulate_day_v2(
            symbol, day_df, direction,
            daily_atr=daily_atr_val,
            max_candle_atr_ratio=max_candle_atr_ratio,
        )
        results.append(trade)

    return results


def run_backtest_v2(
    symbols: list[str],
    stock_intraday: dict[str, pd.DataFrame],
    stock_daily: dict[str, pd.DataFrame],
    gap_threshold: float = 2.0,
    vol_threshold: float = 1.5,
    max_candle_atr_ratio: float | None = None,
) -> BacktestReportV2:
    """Run v2 backtest across multiple symbols."""
    report = BacktestReportV2()

    for symbol in symbols:
        if symbol not in stock_intraday or symbol not in stock_daily:
            continue

        trades = backtest_symbol_v2(
            symbol,
            stock_intraday[symbol],
            stock_daily[symbol],
            gap_threshold=gap_threshold,
            vol_threshold=vol_threshold,
            max_candle_atr_ratio=max_candle_atr_ratio,
        )

        for t in trades:
            report.trades.append(t)
            report.total_trades += 1

            if t.result == "NO_TRIGGER":
                report.no_trigger += 1
                continue

            report.r_multiples.append(t.r_multiple)
            report.total_pnl_net += t.pnl_net
            report.total_costs += t.costs
            report.total_r += t.r_multiple

            if t.result == "WIN":
                report.wins += 1
            elif t.result == "LOSS":
                report.losses += 1
            else:
                report.time_exits += 1

    return report
