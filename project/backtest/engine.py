"""Backtesting engine: simulates the ORB strategy on historical intraday data."""

import pandas as pd
from dataclasses import dataclass, field

from project.features.indicators import gap_percentage, relative_volume, vwap, ema


@dataclass
class TradeResult:
    symbol: str
    date: str
    direction: str
    entry: float
    stoploss: float
    target: float
    exit_price: float
    pnl: float
    result: str  # "WIN", "LOSS", or "NO_TRIGGER"


@dataclass
class BacktestReport:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    no_trigger: int = 0
    total_pnl: float = 0.0
    gains: list[float] = field(default_factory=list)
    loss_list: list[float] = field(default_factory=list)
    trades: list[TradeResult] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        triggered = self.wins + self.losses
        return (self.wins / triggered * 100) if triggered > 0 else 0.0

    @property
    def avg_gain(self) -> float:
        return sum(self.gains) / len(self.gains) if self.gains else 0.0

    @property
    def avg_loss(self) -> float:
        return sum(self.loss_list) / len(self.loss_list) if self.loss_list else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in self.trades:
            if t.result == "NO_TRIGGER":
                continue
            cumulative += t.pnl
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)
        return max_dd

    def summary(self) -> str:
        triggered = self.wins + self.losses
        lines = [
            f"\n{'='*50}",
            f"  BACKTEST REPORT",
            f"{'='*50}",
            f"  Total trading days scanned: {self.total_trades}",
            f"  Trades triggered:           {triggered}",
            f"  No trigger (price didn't break ORB): {self.no_trigger}",
            f"  Wins:       {self.wins}",
            f"  Losses:     {self.losses}",
            f"  Win Rate:   {self.win_rate:.1f}%",
            f"  Total P&L:  ₹{self.total_pnl:.2f}",
            f"  Avg Gain:   ₹{self.avg_gain:.2f}",
            f"  Avg Loss:   ₹{self.avg_loss:.2f}",
            f"  Max Drawdown: ₹{self.max_drawdown:.2f}",
            f"{'='*50}\n",
        ]
        return "\n".join(lines)


def _simulate_day(symbol: str, day_df: pd.DataFrame, direction: str) -> TradeResult:
    """Simulate a single day's ORB trade on 15m candles.

    Args:
        symbol: Ticker.
        day_df: Intraday 15m DataFrame for one day.
        direction: "LONG" or "SHORT".

    Returns:
        TradeResult for the day.
    """
    date_str = str(day_df.index[0].date())
    first_candle = day_df.iloc[0]
    entry_long = float(first_candle["High"])
    entry_short = float(first_candle["Low"])
    sl_long = float(first_candle["Low"])
    sl_short = float(first_candle["High"])

    if direction == "LONG":
        entry = entry_long
        stoploss = sl_long
        risk = entry - stoploss
        target = entry + 2 * risk
    else:
        entry = entry_short
        stoploss = sl_short
        risk = stoploss - entry
        target = entry - 2 * risk

    if risk <= 0:
        return TradeResult(symbol, date_str, direction, entry, stoploss, target,
                           0.0, 0.0, "NO_TRIGGER")

    # Scan candles after the first one
    for _, candle in day_df.iloc[1:].iterrows():
        high = float(candle["High"])
        low = float(candle["Low"])

        if direction == "LONG":
            # Check if entry was triggered
            if high >= entry:
                # Check if SL hit in same candle
                if low <= stoploss:
                    pnl = -(risk)
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, stoploss, pnl, "LOSS")
                # Check if target hit
                if high >= target:
                    pnl = 2 * risk
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, target, pnl, "WIN")
                # Entry triggered, now track until SL or target in remaining candles
                for _, later in day_df.loc[candle.name:].iloc[1:].iterrows():
                    if float(later["Low"]) <= stoploss:
                        return TradeResult(symbol, date_str, direction, entry, stoploss,
                                           target, stoploss, -risk, "LOSS")
                    if float(later["High"]) >= target:
                        return TradeResult(symbol, date_str, direction, entry, stoploss,
                                           target, target, 2 * risk, "WIN")
                # End of day — exit at last close
                last_close = float(day_df.iloc[-1]["Close"])
                pnl = last_close - entry
                result = "WIN" if pnl > 0 else "LOSS"
                return TradeResult(symbol, date_str, direction, entry, stoploss,
                                   target, last_close, pnl, result)
        else:  # SHORT
            if low <= entry:
                if high >= stoploss:
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, stoploss, -risk, "LOSS")
                if low <= target:
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, target, 2 * risk, "WIN")
                for _, later in day_df.loc[candle.name:].iloc[1:].iterrows():
                    if float(later["High"]) >= stoploss:
                        return TradeResult(symbol, date_str, direction, entry, stoploss,
                                           target, stoploss, -risk, "LOSS")
                    if float(later["Low"]) <= target:
                        return TradeResult(symbol, date_str, direction, entry, stoploss,
                                           target, target, 2 * risk, "WIN")
                last_close = float(day_df.iloc[-1]["Close"])
                pnl = entry - last_close
                result = "WIN" if pnl > 0 else "LOSS"
                return TradeResult(symbol, date_str, direction, entry, stoploss,
                                   target, last_close, pnl, result)

    return TradeResult(symbol, date_str, direction, entry, stoploss, target,
                       0.0, 0.0, "NO_TRIGGER")


def backtest_symbol(symbol: str, intraday_df: pd.DataFrame,
                    daily_df: pd.DataFrame) -> list[TradeResult]:
    """Backtest the ORB strategy on one symbol across all available days.

    For each day:
      1. Check if gap >= 2% and relative volume >= 1.5
      2. If yes, simulate the ORB trade
    """
    results = []
    dates = sorted(set(intraday_df.index.date))

    for i, date in enumerate(dates):
        day_df = intraday_df[intraday_df.index.date == date]
        if len(day_df) < 3:
            continue

        today_open = float(day_df.iloc[0]["Open"])

        # Get previous day's close from daily data
        daily_before = daily_df[daily_df.index.date < date]
        if daily_before.empty:
            continue
        prev_close = float(daily_before.iloc[-1]["Close"])

        gap_pct = gap_percentage(today_open, prev_close)

        # Relative volume: today's volume vs avg of prior days in daily_df
        today_vol = float(day_df["Volume"].sum())
        prior_vols = daily_before["Volume"].tail(10)
        if prior_vols.empty:
            continue
        avg_vol = float(prior_vols.mean())
        rel_vol = relative_volume(today_vol, avg_vol)

        # Apply primary filters (simplified: gap + volume only for backtest)
        if abs(gap_pct) < 2.0 or rel_vol < 1.5:
            continue

        direction = "LONG" if gap_pct > 0 else "SHORT"
        trade = _simulate_day(symbol, day_df, direction)
        results.append(trade)

    return results


def run_backtest(symbols: list[str], stock_intraday: dict[str, pd.DataFrame],
                 stock_daily: dict[str, pd.DataFrame]) -> BacktestReport:
    """Run backtest across multiple symbols.

    Args:
        symbols: List of tickers.
        stock_intraday: Dict of symbol -> intraday DataFrame.
        stock_daily: Dict of symbol -> daily DataFrame.

    Returns:
        BacktestReport with aggregated results.
    """
    report = BacktestReport()

    for symbol in symbols:
        if symbol not in stock_intraday or symbol not in stock_daily:
            continue

        trades = backtest_symbol(symbol, stock_intraday[symbol], stock_daily[symbol])
        for t in trades:
            report.trades.append(t)
            report.total_trades += 1
            if t.result == "WIN":
                report.wins += 1
                report.gains.append(t.pnl)
                report.total_pnl += t.pnl
            elif t.result == "LOSS":
                report.losses += 1
                report.loss_list.append(t.pnl)
                report.total_pnl += t.pnl
            else:
                report.no_trigger += 1

    return report
