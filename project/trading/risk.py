"""Risk management — position sizing, daily limits, and kill switch.

Prevents catastrophic losses by enforcing:
    - Max capital per trade (25% default)
    - Max simultaneous trades (4 default)
    - Daily loss limit (3% of capital)
    - Per-trade risk limit (never risk more than 2% of capital on one trade)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    """All risk parameters in one place."""
    total_capital: float = 20_000.0
    max_capital_per_trade: float = 0.25       # 25% of capital per trade
    max_simultaneous_trades: int = 4
    daily_loss_limit_pct: float = 0.03        # 3% of capital
    per_trade_risk_pct: float = 0.02          # 2% of capital risked per trade
    max_trades_per_day: int = 8               # Don't overtrade
    skip_expiry_days: bool = True             # Skip Thur (weekly expiry)
    skip_first_minute: bool = True            # Wait for 15m candle to form


@dataclass
class DailyRiskState:
    """Tracks risk metrics throughout the trading day."""
    date: str = ""
    trades_taken: int = 0
    active_trades: int = 0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    peak_pnl: float = 0.0
    max_drawdown: float = 0.0
    is_halted: bool = False
    halt_reason: str = ""

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl


class RiskManager:
    """Enforces risk limits for the trading session."""

    def __init__(self, config: RiskConfig | None = None):
        self.config = config or RiskConfig()
        self.state = DailyRiskState(date=datetime.now().strftime("%Y-%m-%d"))

    def reset_daily(self):
        """Reset for a new trading day."""
        self.state = DailyRiskState(date=datetime.now().strftime("%Y-%m-%d"))

    # ── Pre-trade checks ──────────────────────────────────────────────────

    def can_take_trade(self) -> tuple[bool, str]:
        """Check if we're allowed to take another trade right now."""
        if self.state.is_halted:
            return False, f"Trading halted: {self.state.halt_reason}"

        if self.state.trades_taken >= self.config.max_trades_per_day:
            return False, f"Max trades reached ({self.config.max_trades_per_day})"

        if self.state.active_trades >= self.config.max_simultaneous_trades:
            return False, f"Max simultaneous trades ({self.config.max_simultaneous_trades})"

        daily_loss_limit = self.config.total_capital * self.config.daily_loss_limit_pct
        if self.state.realized_pnl <= -daily_loss_limit:
            self.state.is_halted = True
            self.state.halt_reason = (
                f"Daily loss limit hit: ₹{self.state.realized_pnl:.2f} "
                f"(limit: -₹{daily_loss_limit:.2f})"
            )
            return False, self.state.halt_reason

        return True, "OK"

    def calculate_position_size(
        self, entry_price: float, stoploss: float
    ) -> int:
        """Calculate how many shares to buy based on risk limits.

        Uses the smaller of:
        1. Max capital per trade (25% of total)
        2. Per-trade risk limit (2% of capital ÷ risk per share)

        Returns:
            Number of shares (integer, minimum 1)
        """
        if entry_price <= 0:
            return 0

        # Method 1: Max capital allocation
        max_capital = self.config.total_capital * self.config.max_capital_per_trade
        qty_by_capital = int(max_capital / entry_price)

        # Method 2: Risk-based sizing
        risk_per_share = abs(entry_price - stoploss)
        if risk_per_share <= 0:
            return 0
        max_risk_amount = self.config.total_capital * self.config.per_trade_risk_pct
        qty_by_risk = int(max_risk_amount / risk_per_share)

        # Take the smaller (more conservative) value
        quantity = min(qty_by_capital, qty_by_risk)
        return max(quantity, 1)  # At least 1 share

    def max_capital_for_trade(self) -> float:
        """How much capital can be allocated to the next trade."""
        return self.config.total_capital * self.config.max_capital_per_trade

    # ── Trade tracking ────────────────────────────────────────────────────

    def record_trade_entry(self):
        """Called when a new trade is entered."""
        self.state.trades_taken += 1
        self.state.active_trades += 1

    def record_trade_exit(self, pnl: float):
        """Called when a trade exits (win or loss)."""
        self.state.active_trades = max(0, self.state.active_trades - 1)
        self.state.realized_pnl += pnl

        # Update drawdown tracking
        self.state.peak_pnl = max(self.state.peak_pnl, self.state.realized_pnl)
        dd = self.state.peak_pnl - self.state.realized_pnl
        self.state.max_drawdown = max(self.state.max_drawdown, dd)

        # Check daily loss limit after exit
        daily_loss_limit = self.config.total_capital * self.config.daily_loss_limit_pct
        if self.state.realized_pnl <= -daily_loss_limit:
            self.state.is_halted = True
            self.state.halt_reason = (
                f"Daily loss limit hit: ₹{self.state.realized_pnl:.2f}"
            )
            log.warning("DAILY LOSS LIMIT HIT — halting all trading. P&L: ₹%.2f",
                        self.state.realized_pnl)

    def update_unrealized(self, unrealized_pnl: float):
        """Update unrealized P&L from open positions."""
        self.state.unrealized_pnl = unrealized_pnl

    # ── Kill switch ───────────────────────────────────────────────────────

    def halt_trading(self, reason: str = "Manual halt"):
        """Immediately stop all new trades."""
        self.state.is_halted = True
        self.state.halt_reason = reason
        log.warning("TRADING HALTED: %s", reason)

    def resume_trading(self):
        """Resume trading after a halt."""
        self.state.is_halted = False
        self.state.halt_reason = ""
        log.info("Trading resumed")

    # ── Day-of-week filters ───────────────────────────────────────────────

    def is_trading_day(self) -> tuple[bool, str]:
        """Check if today is a valid trading day."""
        now = datetime.now()
        weekday = now.weekday()  # 0=Mon, 6=Sun

        if weekday >= 5:
            return False, "Weekend"

        if self.config.skip_expiry_days and weekday == 3:  # Thursday
            return False, "Weekly expiry day — skipping (high noise)"

        return True, "OK"

    # ── Summary ───────────────────────────────────────────────────────────

    def daily_summary(self) -> dict:
        """Get a summary of today's risk state."""
        daily_limit = self.config.total_capital * self.config.daily_loss_limit_pct
        return {
            "date": self.state.date,
            "capital": self.config.total_capital,
            "trades_taken": self.state.trades_taken,
            "active_trades": self.state.active_trades,
            "realized_pnl": round(self.state.realized_pnl, 2),
            "max_drawdown": round(self.state.max_drawdown, 2),
            "daily_loss_limit": round(daily_limit, 2),
            "remaining_loss_budget": round(daily_limit + self.state.realized_pnl, 2),
            "is_halted": self.state.is_halted,
            "halt_reason": self.state.halt_reason,
        }
