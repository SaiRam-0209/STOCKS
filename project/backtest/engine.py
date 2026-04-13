"""Backtesting engine: simulates the ORB strategy on historical intraday data."""

import pandas as pd
from dataclasses import dataclass, field

from project.features.indicators import gap_percentage, relative_volume, vwap, ema, atr


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
    def profit_factor(self) -> float:
        gross_profit = sum(self.gains)
        gross_loss = abs(sum(self.loss_list))
        return gross_profit / gross_loss if gross_loss > 0 else float("inf")

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
            f"  Trades triggered:  {triggered}",
            f"  Wins:              {self.wins}",
            f"  Losses:            {self.losses}",
            f"  Win Rate:          {self.win_rate:.1f}%",
            f"  Total P&L:         ₹{self.total_pnl:.2f}",
            f"  Avg Gain:          ₹{self.avg_gain:.2f}",
            f"  Avg Loss:          ₹{self.avg_loss:.2f}",
            f"  Profit Factor:     {self.profit_factor:.3f}",
            f"  Max Drawdown:      ₹{self.max_drawdown:.2f}",
            f"{'='*50}\n",
        ]
        return "\n".join(lines)


def _simulate_day(
    symbol: str,
    day_df: pd.DataFrame,
    direction: str,
    # ── improvement knobs ─────────────────────────────────────────────────
    sl_fraction: float = 1.0,    # 1.0 = full candle SL, 0.5 = half candle SL
    trailing_stop: bool = False,  # move SL to breakeven at 1R, trail at 2R
    max_candle_atr_ratio: float | None = None,  # skip if candle > N×ATR
    daily_atr: float | None = None,             # required for max_candle_atr_ratio
) -> TradeResult:
    """Simulate a single day's ORB trade on 15m candles."""
    date_str = str(day_df.index[0].date())
    first_candle = day_df.iloc[0]
    candle_high = float(first_candle["High"])
    candle_low = float(first_candle["Low"])
    candle_range = candle_high - candle_low

    # Skip if opening candle is too wide (chaotic, no edge)
    if max_candle_atr_ratio is not None and daily_atr and daily_atr > 0:
        if candle_range > max_candle_atr_ratio * daily_atr:
            return TradeResult(symbol, date_str, direction, 0, 0, 0, 0, 0.0, "NO_TRIGGER")

    if direction == "LONG":
        entry = candle_high
        # Tighter SL: use fraction of candle range
        stoploss = entry - (candle_range * sl_fraction)
        risk = entry - stoploss
        target = entry + 2 * risk
    else:
        entry = candle_low
        stoploss = entry + (candle_range * sl_fraction)
        risk = stoploss - entry
        target = entry - 2 * risk

    if risk <= 0:
        return TradeResult(symbol, date_str, direction, entry, stoploss, target,
                           0.0, 0.0, "NO_TRIGGER")

    # Trailing stop state
    trail_sl = stoploss
    breakeven_moved = False
    trailing_active = False

    for _, candle in day_df.iloc[1:].iterrows():
        high = float(candle["High"])
        low = float(candle["Low"])

        if direction == "LONG":
            if high < entry:
                continue  # not triggered yet

            # Entry triggered — check SL hit in same candle
            if low <= trail_sl:
                pnl = trail_sl - entry if trail_sl > stoploss else -risk
                result = "WIN" if pnl > 0 else "LOSS"
                return TradeResult(symbol, date_str, direction, entry, stoploss,
                                   target, trail_sl, pnl, result)

            # Check target
            if high >= target:
                return TradeResult(symbol, date_str, direction, entry, stoploss,
                                   target, target, 2 * risk, "WIN")

            # Trailing stop logic once in trade
            for _, later in day_df.loc[candle.name:].iloc[1:].iterrows():
                l_high = float(later["High"])
                l_low = float(later["Low"])

                if trailing_stop:
                    # At 1R profit: move SL to breakeven
                    if l_high >= entry + risk and not breakeven_moved:
                        trail_sl = entry
                        breakeven_moved = True
                    # At 2R profit: start trailing by 0.5R
                    if l_high >= entry + 2 * risk:
                        new_trail = l_high - 0.5 * risk
                        trail_sl = max(trail_sl, new_trail)
                        trailing_active = True

                if l_low <= trail_sl:
                    pnl = trail_sl - entry
                    result = "WIN" if pnl > 0 else "LOSS"
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, trail_sl, pnl, result)
                if l_high >= target and not trailing_active:
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, target, 2 * risk, "WIN")

            # EOD exit
            last_close = float(day_df.iloc[-1]["Close"])
            pnl = last_close - entry
            result = "WIN" if pnl > 0 else "LOSS"
            return TradeResult(symbol, date_str, direction, entry, stoploss,
                               target, last_close, pnl, result)

        else:  # SHORT
            if low > entry:
                continue

            if high >= trail_sl:
                pnl = entry - trail_sl if trail_sl < stoploss else -risk
                result = "WIN" if pnl > 0 else "LOSS"
                return TradeResult(symbol, date_str, direction, entry, stoploss,
                                   target, trail_sl, pnl, result)

            if low <= target:
                return TradeResult(symbol, date_str, direction, entry, stoploss,
                                   target, target, 2 * risk, "WIN")

            for _, later in day_df.loc[candle.name:].iloc[1:].iterrows():
                l_high = float(later["High"])
                l_low = float(later["Low"])

                if trailing_stop:
                    if l_low <= entry - risk and not breakeven_moved:
                        trail_sl = entry
                        breakeven_moved = True
                    if l_low <= entry - 2 * risk:
                        new_trail = l_low + 0.5 * risk
                        trail_sl = min(trail_sl, new_trail)
                        trailing_active = True

                if l_high >= trail_sl:
                    pnl = entry - trail_sl
                    result = "WIN" if pnl > 0 else "LOSS"
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, trail_sl, pnl, result)
                if l_low <= target and not trailing_active:
                    return TradeResult(symbol, date_str, direction, entry, stoploss,
                                       target, target, 2 * risk, "WIN")

            last_close = float(day_df.iloc[-1]["Close"])
            pnl = entry - last_close
            result = "WIN" if pnl > 0 else "LOSS"
            return TradeResult(symbol, date_str, direction, entry, stoploss,
                               target, last_close, pnl, result)

    return TradeResult(symbol, date_str, direction, entry, stoploss, target,
                       0.0, 0.0, "NO_TRIGGER")


def backtest_symbol(
    symbol: str,
    intraday_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    nifty_daily: pd.DataFrame | None = None,
    # ── entry thresholds ─────────────────────────────────
    gap_threshold: float = 2.0,
    vol_threshold: float = 1.5,
    # ── improvement knobs ────────────────────────────────
    sl_fraction: float = 1.0,
    trailing_stop: bool = False,
    max_candle_atr_ratio: float | None = None,
    nifty_filter: bool = False,
) -> list[TradeResult]:
    """Backtest the ORB strategy on one symbol across all available days."""
    results = []
    dates = sorted(set(intraday_df.index.date))

    for date in dates:
        day_df = intraday_df[intraday_df.index.date == date]
        if len(day_df) < 3:
            continue

        today_open = float(day_df.iloc[0]["Open"])
        daily_before = daily_df[daily_df.index.date < date]
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

        # Nifty filter: skip counter-trend trades
        if nifty_filter and nifty_daily is not None:
            nifty_before = nifty_daily[nifty_daily.index.date < date]
            nifty_today = nifty_daily[nifty_daily.index.date == date]
            if not nifty_before.empty and not nifty_today.empty:
                nifty_prev_close = float(nifty_before.iloc[-1]["Close"])
                nifty_open = float(nifty_today.iloc[0]["Open"])
                nifty_gap = gap_percentage(nifty_open, nifty_prev_close)
                # Skip if stock direction opposes Nifty gap direction
                if nifty_gap > 0.5 and direction == "SHORT":
                    continue
                if nifty_gap < -0.5 and direction == "LONG":
                    continue

        # ATR for wide-candle filter
        daily_atr_val = None
        if max_candle_atr_ratio is not None:
            atr_series = atr(daily_before, 14)
            if len(atr_series) > 0:
                daily_atr_val = float(atr_series.iloc[-1])

        trade = _simulate_day(
            symbol, day_df, direction,
            sl_fraction=sl_fraction,
            trailing_stop=trailing_stop,
            max_candle_atr_ratio=max_candle_atr_ratio,
            daily_atr=daily_atr_val,
        )
        results.append(trade)

    return results


def run_backtest(
    symbols: list[str],
    stock_intraday: dict[str, pd.DataFrame],
    stock_daily: dict[str, pd.DataFrame],
    nifty_daily: pd.DataFrame | None = None,
    gap_threshold: float = 2.0,
    vol_threshold: float = 1.5,
    sl_fraction: float = 1.0,
    trailing_stop: bool = False,
    max_candle_atr_ratio: float | None = None,
    nifty_filter: bool = False,
) -> BacktestReport:
    """Run backtest across multiple symbols with configurable improvements."""
    report = BacktestReport()

    for symbol in symbols:
        if symbol not in stock_intraday or symbol not in stock_daily:
            continue

        trades = backtest_symbol(
            symbol,
            stock_intraday[symbol],
            stock_daily[symbol],
            nifty_daily=nifty_daily,
            gap_threshold=gap_threshold,
            vol_threshold=vol_threshold,
            sl_fraction=sl_fraction,
            trailing_stop=trailing_stop,
            max_candle_atr_ratio=max_candle_atr_ratio,
            nifty_filter=nifty_filter,
        )
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
