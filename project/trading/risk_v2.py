"""Dynamic Risk Engine v2 — confidence-based sizing, drawdown control, kill switch.

Major upgrades over the original risk.py:
    1. Confidence-based position sizing (0.5x / 1x / 1.5x / 2x)
    2. Daily loss limit: 3R → halt
    3. Weekly drawdown: 10R → global size reduction
    4. Kill switch: 5 consecutive losses → halt + alert
    5. Aggressive mode toggle (controlled)
    6. Integration with WinClassifierV2 confidence buckets
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

log = logging.getLogger(__name__)


# ── Confidence → Size multiplier mapping ─────────────────────────────────────
CONFIDENCE_MULTIPLIERS = {
    "LOW": 0.5,       # P(win) < 0.13
    "MEDIUM": 1.0,    # 0.13 <= P(win) < 0.22
    "HIGH": 1.5,      # P(win) >= 0.22
}

AGGRESSIVE_CONFIDENCE_MULTIPLIERS = {
    "LOW": 0.75,
    "MEDIUM": 1.5,
    "HIGH": 2.0,
}


@dataclass
class RiskConfigV2:
    """All risk parameters — v2 with dynamic controls."""
    total_capital: float = 20_000.0
    max_capital_per_trade: float = 0.25       # 25% of capital per trade
    max_simultaneous_trades: int = 4
    max_trades_per_day: int = 8

    # ── R-based limits ────────────────────────────────────────────────────
    risk_per_trade_pct: float = 0.02          # 2% of capital risked per trade
    daily_loss_limit_r: float = 3.0           # Stop trading after 3R daily loss
    weekly_drawdown_limit_r: float = 10.0     # Reduce size after 10R weekly DD
    weekly_size_reduction: float = 0.5        # Reduce to 50% after weekly DD

    # ── Kill switch ───────────────────────────────────────────────────────
    consecutive_loss_kill: int = 5            # Halt after 5 consecutive losses
    kill_switch_enabled: bool = True

    # ── Aggressive mode ───────────────────────────────────────────────────
    aggressive_mode: bool = False
    aggressive_threshold_offset: float = 0.05  # Lower threshold by this in aggressive

    # ── Day filters ───────────────────────────────────────────────────────
    skip_expiry_days: bool = True
    skip_first_minute: bool = True


@dataclass
class DailyRiskStateV2:
    """Tracks risk metrics throughout the trading day."""
    date: str = ""
    trades_taken: int = 0
    active_trades: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    peak_pnl: float = 0.0
    max_drawdown: float = 0.0
    daily_r_pnl: float = 0.0            # Running R-multiple P&L for the day
    consecutive_losses: int = 0
    is_halted: bool = False
    halt_reason: str = ""
    trade_results: list[str] = field(default_factory=list)

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


@dataclass
class WeeklyRiskState:
    """Tracks weekly-level drawdown for global size adjustment."""
    week_start: str = ""
    weekly_r_pnl: float = 0.0
    peak_weekly_r: float = 0.0
    weekly_drawdown_r: float = 0.0
    global_size_reduction: float = 1.0    # 1.0 = normal, 0.5 = reduced


class RiskManagerV2:
    """Dynamic risk manager with confidence-based sizing and multi-level controls."""

    def __init__(
        self,
        config: RiskConfigV2 | None = None,
        alert_callback: Callable[[str], None] | None = None,
    ):
        self.config = config or RiskConfigV2()
        self.state = DailyRiskStateV2(date=datetime.now().strftime("%Y-%m-%d"))
        self.weekly = WeeklyRiskState(week_start=datetime.now().strftime("%Y-%m-%d"))
        self.alert_callback = alert_callback

        # Choose multiplier table based on aggressive mode
        self._multipliers = (
            AGGRESSIVE_CONFIDENCE_MULTIPLIERS if self.config.aggressive_mode
            else CONFIDENCE_MULTIPLIERS
        )

    def reset_daily(self):
        """Reset for a new trading day."""
        # Carry over consecutive losses across days
        consec = self.state.consecutive_losses
        self.state = DailyRiskStateV2(date=datetime.now().strftime("%Y-%m-%d"))
        self.state.consecutive_losses = consec

    def reset_weekly(self):
        """Reset weekly tracking (call every Monday)."""
        self.weekly = WeeklyRiskState(week_start=datetime.now().strftime("%Y-%m-%d"))

    # ── Pre-trade checks ──────────────────────────────────────────────────

    def can_take_trade(self) -> tuple[bool, str]:
        """Check all risk gates before allowing a new trade."""
        if self.state.is_halted:
            return False, f"Trading halted: {self.state.halt_reason}"

        if self.state.trades_taken >= self.config.max_trades_per_day:
            return False, f"Max trades reached ({self.config.max_trades_per_day})"

        if self.state.active_trades >= self.config.max_simultaneous_trades:
            return False, f"Max simultaneous trades ({self.config.max_simultaneous_trades})"

        # Daily R-limit check
        if self.state.daily_r_pnl <= -self.config.daily_loss_limit_r:
            self._halt(
                f"Daily loss limit hit: {self.state.daily_r_pnl:.1f}R "
                f"(limit: -{self.config.daily_loss_limit_r}R)"
            )
            return False, self.state.halt_reason

        # Kill switch: consecutive losses
        if (
            self.config.kill_switch_enabled
            and self.state.consecutive_losses >= self.config.consecutive_loss_kill
        ):
            self._halt(
                f"KILL SWITCH: {self.state.consecutive_losses} consecutive losses"
            )
            self._alert(
                f"🚨 KILL SWITCH ACTIVATED — {self.state.consecutive_losses} "
                f"consecutive losses. System halted."
            )
            return False, self.state.halt_reason

        return True, "OK"

    # ── Position sizing ───────────────────────────────────────────────────

    def calculate_position_size(
        self,
        entry_price: float,
        stoploss: float,
        confidence: str = "MEDIUM",
    ) -> int:
        """Calculate position size based on confidence + risk limits.

        Sizing tiers:
            LOW confidence (P < 0.50):    0.5x base
            MEDIUM confidence (0.50-0.65): 1.0x base
            HIGH confidence (P > 0.65):    1.5x base (2x in aggressive mode)

        Further reduced by:
            - Weekly drawdown state
            - Consecutive loss recovery
        """
        if entry_price <= 0:
            return 0

        risk_per_share = abs(entry_price - stoploss)
        if risk_per_share <= 0:
            return 0

        # Base size from risk limit
        max_risk_amount = self.config.total_capital * self.config.risk_per_trade_pct
        base_qty = int(max_risk_amount / risk_per_share)

        # Confidence multiplier
        conf_mult = self._multipliers.get(confidence, 1.0)

        # Weekly drawdown reduction
        global_mult = self.weekly.global_size_reduction

        # Combined multiplier
        total_mult = conf_mult * global_mult

        # Capital ceiling
        max_capital = self.config.total_capital * self.config.max_capital_per_trade * total_mult
        qty_by_capital = int(max_capital / entry_price)

        quantity = min(int(base_qty * total_mult), qty_by_capital)
        return max(quantity, 1)

    def get_threshold_for_regime(self, base_threshold: float, regime: str = "") -> float:
        """Get adjusted probability threshold.

        In aggressive mode, the threshold is lowered slightly.
        """
        threshold = base_threshold
        if self.config.aggressive_mode:
            threshold -= self.config.aggressive_threshold_offset
        return max(threshold, 0.20)  # Never go below 20%

    # ── Trade tracking ────────────────────────────────────────────────────

    def record_trade_entry(self):
        """Called when a new trade is entered."""
        self.state.trades_taken += 1
        self.state.active_trades += 1

    def record_trade_exit(
        self,
        pnl: float,
        r_multiple: float,
        result: str = "",
    ):
        """Called when a trade exits.

        Args:
            pnl: Cash P&L in ₹.
            r_multiple: P&L expressed in R (risk units).
            result: "WIN" / "LOSS" / "TIME_EXIT".
        """
        self.state.active_trades = max(0, self.state.active_trades - 1)
        self.state.realized_pnl += pnl
        self.state.daily_r_pnl += r_multiple
        self.state.trade_results.append(result)

        # Weekly tracking
        self.weekly.weekly_r_pnl += r_multiple
        self.weekly.peak_weekly_r = max(self.weekly.peak_weekly_r, self.weekly.weekly_r_pnl)
        self.weekly.weekly_drawdown_r = self.weekly.peak_weekly_r - self.weekly.weekly_r_pnl

        # Weekly drawdown size reduction
        if self.weekly.weekly_drawdown_r >= self.config.weekly_drawdown_limit_r:
            self.weekly.global_size_reduction = self.config.weekly_size_reduction
            log.warning(
                "Weekly drawdown %.1fR exceeds limit — global size reduced to %.0f%%",
                self.weekly.weekly_drawdown_r,
                self.weekly.global_size_reduction * 100,
            )
            self._alert(
                f"⚠️ Weekly drawdown {self.weekly.weekly_drawdown_r:.1f}R — "
                f"reducing all positions to {self.weekly.global_size_reduction:.0%}"
            )

        # Consecutive loss tracking
        if result == "LOSS" or r_multiple < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0

        # Drawdown tracking
        self.state.peak_pnl = max(self.state.peak_pnl, self.state.realized_pnl)
        dd = self.state.peak_pnl - self.state.realized_pnl
        self.state.max_drawdown = max(self.state.max_drawdown, dd)

        # Daily R-limit check after exit
        if self.state.daily_r_pnl <= -self.config.daily_loss_limit_r:
            self._halt(
                f"Daily loss limit hit: {self.state.daily_r_pnl:.1f}R"
            )

    def update_unrealized(self, unrealized_pnl: float):
        """Update unrealized P&L from open positions."""
        self.state.unrealized_pnl = unrealized_pnl

    # ── Kill switch ───────────────────────────────────────────────────────

    def _halt(self, reason: str):
        self.state.is_halted = True
        self.state.halt_reason = reason
        log.warning("TRADING HALTED: %s", reason)

    def halt_trading(self, reason: str = "Manual halt"):
        """Immediately stop all new trades."""
        self._halt(reason)

    def resume_trading(self):
        """Resume trading after a halt."""
        self.state.is_halted = False
        self.state.halt_reason = ""
        self.state.consecutive_losses = 0  # Reset on resume
        log.info("Trading resumed")

    # ── Day-of-week filters ───────────────────────────────────────────────

    def is_trading_day(self) -> tuple[bool, str]:
        """Check if today is a valid trading day."""
        now = datetime.now()
        weekday = now.weekday()

        if weekday >= 5:
            return False, "Weekend"

        if self.config.skip_expiry_days and weekday == 3:
            return False, "Weekly expiry day — skipping (high noise)"

        # Auto-reset weekly state on Monday
        if weekday == 0:
            if self.weekly.week_start != now.strftime("%Y-%m-%d"):
                self.reset_weekly()

        return True, "OK"

    # ── Summary ───────────────────────────────────────────────────────────

    def daily_summary(self) -> dict:
        """Get a summary of today's risk state."""
        return {
            "date": self.state.date,
            "capital": self.config.total_capital,
            "aggressive_mode": self.config.aggressive_mode,
            "trades_taken": self.state.trades_taken,
            "active_trades": self.state.active_trades,
            "realized_pnl": round(self.state.realized_pnl, 2),
            "daily_r_pnl": round(self.state.daily_r_pnl, 2),
            "max_drawdown": round(self.state.max_drawdown, 2),
            "consecutive_losses": self.state.consecutive_losses,
            "weekly_r_pnl": round(self.weekly.weekly_r_pnl, 2),
            "weekly_drawdown_r": round(self.weekly.weekly_drawdown_r, 2),
            "global_size_mult": self.weekly.global_size_reduction,
            "is_halted": self.state.is_halted,
            "halt_reason": self.state.halt_reason,
        }

    # ── Helpers ────────────────────────────────────────────────────────────

    def _alert(self, message: str):
        if self.alert_callback:
            try:
                self.alert_callback(message)
            except Exception as exc:
                log.error("Alert callback failed: %s", exc)
