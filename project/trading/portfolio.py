"""Portfolio tracker — tracks holdings, P&L over time, equity curve.

Stores data in JSON files under logs/portfolio/.
"""

import os
import json
from datetime import datetime, date
from dataclasses import dataclass, asdict

LOG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "logs", "portfolio"
)


@dataclass
class PortfolioSnapshot:
    date: str
    capital: float
    realized_pnl: float
    trades_taken: int
    wins: int
    losses: int
    win_rate: float
    cumulative_pnl: float


def save_daily_snapshot(
    capital: float,
    realized_pnl: float,
    trades: int,
    wins: int,
    losses: int,
):
    """Save today's portfolio snapshot."""
    os.makedirs(LOG_DIR, exist_ok=True)
    today = date.today().isoformat()

    wr = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0

    # Load existing history to compute cumulative
    history = load_portfolio_history()
    prev_cum = history[-1].cumulative_pnl if history else 0.0

    snapshot = PortfolioSnapshot(
        date=today,
        capital=capital,
        realized_pnl=realized_pnl,
        trades_taken=trades,
        wins=wins,
        losses=losses,
        win_rate=round(wr, 1),
        cumulative_pnl=round(prev_cum + realized_pnl, 2),
    )

    filepath = os.path.join(LOG_DIR, f"{today}.json")
    with open(filepath, "w") as f:
        json.dump(asdict(snapshot), f, indent=2)


def load_portfolio_history() -> list[PortfolioSnapshot]:
    """Load all portfolio snapshots sorted by date."""
    if not os.path.exists(LOG_DIR):
        return []

    snapshots = []
    for filename in sorted(os.listdir(LOG_DIR)):
        if filename.endswith(".json"):
            filepath = os.path.join(LOG_DIR, filename)
            with open(filepath) as f:
                data = json.load(f)
                snapshots.append(PortfolioSnapshot(**data))
    return snapshots


def get_portfolio_summary() -> dict:
    """Get overall portfolio stats."""
    history = load_portfolio_history()
    if not history:
        return {
            "total_days": 0, "total_trades": 0, "total_wins": 0,
            "total_losses": 0, "total_pnl": 0.0, "best_day": 0.0,
            "worst_day": 0.0, "avg_daily_pnl": 0.0, "win_rate": 0.0,
            "current_capital": 0.0, "equity_curve": [],
        }

    total_trades = sum(h.trades_taken for h in history)
    total_wins = sum(h.wins for h in history)
    total_losses = sum(h.losses for h in history)
    pnls = [h.realized_pnl for h in history]

    return {
        "total_days": len(history),
        "total_trades": total_trades,
        "total_wins": total_wins,
        "total_losses": total_losses,
        "total_pnl": round(sum(pnls), 2),
        "best_day": round(max(pnls), 2) if pnls else 0.0,
        "worst_day": round(min(pnls), 2) if pnls else 0.0,
        "avg_daily_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0.0,
        "win_rate": round(total_wins / (total_wins + total_losses) * 100, 1) if (total_wins + total_losses) > 0 else 0.0,
        "current_capital": history[-1].capital + history[-1].cumulative_pnl,
        "equity_curve": [{"date": h.date, "pnl": h.cumulative_pnl} for h in history],
    }
