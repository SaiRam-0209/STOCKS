"""Main trading executor — runs the ORB strategy live.

Timeline (IST):
    09:00  Login to broker, prefetch instruments
    09:15  Market opens — first 15-min candle forming
    09:20  First candle closes → scan → rank → place orders
    09:20-15:15  Monitor positions (bracket orders auto-handle SL/target)
    15:15  Exit remaining positions (EOD square-off)
    15:30  Daily report → logout

Usage:
    executor = TradingExecutor(mode="paper")  # or "live"
    executor.run()
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, time as dt_time
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

from project.broker.angel import AngelBroker, BrokerConfig
from project.broker.orders import OrderManager, OrderSide, OrderStatus, TradeOrder
from project.broker.symbols import SymbolMapper
from project.trading.risk import RiskManager, RiskConfig
from project.features.indicators import gap_percentage, relative_volume
from project.data.symbols_fetcher import get_all_nse_stocks

log = logging.getLogger(__name__)

# ── Market hours (IST) ───────────────────────────────────────────────────
MARKET_OPEN = dt_time(9, 15)
FIRST_CANDLE_CLOSE = dt_time(9, 20)    # 15-min candle at 9:15 closes at 9:20 for 5-min, but we use 9:30 for 15-min
SCAN_TIME = dt_time(9, 30)              # After first 15-min candle closes
EOD_EXIT_TIME = dt_time(15, 15)
MARKET_CLOSE = dt_time(15, 30)

# ── Strategy defaults ────────────────────────────────────────────────────
DEFAULT_GAP_THRESHOLD = 2.0      # Loose pre-filter; AI model is the real gatekeeper
DEFAULT_VOL_THRESHOLD = 1.5      # Above-average volume, not exceptional
DEFAULT_TOP_N = 4                # Max simultaneous trades
SLIPPAGE_PCT = 0.001             # 0.1% slippage buffer on entry orders
TRAILING_SL_ENABLED = True       # Move SL to breakeven at 1R profit
MIN_STOCK_PRICE = 50.0           # Avoid penny stocks (noisy, wide spreads)
MAX_STOCK_PRICE = 10000.0        # Let position sizing handle expensive stocks
SHORT_FILTER_ENABLED = True      # Only allow shorts in bearish markets
MIN_AI_CONFIDENCE = 0.2          # Fallback threshold when AI model unavailable


@dataclass
class ScanResult:
    """A stock that passed the ORB filter."""
    ticker: str
    direction: str          # "LONG" or "SHORT"
    gap_pct: float
    rel_vol: float
    entry: float            # First candle high (LONG) or low (SHORT)
    stoploss: float         # First candle low (LONG) or high (SHORT)
    target: float
    risk: float
    model_score: float = 0.0


@dataclass
class DailyLog:
    """Log of everything that happened today."""
    date: str = ""
    scanned_stocks: int = 0
    qualifying_stocks: int = 0
    trades_placed: int = 0
    trades_filled: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    events: list[str] = field(default_factory=list)

    def log_event(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{ts}] {msg}")
        log.info(msg)


class TradingExecutor:
    """Orchestrates the full trading day."""

    def __init__(
        self,
        mode: str = "paper",            # "paper" or "live"
        capital: float = 20_000.0,
        gap_threshold: float = DEFAULT_GAP_THRESHOLD,
        vol_threshold: float = DEFAULT_VOL_THRESHOLD,
        top_n: int = DEFAULT_TOP_N,
        symbols: list[str] | None = None,
        alert_callback=None,             # Called with (message: str)
    ):
        self.mode = mode
        self.gap_threshold = gap_threshold
        self.vol_threshold = vol_threshold
        self.top_n = top_n
        self.alert_callback = alert_callback
        self.daily_log = DailyLog(date=datetime.now().strftime("%Y-%m-%d"))

        # Risk manager
        self.risk = RiskManager(RiskConfig(total_capital=capital))

        # Broker (only connect in live mode)
        self.broker: AngelBroker | None = None
        self.order_mgr: OrderManager | None = None
        self.mapper: SymbolMapper | None = None

        # Stock universe
        self._symbols = symbols

        # Paper trading state
        self.paper_trades: list[dict] = []

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        """Run the full trading day. Blocks until market close."""
        self.daily_log.log_event(f"Starting executor in {self.mode.upper()} mode")
        self.daily_log.log_event(f"Capital: ₹{self.risk.config.total_capital:,.0f}")

        # Pre-market checks
        ok, reason = self.risk.is_trading_day()
        if not ok:
            self.daily_log.log_event(f"Not a trading day: {reason}")
            self._alert(f"Skipping today: {reason}")
            return self.daily_log

        # Market regime check: skip ORB in extreme bear markets
        try:
            from project.macro.global_data import fetch_global_snapshot, compute_macro_score
            snapshot = fetch_global_snapshot()
            macro = compute_macro_score(snapshot)
            mood = macro.get("market_mood", "NEUTRAL")
            self._market_mood = mood
            self.daily_log.log_event(f"Market mood: {mood} (score: {macro.get('macro_score', 0)})")
            if mood == "VERY_BEARISH":
                self.daily_log.log_event("VERY BEARISH market — reducing position sizes by 50%")
                self.risk.config.max_capital_per_trade *= 0.5
                self._alert("⚠️ Very bearish market — trading with reduced size")
        except Exception as exc:
            self._market_mood = "NEUTRAL"
            self.daily_log.log_event(f"Macro check skipped: {exc}")

        # Connect broker (live mode only)
        if self.mode == "live":
            if not self._connect_broker():
                return self.daily_log

        # Wait for market open + first candle
        self._wait_until(SCAN_TIME, "Waiting for first 15-min candle to close...")

        # SCAN phase: find qualifying stocks
        candidates = self._scan_stocks()
        if not candidates:
            self.daily_log.log_event("No qualifying stocks found today")
            self._alert("No qualifying stocks today. Sitting out.")
            return self.daily_log

        # RANK phase: pick top N by gap strength + model score
        top_picks = self._rank_and_select(candidates)

        # EXECUTE phase: place orders
        self._place_orders(top_picks)

        # MONITOR phase: watch until EOD
        self._monitor_loop()

        # EOD: exit remaining positions
        self._eod_exit()

        # Report
        self._generate_report()

        # Disconnect
        if self.broker:
            self.broker.logout()

        return self.daily_log

    # ── Scanning ──────────────────────────────────────────────────────────

    def _scan_stocks(self) -> list[ScanResult]:
        """Scan all stocks for ORB setups after first 15-min candle."""
        self.daily_log.log_event("Scanning for ORB setups...")

        if self._symbols is None:
            self._symbols = get_all_nse_stocks()
            if not self._symbols:
                from project.data.symbols import ALL_STOCKS
                self._symbols = ALL_STOCKS
                self.daily_log.log_event(
                    f"Dynamic NSE symbol load returned 0; using {len(self._symbols)} index stocks"
                )
        self.daily_log.scanned_stocks = len(self._symbols)

        candidates = []
        today = datetime.now().date()

        for ticker in self._symbols:
            try:
                result = self._check_stock(ticker, today)
                if result:
                    candidates.append(result)
            except Exception as exc:
                log.debug("Error scanning %s: %s", ticker, exc)

        self.daily_log.qualifying_stocks = len(candidates)
        self.daily_log.log_event(
            f"Found {len(candidates)} qualifying stocks out of {len(self._symbols)}"
        )
        return candidates

    def _check_stock(self, ticker: str, today) -> ScanResult | None:
        """Check if a single stock qualifies for ORB trade today."""
        yf_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"

        # Fetch recent intraday data. yfinance can return empty for NSE
        # `period="1d"` outside some market windows, while 5d remains reliable.
        tk = yf.Ticker(yf_ticker)
        intra = tk.history(period="5d", interval="15m")
        if intra.empty:
            return None

        session_dates = intra.index.date
        today_intra = intra[session_dates == today]
        if today_intra.empty:
            return None

        # Fetch completed daily data for prev close + average volume.
        daily = tk.history(period="30d", interval="1d")
        if daily.empty:
            return None
        completed_daily = daily[daily.index.date < today]
        if len(completed_daily) < 2:
            return None

        # First 15-min candle
        first_candle = today_intra.iloc[0]
        today_open = float(first_candle["Open"])
        candle_high = float(first_candle["High"])
        candle_low = float(first_candle["Low"])
        candle_range = candle_high - candle_low

        # Previous close
        prev_close = float(completed_daily.iloc[-1]["Close"])

        # Gap percentage
        gap_pct = gap_percentage(today_open, prev_close)

        # Relative volume: today's first candle volume vs avg daily volume
        today_vol = float(first_candle["Volume"])
        avg_vol = float(completed_daily["Volume"].tail(10).mean())
        if avg_vol <= 0:
            return None
        # Scale intraday volume: 15-min volume × 25 (approx candles/day) to compare with daily
        rel_vol = relative_volume(today_vol * 25, avg_vol)

        # Apply thresholds
        if abs(gap_pct) < self.gap_threshold or rel_vol < self.vol_threshold:
            return None

        # Price filter: avoid penny stocks and ultra-expensive stocks
        if today_open < MIN_STOCK_PRICE or today_open > MAX_STOCK_PRICE:
            return None

        # Direction
        direction = "LONG" if gap_pct > 0 else "SHORT"

        # Short filter: only allow shorts in bearish markets (backtest shows 38% WR for shorts)
        if SHORT_FILTER_ENABLED and direction == "SHORT":
            try:
                from project.macro.global_data import fetch_global_snapshot, compute_macro_score
                snapshot = fetch_global_snapshot()
                macro = compute_macro_score(snapshot)
                mood = macro.get("market_mood", "NEUTRAL")
                if mood not in ("BEARISH", "VERY_BEARISH"):
                    return None  # Skip shorts in neutral/bullish markets
            except Exception:
                return None  # If can't determine mood, skip shorts to be safe

        # Entry, SL, Target
        if direction == "LONG":
            entry = candle_high
            stoploss = candle_low
            risk = entry - stoploss
            target = entry + 2 * risk
        else:
            entry = candle_low
            stoploss = candle_high
            risk = stoploss - entry
            target = entry - 2 * risk

        if risk <= 0 or candle_range <= 0:
            return None

        # Multi-timeframe: check 5-min candle for tighter confirmation
        try:
            intra_5m = tk.history(period="1d", interval="5m")
            if not intra_5m.empty and len(intra_5m) >= 3:
                # The 3rd 5-min candle (9:25-9:30) should confirm direction
                confirm_candle = intra_5m.iloc[2] if len(intra_5m) > 2 else intra_5m.iloc[-1]
                c_close = float(confirm_candle["Close"])
                c_open = float(confirm_candle["Open"])
                # Confirmation: 5-min candle closes in gap direction
                if direction == "LONG" and c_close < c_open:
                    return None  # 5-min bearish candle contradicts gap-up
                if direction == "SHORT" and c_close > c_open:
                    return None  # 5-min bullish candle contradicts gap-down
        except Exception:
            pass  # If 5-min data fails, proceed with 15-min only

        # Peer comparison: check sector gap to isolate unique strength
        unique_gap = gap_pct  # Default: full gap is unique
        try:
            from project.data.sectors import get_sector, get_sector_stocks
            sector = get_sector(yf_ticker)
            if sector:
                sector_stocks = get_sector_stocks(sector)[:5]  # Sample 5 peers
                peer_gaps = []
                for peer in sector_stocks:
                    if peer == yf_ticker:
                        continue
                    try:
                        p_daily = yf.Ticker(peer).history(period="5d", interval="1d")
                        if len(p_daily) >= 2:
                            p_gap = gap_percentage(
                                float(p_daily.iloc[-1]["Open"]),
                                float(p_daily.iloc[-2]["Close"])
                            )
                            peer_gaps.append(p_gap)
                    except Exception:
                        continue
                if peer_gaps:
                    sector_avg_gap = sum(peer_gaps) / len(peer_gaps)
                    unique_gap = gap_pct - sector_avg_gap  # Excess gap over sector
        except Exception:
            pass

        return ScanResult(
            ticker=ticker,
            direction=direction,
            gap_pct=gap_pct,
            rel_vol=rel_vol,
            entry=round(entry, 2),
            stoploss=round(stoploss, 2),
            target=round(target, 2),
            risk=round(risk, 2),
        )

    # ── Ranking ───────────────────────────────────────────────────────────

    def _rank_and_select(self, candidates: list[ScanResult]) -> list[ScanResult]:
        """Filter candidates using Win Classifier, then rank by win probability."""
        import numpy as np

        # Try Win Classifier first
        ai_filtered = False
        try:
            from project.ml.win_classifier import WinClassifier, ALL_FEATURES
            from project.ml.features import build_breakout_features_for_day
            from project.ml.features_v2 import build_v2_features
            from project.ml.features_v3 import build_v3_features

            # Fetch Nifty once for all candidates (market-context features)
            try:
                nifty_df = yf.Ticker("^NSEI").history(period="90d", interval="1d")
                if len(nifty_df) < 20:
                    nifty_df = None
            except Exception:
                nifty_df = None

            clf = WinClassifier()
            if clf.load():
                if clf.n_features != len(ALL_FEATURES):
                    self.daily_log.log_event(
                        f"⚠️ Model has {clf.n_features} features but code expects "
                        f"{len(ALL_FEATURES)} — falling back to non-AI ranking"
                    )
                    raise ValueError("feature count mismatch")

                self.daily_log.log_event(
                    f"Using Win Classifier ({len(ALL_FEATURES)} features, {clf.n_samples} samples)"
                )

                scored_candidates = []
                for c in candidates:
                    try:
                        yf_ticker = c.ticker if c.ticker.endswith(".NS") else f"{c.ticker}.NS"
                        tk = yf.Ticker(yf_ticker)
                        daily = tk.history(period="90d", interval="1d")
                        if len(daily) < 30:
                            continue

                        day_idx = len(daily) - 1
                        # Base 20 features
                        base_feat = build_breakout_features_for_day(daily, day_idx)
                        if base_feat is None:
                            continue

                        # Extra 10 features
                        extra_feat = clf.build_extra_features(daily, day_idx)
                        if extra_feat is None:
                            continue

                        # V2 features (market context + microstructure)
                        v2_feat = build_v2_features(daily, day_idx, nifty_df=nifty_df)

                        # V3 features (VIX, DII, delivery, OI, PCR, blocks, peers)
                        v3_feat = build_v3_features(
                            c.ticker, datetime.now().date(), daily, day_idx
                        )

                        all_feat = {**base_feat, **extra_feat, **v2_feat, **v3_feat}
                        feature_vec = np.array(
                            [all_feat[col] for col in ALL_FEATURES], dtype=np.float32
                        )

                        take, win_prob = clf.should_take_trade(feature_vec)
                        c.model_score = win_prob

                        if take:
                            scored_candidates.append(c)
                            self.daily_log.log_event(
                                f"  ✅ {c.ticker} P(win)={win_prob:.0%} gap={c.gap_pct:+.1f}%"
                            )
                        else:
                            self.daily_log.log_event(
                                f"  ❌ {c.ticker} P(win)={win_prob:.0%} — SKIPPED (below 55%)"
                            )
                    except Exception as exc:
                        log.debug("Win classifier error for %s: %s", c.ticker, exc)
                        continue

                candidates = scored_candidates
                ai_filtered = True
        except Exception as exc:
            self.daily_log.log_event(f"Win classifier unavailable: {exc}")

        if not ai_filtered:
            # Fallback: simple conviction score
            for c in candidates:
                c.model_score = min(abs(c.gap_pct) * c.rel_vol / 100, 1.0)
            if candidates:
                self.daily_log.log_event(
                    "AI filter unavailable; ranking primary candidates by gap/volume conviction"
                )

        # Sort by win probability (highest first)
        candidates.sort(key=lambda x: x.model_score, reverse=True)
        top = candidates[:self.top_n]

        self.daily_log.log_event(
            f"Selected {len(top)}/{len(candidates)} (AI={'YES' if ai_filtered else 'NO'}): "
            + ", ".join(
                f"{c.ticker} (P(win)={c.model_score:.0%} gap={c.gap_pct:+.1f}%)"
                for c in top
            )
        )
        return top

    # ── Order execution ───────────────────────────────────────────────────

    def _place_orders(self, picks: list[ScanResult]):
        """Place bracket orders for selected stocks."""
        for pick in picks:
            ok, reason = self.risk.can_take_trade()
            if not ok:
                self.daily_log.log_event(f"Risk check failed: {reason}")
                break

            quantity = self.risk.calculate_position_size(pick.entry, pick.stoploss)
            if quantity <= 0:
                continue

            trade = TradeOrder(
                ticker=pick.ticker,
                side=OrderSide.BUY if pick.direction == "LONG" else OrderSide.SELL,
                quantity=quantity,
                entry_price=pick.entry,
                stoploss=pick.stoploss,
                target=pick.target,
            )

            if self.mode == "paper":
                self._paper_place(trade, pick)
            else:
                self._live_place(trade, pick)

    def _paper_place(self, trade: TradeOrder, pick: ScanResult):
        """Simulate order placement in paper mode with slippage."""
        # Apply slippage buffer — real market won't fill exactly at signal price
        if trade.side == OrderSide.BUY:
            trade.entry_price = round(trade.entry_price * (1 + SLIPPAGE_PCT), 2)
        else:
            trade.entry_price = round(trade.entry_price * (1 - SLIPPAGE_PCT), 2)

        trade.status = OrderStatus.PLACED
        trade.order_id = f"PAPER-{len(self.paper_trades)+1}"
        trade.placed_at = datetime.now().strftime("%H:%M:%S")

        self.paper_trades.append({
            "trade": trade,
            "pick": pick,
            "status": "OPEN",
            "trail_sl": trade.stoploss,
            "breakeven_moved": False,
        })
        self.risk.record_trade_entry()
        self.daily_log.trades_placed += 1

        msg = (
            f"📋 PAPER {trade.side.value} {trade.ticker} | "
            f"Qty: {trade.quantity} @ ₹{trade.entry_price:.2f} | "
            f"SL: ₹{trade.stoploss:.2f} | TGT: ₹{trade.target:.2f} | "
            f"Gap: {pick.gap_pct:+.1f}% | Vol: {pick.rel_vol:.1f}x"
        )
        self.daily_log.log_event(msg)
        self._alert(msg)

    def _live_place(self, trade: TradeOrder, pick: ScanResult):
        """Place real bracket order via broker."""
        if not self.order_mgr:
            self.daily_log.log_event("ERROR: Order manager not initialized")
            return

        success = self.order_mgr.place_bracket_order(trade)
        if success:
            self.risk.record_trade_entry()
            self.daily_log.trades_placed += 1
            msg = (
                f"🟢 LIVE {trade.side.value} {trade.ticker} | "
                f"Qty: {trade.quantity} @ ₹{trade.entry_price:.2f} | "
                f"SL: ₹{trade.stoploss:.2f} | TGT: ₹{trade.target:.2f}"
            )
            self.daily_log.log_event(msg)
            self._alert(msg)
        else:
            self.daily_log.log_event(f"Order REJECTED for {trade.ticker}")

    # ── Monitoring ────────────────────────────────────────────────────────

    def _monitor_loop(self):
        """Monitor open positions until EOD exit time."""
        self.daily_log.log_event("Monitoring positions...")

        while datetime.now().time() < EOD_EXIT_TIME:
            if self.mode == "paper":
                self._paper_monitor()
            else:
                self._live_monitor()

            # Check if halted
            if self.risk.state.is_halted:
                self.daily_log.log_event(f"HALTED: {self.risk.state.halt_reason}")
                break

            time.sleep(30)  # Check every 30 seconds

    def _paper_monitor(self):
        """Check paper trades against live prices with trailing stoploss."""
        for pt in self.paper_trades:
            if pt["status"] != "OPEN":
                continue

            trade: TradeOrder = pt["trade"]
            pick: ScanResult = pt["pick"]

            # Fetch current price
            yf_ticker = trade.ticker if trade.ticker.endswith(".NS") else f"{trade.ticker}.NS"
            try:
                tk = yf.Ticker(yf_ticker)
                data = tk.history(period="1d", interval="1m")
                if data.empty:
                    continue
                current_price = float(data.iloc[-1]["Close"])
                current_high = float(data.iloc[-1]["High"])
                current_low = float(data.iloc[-1]["Low"])
            except Exception:
                continue

            risk = abs(trade.entry_price - trade.stoploss)
            trail_sl = pt.get("trail_sl", trade.stoploss)

            # Trailing stoploss: move SL to breakeven at 1R profit
            if TRAILING_SL_ENABLED and risk > 0:
                if trade.side == OrderSide.BUY:
                    if current_high >= trade.entry_price + risk and not pt.get("breakeven_moved"):
                        trail_sl = trade.entry_price + 0.5  # Tiny buffer above entry
                        pt["breakeven_moved"] = True
                        pt["trail_sl"] = trail_sl
                        self._alert(f"📊 {trade.ticker} — SL moved to breakeven ₹{trail_sl:.2f}")
                else:
                    if current_low <= trade.entry_price - risk and not pt.get("breakeven_moved"):
                        trail_sl = trade.entry_price - 0.5
                        pt["breakeven_moved"] = True
                        pt["trail_sl"] = trail_sl
                        self._alert(f"📊 {trade.ticker} — SL moved to breakeven ₹{trail_sl:.2f}")

            # Check SL / Target hit
            if trade.side == OrderSide.BUY:
                if current_low <= trail_sl:
                    pnl = (trail_sl - trade.entry_price) * trade.quantity
                    result = "WIN" if pnl > 0 else "LOSS"
                    self._paper_exit(pt, trail_sl, pnl, result)
                elif current_high >= trade.target:
                    pnl = (trade.target - trade.entry_price) * trade.quantity
                    self._paper_exit(pt, trade.target, pnl, "WIN")
            else:
                if current_high >= trail_sl:
                    pnl = (trade.entry_price - trail_sl) * trade.quantity
                    result = "WIN" if pnl > 0 else "LOSS"
                    self._paper_exit(pt, trail_sl, pnl, result)
                elif current_low <= trade.target:
                    pnl = (trade.entry_price - trade.target) * trade.quantity
                    self._paper_exit(pt, trade.target, pnl, "WIN")

    def _paper_exit(self, pt: dict, exit_price: float, pnl: float, result: str):
        """Record paper trade exit."""
        trade: TradeOrder = pt["trade"]
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.status = OrderStatus.EXITED
        trade.exited_at = datetime.now().strftime("%H:%M:%S")
        pt["status"] = result

        self.risk.record_trade_exit(pnl)
        if result == "WIN":
            self.daily_log.wins += 1
        else:
            self.daily_log.losses += 1
        self.daily_log.total_pnl += pnl

        emoji = "✅" if result == "WIN" else "❌"
        msg = (
            f"{emoji} PAPER {result} {trade.ticker} | "
            f"Exit: ₹{exit_price:.2f} | P&L: ₹{pnl:+.2f}"
        )
        self.daily_log.log_event(msg)
        self._alert(msg)

    def _live_monitor(self):
        """Sync order status from broker (bracket orders handle SL/target)."""
        if self.order_mgr:
            self.order_mgr.sync_order_status()

    # ── EOD Exit ──────────────────────────────────────────────────────────

    def _eod_exit(self):
        """Exit all remaining positions at market price before close."""
        self.daily_log.log_event("EOD square-off: closing remaining positions")

        if self.mode == "paper":
            for pt in self.paper_trades:
                if pt["status"] == "OPEN":
                    trade: TradeOrder = pt["trade"]
                    yf_ticker = trade.ticker if trade.ticker.endswith(".NS") else f"{trade.ticker}.NS"
                    try:
                        tk = yf.Ticker(yf_ticker)
                        data = tk.history(period="1d", interval="1m")
                        if not data.empty:
                            exit_price = float(data.iloc[-1]["Close"])
                        else:
                            exit_price = trade.entry_price
                    except Exception:
                        exit_price = trade.entry_price

                    if trade.side == OrderSide.BUY:
                        pnl = (exit_price - trade.entry_price) * trade.quantity
                    else:
                        pnl = (trade.entry_price - exit_price) * trade.quantity

                    result = "WIN" if pnl > 0 else "LOSS"
                    self._paper_exit(pt, exit_price, pnl, result)
        else:
            if self.order_mgr:
                self.order_mgr.cancel_all_pending()
                closed = self.order_mgr.exit_all_positions()
                self.daily_log.log_event(f"Closed {closed} positions at market")

    # ── Reporting ─────────────────────────────────────────────────────────

    def _generate_report(self):
        """Generate and send daily summary."""
        summary = self.risk.daily_summary()
        report = (
            f"\n{'='*40}\n"
            f"  DAILY REPORT — {self.daily_log.date}\n"
            f"  Mode: {self.mode.upper()}\n"
            f"{'='*40}\n"
            f"  Stocks scanned:    {self.daily_log.scanned_stocks}\n"
            f"  Qualifying:        {self.daily_log.qualifying_stocks}\n"
            f"  Trades placed:     {self.daily_log.trades_placed}\n"
            f"  Wins:              {self.daily_log.wins}\n"
            f"  Losses:            {self.daily_log.losses}\n"
            f"  Total P&L:         ₹{self.daily_log.total_pnl:+.2f}\n"
            f"  Max Drawdown:      ₹{summary['max_drawdown']:.2f}\n"
            f"  Capital:           ₹{summary['capital']:,.0f}\n"
            f"{'='*40}\n"
        )
        self.daily_log.log_event(report)
        self._alert(report)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _connect_broker(self) -> bool:
        """Initialize broker connection."""
        try:
            config = BrokerConfig.from_env()
            self.broker = AngelBroker(config)
            if not self.broker.login():
                self.daily_log.log_event("FATAL: Broker login failed")
                return False
            self.mapper = SymbolMapper()
            self.order_mgr = OrderManager(self.broker, self.mapper)
            self.daily_log.log_event("Connected to Angel One")
            return True
        except Exception as exc:
            self.daily_log.log_event(f"FATAL: Broker connection failed: {exc}")
            return False

    def _wait_until(self, target_time: dt_time, msg: str):
        """Wait until a specific time of day."""
        now = datetime.now().time()
        if now >= target_time:
            return
        self.daily_log.log_event(msg)
        while datetime.now().time() < target_time:
            time.sleep(10)

    def _alert(self, message: str):
        """Send alert via callback (Telegram, etc.)."""
        if self.alert_callback:
            try:
                self.alert_callback(message)
            except Exception as exc:
                log.error("Alert callback failed: %s", exc)
