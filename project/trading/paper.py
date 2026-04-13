"""Paper trading engine — simulates live trading with real prices, no real money.

This is the safe way to validate the strategy before going live.
It logs every trade as if it were real, tracks P&L, and generates reports.

Usage:
    from project.trading.paper import run_paper_trading
    log = run_paper_trading(capital=20000)
"""

import os
import json
import logging
from datetime import datetime

from project.trading.executor import TradingExecutor, DailyLog

log = logging.getLogger(__name__)

PAPER_LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "logs", "paper_trades"
)


def run_paper_trading(
    capital: float = 20_000.0,
    gap_threshold: float = 4.0,
    vol_threshold: float = 2.5,
    top_n: int = 4,
    symbols: list[str] | None = None,
    alert_callback=None,
) -> DailyLog:
    """Run a full paper trading session for today.

    Args:
        capital: Starting capital
        gap_threshold: Min gap % to qualify (default 4.0 = proven PF 2.055)
        vol_threshold: Min relative volume (default 2.5)
        top_n: Max simultaneous trades
        symbols: Stock universe (None = all NSE)
        alert_callback: Function called with alert messages

    Returns:
        DailyLog with all events and trade results
    """
    executor = TradingExecutor(
        mode="paper",
        capital=capital,
        gap_threshold=gap_threshold,
        vol_threshold=vol_threshold,
        top_n=top_n,
        symbols=symbols,
        alert_callback=alert_callback,
    )

    daily_log = executor.run()

    # Save to file
    _save_paper_log(daily_log, executor.paper_trades)

    return daily_log


def run_paper_scan_only(
    capital: float = 20_000.0,
    gap_threshold: float = 4.0,
    vol_threshold: float = 2.5,
    symbols: list[str] | None = None,
) -> list[dict]:
    """Run just the scan phase (no monitoring) — useful for UI integration.

    Returns list of qualifying stocks with trade details.
    """
    executor = TradingExecutor(
        mode="paper",
        capital=capital,
        gap_threshold=gap_threshold,
        vol_threshold=vol_threshold,
        symbols=symbols,
    )

    candidates = executor._scan_stocks()
    if not candidates:
        return []

    top = executor._rank_and_select(candidates)

    results = []
    for pick in top:
        qty = executor.risk.calculate_position_size(pick.entry, pick.stoploss)
        risk_amount = pick.risk * qty
        reward_amount = (pick.target - pick.entry) * qty if pick.direction == "LONG" else (pick.entry - pick.target) * qty

        results.append({
            "ticker": pick.ticker,
            "direction": pick.direction,
            "gap_pct": round(pick.gap_pct, 2),
            "rel_vol": round(pick.rel_vol, 2),
            "entry": pick.entry,
            "stoploss": pick.stoploss,
            "target": pick.target,
            "quantity": qty,
            "risk_amount": round(risk_amount, 2),
            "reward_amount": round(abs(reward_amount), 2),
            "score": round(pick.model_score, 2),
        })

    return results


def _save_paper_log(daily_log: DailyLog, paper_trades: list[dict]):
    """Persist paper trade log to disk for review."""
    os.makedirs(PAPER_LOG_DIR, exist_ok=True)
    filename = f"paper_{daily_log.date}.json"
    filepath = os.path.join(PAPER_LOG_DIR, filename)

    trades_data = []
    for pt in paper_trades:
        trade = pt["trade"]
        trades_data.append({
            "ticker": trade.ticker,
            "side": trade.side.value,
            "quantity": trade.quantity,
            "entry_price": trade.entry_price,
            "stoploss": trade.stoploss,
            "target": trade.target,
            "exit_price": trade.exit_price,
            "pnl": round(trade.pnl, 2),
            "status": pt["status"],
            "placed_at": trade.placed_at,
            "exited_at": trade.exited_at,
        })

    log_data = {
        "date": daily_log.date,
        "scanned": daily_log.scanned_stocks,
        "qualifying": daily_log.qualifying_stocks,
        "trades_placed": daily_log.trades_placed,
        "wins": daily_log.wins,
        "losses": daily_log.losses,
        "total_pnl": round(daily_log.total_pnl, 2),
        "trades": trades_data,
        "events": daily_log.events,
    }

    with open(filepath, "w") as f:
        json.dump(log_data, f, indent=2)

    log.info("Paper trade log saved: %s", filepath)


def get_paper_trade_history() -> list[dict]:
    """Load all paper trade logs for display in UI."""
    if not os.path.exists(PAPER_LOG_DIR):
        return []

    logs = []
    for filename in sorted(os.listdir(PAPER_LOG_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(PAPER_LOG_DIR, filename)
            with open(filepath) as f:
                logs.append(json.load(f))
    return logs
