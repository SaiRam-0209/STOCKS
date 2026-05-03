"""Trading executor v2 — uses all v2 modules (risk, classifier, filters).

Drop-in replacement for executor.py. Uses:
    - WinClassifierV2 (20 curated features)
    - RiskManagerV2 (confidence-based sizing, kill switch)
    - Execution filters (spread, volatility, volume)
    - News risk filter (earnings/regulatory → skip)
    - Fundamental filter (weak → reduce confidence)
    - Market regime detection

Usage:
    executor = TradingExecutorV2(mode="paper")
    executor.run()
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, time as dt_time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf

from project.broker.angel import AngelBroker, BrokerConfig
from project.broker.orders import OrderManager, OrderSide, OrderStatus, TradeOrder
from project.broker.symbols import SymbolMapper
from project.trading.risk_v2 import RiskManagerV2, RiskConfigV2
from project.trading.execution_filters import check_execution_filters, ExecutionFilterConfig
from project.features.indicators import gap_percentage, relative_volume
from project.features.regime import detect_regime, MarketRegime, compute_regime_features
from project.data.symbols_fetcher import get_all_nse_stocks

log = logging.getLogger(__name__)

# ── Market hours (IST) ───────────────────────────────────────────────────
MARKET_OPEN = dt_time(9, 15)
SCAN_TIME = dt_time(9, 30)
EOD_EXIT_TIME = dt_time(15, 15)
MARKET_CLOSE = dt_time(15, 30)

# ── Defaults ─────────────────────────────────────────────────────────────
DEFAULT_GAP_THRESHOLD = 2.0
DEFAULT_VOL_THRESHOLD = 1.5
DEFAULT_TOP_N = 4
SLIPPAGE_PCT = 0.001
TRAILING_SL_ENABLED = True
MIN_STOCK_PRICE = 50.0
MAX_STOCK_PRICE = 10000.0


@dataclass
class ScanResult:
    ticker: str
    direction: str
    gap_pct: float
    rel_vol: float
    entry: float
    stoploss: float
    target: float
    risk: float
    model_score: float = 0.0
    confidence: str = "MEDIUM"


@dataclass
class DailyLog:
    date: str = ""
    scanned_stocks: int = 0
    qualifying_stocks: int = 0
    trades_placed: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    regime: str = "SIDEWAYS"
    events: list[str] = field(default_factory=list)

    def log_event(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{ts}] {msg}")
        log.info(msg)


class TradingExecutorV2:
    """V2 executor with full dynamic risk engine + all filters."""

    def __init__(
        self,
        mode: str = "paper",
        capital: float = 20_000.0,
        gap_threshold: float = DEFAULT_GAP_THRESHOLD,
        vol_threshold: float = DEFAULT_VOL_THRESHOLD,
        top_n: int = DEFAULT_TOP_N,
        symbols: list[str] | None = None,
        aggressive_mode: bool = False,
        alert_callback=None,
    ):
        self.mode = mode
        self.gap_threshold = gap_threshold
        self.vol_threshold = vol_threshold
        self.top_n = top_n
        self.alert_callback = alert_callback
        self.daily_log = DailyLog(date=datetime.now().strftime("%Y-%m-%d"))

        # V2 Risk manager with aggressive mode
        self.risk = RiskManagerV2(
            RiskConfigV2(total_capital=capital, aggressive_mode=aggressive_mode),
            alert_callback=alert_callback,
        )

        # Execution filter config
        self.exec_filter_config = ExecutionFilterConfig()

        # Broker
        self.broker: AngelBroker | None = None
        self.order_mgr: OrderManager | None = None
        self.mapper: SymbolMapper | None = None
        self._symbols = symbols
        self.paper_trades: list[dict] = []

        # Regime + Nifty
        self._nifty_df: pd.DataFrame | None = None
        self._regime = MarketRegime.SIDEWAYS

        # News cache
        self._news_items: list[dict] = []

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self):
        self.daily_log.log_event(f"Starting V2 executor in {self.mode.upper()} mode")
        self.daily_log.log_event(
            f"Capital: ₹{self.risk.config.total_capital:,.0f} | "
            f"Aggressive: {'ON' if self.risk.config.aggressive_mode else 'OFF'}"
        )

        ok, reason = self.risk.is_trading_day()
        if not ok:
            self.daily_log.log_event(f"Not a trading day: {reason}")
            return self.daily_log

        # Detect market regime
        self._detect_regime()

        # Fetch news for risk filtering
        self._fetch_news()

        # Connect broker (live mode)
        if self.mode == "live" and not self._connect_broker():
            return self.daily_log

        self._wait_until(SCAN_TIME, "Waiting for first 15-min candle...")

        candidates = self._scan_stocks()
        if not candidates:
            self.daily_log.log_event("No qualifying stocks today")
            self._alert("No qualifying stocks today. Sitting out.")
            return self.daily_log

        top_picks = self._rank_and_select(candidates)
        self._place_orders(top_picks)
        self._monitor_loop()
        self._eod_exit()
        self._generate_report()

        if self.broker:
            self.broker.logout()

        return self.daily_log

    # ── Regime detection ──────────────────────────────────────────────────

    def _detect_regime(self):
        try:
            self._nifty_df = yf.Ticker("^NSEI").history(period="90d", interval="1d")
            if hasattr(self._nifty_df.columns, "levels"):
                self._nifty_df.columns = self._nifty_df.columns.droplevel(1)
            if len(self._nifty_df) >= 65:
                self._regime = detect_regime(self._nifty_df)
            else:
                self._regime = MarketRegime.SIDEWAYS
                self._nifty_df = None
        except Exception as exc:
            self._regime = MarketRegime.SIDEWAYS
            self._nifty_df = None
            self.daily_log.log_event(f"Regime detection failed: {exc}")

        self.daily_log.regime = self._regime.value
        self.daily_log.log_event(f"Market regime: {self._regime.value}")

        if self._regime == MarketRegime.HIGH_VOLATILITY:
            self.daily_log.log_event("⚠️ HIGH VOLATILITY — positions will be reduced")

    # ── News fetch ────────────────────────────────────────────────────────

    def _fetch_news(self):
        try:
            from project.news.fetcher import fetch_news
            self._news_items = fetch_news(max_age_hours=24)
            self.daily_log.log_event(f"Fetched {len(self._news_items)} news items")
        except Exception as exc:
            self._news_items = []
            self.daily_log.log_event(f"News fetch skipped: {exc}")

    # ── Scanning ──────────────────────────────────────────────────────────

    def _scan_stocks(self) -> list[ScanResult]:
        self.daily_log.log_event("Scanning for ORB setups...")

        if self._symbols is None:
            self._symbols = get_all_nse_stocks()
            if not self._symbols:
                from project.data.symbols import ALL_STOCKS
                self._symbols = ALL_STOCKS

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
        yf_ticker = ticker if ticker.endswith(".NS") else f"{ticker}.NS"
        tk = yf.Ticker(yf_ticker)

        intra = tk.history(period="5d", interval="15m")
        if intra.empty:
            return None

        today_intra = intra[intra.index.date == today]
        if today_intra.empty:
            return None

        daily = tk.history(period="30d", interval="1d")
        if daily.empty:
            return None
        completed_daily = daily[daily.index.date < today]
        if len(completed_daily) < 2:
            return None

        first_candle = today_intra.iloc[0]
        today_open = float(first_candle["Open"])
        candle_high = float(first_candle["High"])
        candle_low = float(first_candle["Low"])
        candle_range = candle_high - candle_low

        prev_close = float(completed_daily.iloc[-1]["Close"])
        gap_pct = gap_percentage(today_open, prev_close)

        today_vol = float(first_candle["Volume"])
        avg_vol = float(completed_daily["Volume"].tail(10).mean())
        if avg_vol <= 0:
            return None
        rel_vol = relative_volume(today_vol * 25, avg_vol)

        if abs(gap_pct) < self.gap_threshold or rel_vol < self.vol_threshold:
            return None

        # ── Execution filters ─────────────────────────────────────────
        filt = check_execution_filters(
            today_open, candle_high, candle_low, today_vol,
            completed_daily, self.exec_filter_config,
        )
        if not filt.passed:
            log.debug("Execution filter blocked %s: %s", ticker, filt.reason)
            return None

        # ── News risk filter ──────────────────────────────────────────
        from project.news.filter import filter_by_news
        news_result = filter_by_news(ticker, self._news_items)
        if news_result.action == "SKIP":
            self.daily_log.log_event(f"  🗞️ {ticker} SKIPPED: {news_result.reason}")
            return None

        # Direction
        direction = "LONG" if gap_pct > 0 else "SHORT"

        # Only allow shorts in bearish regimes
        if direction == "SHORT" and self._regime not in (
            MarketRegime.TRENDING_DOWN, MarketRegime.HIGH_VOLATILITY
        ):
            return None

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

        return ScanResult(
            ticker=ticker, direction=direction,
            gap_pct=gap_pct, rel_vol=rel_vol,
            entry=round(entry, 2), stoploss=round(stoploss, 2),
            target=round(target, 2), risk=round(risk, 2),
        )

    # ── Ranking with WinClassifierV2 ──────────────────────────────────────

    def _rank_and_select(self, candidates: list[ScanResult]) -> list[ScanResult]:
        ai_filtered = False
        try:
            from project.ml.win_classifier_v2 import WinClassifierV2, CURATED_FEATURES

            clf = WinClassifierV2()
            if clf.load():
                self.daily_log.log_event(
                    f"Using WinClassifierV2 ({len(CURATED_FEATURES)} features)"
                )

                scored = []
                for c in candidates:
                    try:
                        yf_ticker = c.ticker if c.ticker.endswith(".NS") else f"{c.ticker}.NS"
                        daily = yf.Ticker(yf_ticker).history(period="90d", interval="1d")
                        if len(daily) < 30:
                            continue

                        feat_vec = clf.extract_features(
                            daily, len(daily) - 1, nifty_df=self._nifty_df
                        )
                        if feat_vec is None:
                            continue

                        take, prob, confidence = clf.should_take_trade(
                            feat_vec, regime=self._regime.value
                        )
                        c.model_score = prob
                        c.confidence = confidence

                        # Fundamental bias
                        try:
                            from project.data.fundamentals import assess_fundamentals
                            fund = assess_fundamentals(c.ticker)
                            if fund.confidence_penalty > 0:
                                c.model_score = max(0, prob - fund.confidence_penalty)
                                self.daily_log.log_event(
                                    f"  📊 {c.ticker} fundamentals={fund.quality} "
                                    f"(penalty: -{fund.confidence_penalty:.0%})"
                                )
                        except Exception:
                            pass

                        # News size reduction
                        from project.news.filter import filter_by_news
                        nr = filter_by_news(c.ticker, self._news_items)
                        if nr.action == "REDUCE":
                            c.confidence = "LOW"  # Force smaller size
                            self.daily_log.log_event(
                                f"  🗞️ {c.ticker} size REDUCED: {nr.reason}"
                            )

                        if take:
                            scored.append(c)
                            self.daily_log.log_event(
                                f"  ✅ {c.ticker} P(win)={prob:.0%} "
                                f"conf={confidence} gap={c.gap_pct:+.1f}%"
                            )
                        else:
                            self.daily_log.log_event(
                                f"  ❌ {c.ticker} P(win)={prob:.0%} — SKIPPED"
                            )
                    except Exception as exc:
                        log.debug("Classifier error for %s: %s", c.ticker, exc)

                candidates = scored
                ai_filtered = True
        except Exception as exc:
            self.daily_log.log_event(f"WinClassifierV2 unavailable: {exc}")

        if not ai_filtered:
            for c in candidates:
                c.model_score = min(abs(c.gap_pct) * c.rel_vol / 100, 1.0)
            if candidates:
                self.daily_log.log_event("AI filter unavailable; using gap/volume fallback")

        candidates.sort(key=lambda x: x.model_score, reverse=True)
        top = candidates[:self.top_n]

        self.daily_log.log_event(
            f"Selected {len(top)}/{len(candidates)} | AI={'YES' if ai_filtered else 'NO'}"
        )
        return top

    # ── Order execution ───────────────────────────────────────────────────

    def _place_orders(self, picks: list[ScanResult]):
        for pick in picks:
            ok, reason = self.risk.can_take_trade()
            if not ok:
                self.daily_log.log_event(f"Risk check failed: {reason}")
                break

            quantity = self.risk.calculate_position_size(
                pick.entry, pick.stoploss, pick.confidence
            )
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
        if trade.side == OrderSide.BUY:
            trade.entry_price = round(trade.entry_price * (1 + SLIPPAGE_PCT), 2)
        else:
            trade.entry_price = round(trade.entry_price * (1 - SLIPPAGE_PCT), 2)

        trade.status = OrderStatus.PLACED
        trade.order_id = f"V2-PAPER-{len(self.paper_trades)+1}"
        trade.placed_at = datetime.now().strftime("%H:%M:%S")

        self.paper_trades.append({
            "trade": trade, "pick": pick,
            "status": "OPEN", "trail_sl": trade.stoploss,
            "breakeven_moved": False,
        })
        self.risk.record_trade_entry()
        self.daily_log.trades_placed += 1

        msg = (
            f"📋 V2 PAPER {trade.side.value} {trade.ticker} | "
            f"Qty: {trade.quantity} ({pick.confidence}) @ ₹{trade.entry_price:.2f} | "
            f"SL: ₹{trade.stoploss:.2f} | TGT: ₹{trade.target:.2f} | "
            f"P(win): {pick.model_score:.0%}"
        )
        self.daily_log.log_event(msg)
        self._alert(msg)

    def _live_place(self, trade: TradeOrder, pick: ScanResult):
        if not self.order_mgr:
            self.daily_log.log_event("ERROR: Order manager not initialized")
            return

        success = self.order_mgr.place_bracket_order(trade)
        if success:
            self.risk.record_trade_entry()
            self.daily_log.trades_placed += 1
            self.daily_log.log_event(
                f"🟢 LIVE {trade.side.value} {trade.ticker} | "
                f"Qty: {trade.quantity} ({pick.confidence})"
            )
        else:
            self.daily_log.log_event(f"Order REJECTED for {trade.ticker}")

    # ── Monitoring ────────────────────────────────────────────────────────

    def _monitor_loop(self):
        self.daily_log.log_event("Monitoring positions...")
        while datetime.now().time() < EOD_EXIT_TIME:
            if self.mode == "paper":
                self._paper_monitor()
            else:
                self._live_monitor()
            if self.risk.state.is_halted:
                self.daily_log.log_event(f"HALTED: {self.risk.state.halt_reason}")
                break
            time.sleep(30)

    def _paper_monitor(self):
        for pt in self.paper_trades:
            if pt["status"] != "OPEN":
                continue

            trade: TradeOrder = pt["trade"]
            yf_ticker = trade.ticker if trade.ticker.endswith(".NS") else f"{trade.ticker}.NS"
            try:
                data = yf.Ticker(yf_ticker).history(period="1d", interval="1m")
                if data.empty:
                    continue
                current_high = float(data.iloc[-1]["High"])
                current_low = float(data.iloc[-1]["Low"])
            except Exception:
                continue

            risk = abs(trade.entry_price - trade.stoploss)
            trail_sl = pt.get("trail_sl", trade.stoploss)

            if TRAILING_SL_ENABLED and risk > 0:
                if trade.side == OrderSide.BUY:
                    if current_high >= trade.entry_price + risk and not pt.get("breakeven_moved"):
                        trail_sl = trade.entry_price + 0.5
                        pt["breakeven_moved"] = True
                        pt["trail_sl"] = trail_sl
                else:
                    if current_low <= trade.entry_price - risk and not pt.get("breakeven_moved"):
                        trail_sl = trade.entry_price - 0.5
                        pt["breakeven_moved"] = True
                        pt["trail_sl"] = trail_sl

            if trade.side == OrderSide.BUY:
                if current_low <= trail_sl:
                    pnl = (trail_sl - trade.entry_price) * trade.quantity
                    r_mult = (trail_sl - trade.entry_price) / risk if risk > 0 else 0
                    result = "WIN" if pnl > 0 else "LOSS"
                    self._paper_exit(pt, trail_sl, pnl, r_mult, result)
                elif current_high >= trade.target:
                    pnl = (trade.target - trade.entry_price) * trade.quantity
                    r_mult = 2.0
                    self._paper_exit(pt, trade.target, pnl, r_mult, "WIN")
            else:
                if current_high >= trail_sl:
                    pnl = (trade.entry_price - trail_sl) * trade.quantity
                    r_mult = (trade.entry_price - trail_sl) / risk if risk > 0 else 0
                    result = "WIN" if pnl > 0 else "LOSS"
                    self._paper_exit(pt, trail_sl, pnl, r_mult, result)
                elif current_low <= trade.target:
                    pnl = (trade.entry_price - trade.target) * trade.quantity
                    r_mult = 2.0
                    self._paper_exit(pt, trade.target, pnl, r_mult, "WIN")

    def _paper_exit(self, pt: dict, exit_price: float, pnl: float, r_mult: float, result: str):
        trade: TradeOrder = pt["trade"]
        trade.exit_price = exit_price
        trade.pnl = pnl
        trade.status = OrderStatus.EXITED
        pt["status"] = result

        self.risk.record_trade_exit(pnl, r_mult, result)
        if result == "WIN":
            self.daily_log.wins += 1
        else:
            self.daily_log.losses += 1
        self.daily_log.total_pnl += pnl

        emoji = "✅" if result == "WIN" else "❌"
        msg = f"{emoji} {result} {trade.ticker} | ₹{pnl:+.2f} ({r_mult:+.1f}R)"
        self.daily_log.log_event(msg)
        self._alert(msg)

    def _live_monitor(self):
        if self.order_mgr:
            self.order_mgr.sync_order_status()

    # ── EOD Exit ──────────────────────────────────────────────────────────

    def _eod_exit(self):
        self.daily_log.log_event("EOD square-off")
        if self.mode == "paper":
            for pt in self.paper_trades:
                if pt["status"] == "OPEN":
                    trade: TradeOrder = pt["trade"]
                    yf_ticker = trade.ticker if trade.ticker.endswith(".NS") else f"{trade.ticker}.NS"
                    try:
                        data = yf.Ticker(yf_ticker).history(period="1d", interval="1m")
                        exit_price = float(data.iloc[-1]["Close"]) if not data.empty else trade.entry_price
                    except Exception:
                        exit_price = trade.entry_price

                    risk = abs(trade.entry_price - trade.stoploss)
                    if trade.side == OrderSide.BUY:
                        pnl = (exit_price - trade.entry_price) * trade.quantity
                    else:
                        pnl = (trade.entry_price - exit_price) * trade.quantity
                    r_mult = pnl / (risk * trade.quantity) if risk > 0 and trade.quantity > 0 else 0
                    result = "WIN" if pnl > 0 else "LOSS"
                    self._paper_exit(pt, exit_price, pnl, r_mult, result)
        else:
            if self.order_mgr:
                self.order_mgr.cancel_all_pending()
                self.order_mgr.exit_all_positions()

    # ── Report ────────────────────────────────────────────────────────────

    def _generate_report(self):
        summary = self.risk.daily_summary()
        report = (
            f"\n{'='*45}\n"
            f"  V2 DAILY REPORT — {self.daily_log.date}\n"
            f"  Mode: {self.mode.upper()} | Regime: {self.daily_log.regime}\n"
            f"{'='*45}\n"
            f"  Scanned:      {self.daily_log.scanned_stocks}\n"
            f"  Qualifying:   {self.daily_log.qualifying_stocks}\n"
            f"  Trades:       {self.daily_log.trades_placed}\n"
            f"  Wins:         {self.daily_log.wins}\n"
            f"  Losses:       {self.daily_log.losses}\n"
            f"  P&L:          ₹{self.daily_log.total_pnl:+.2f}\n"
            f"  Daily R:      {summary['daily_r_pnl']:+.1f}R\n"
            f"  Consecutive:  {summary['consecutive_losses']} losses\n"
            f"  Aggressive:   {'ON' if summary['aggressive_mode'] else 'OFF'}\n"
            f"{'='*45}\n"
        )
        self.daily_log.log_event(report)
        self._alert(report)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _connect_broker(self) -> bool:
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
        now = datetime.now().time()
        if now >= target_time:
            return
        self.daily_log.log_event(msg)
        while datetime.now().time() < target_time:
            time.sleep(10)

    def _alert(self, message: str):
        if self.alert_callback:
            try:
                self.alert_callback(message)
            except Exception as exc:
                log.error("Alert callback failed: %s", exc)
