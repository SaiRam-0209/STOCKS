"""Auto-scheduler — runs the trading bot at 9:15 AM IST daily.

Can be run as:
    python -m project.trading.scheduler          # foreground
    nohup python -m project.trading.scheduler &   # background

Or deployed as a systemd service / cron job.
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from project.trading.executor import TradingExecutor
from project.alerts.telegram import TelegramAlert

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/scheduler.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)


def _get_alert():
    tg = TelegramAlert()
    return tg.send if tg.is_enabled else None


def morning_scan_job():
    """Run at 9:15 AM — the main daily trading session."""
    now = datetime.now()
    weekday = now.weekday()
    if weekday >= 5:
        log.info("Weekend — skipping")
        return

    log.info("=" * 50)
    log.info("MORNING SCAN — %s", now.strftime("%Y-%m-%d %H:%M"))
    log.info("=" * 50)

    alert_fn = _get_alert()
    if alert_fn:
        alert_fn(f"🌅 Good morning! Starting daily scan at {now.strftime('%H:%M')}...")

    capital = float(os.getenv("TRADING_CAPITAL", "20000"))
    mode = os.getenv("TRADING_MODE", "paper")

    executor = TradingExecutor(
        mode=mode,
        capital=capital,
        gap_threshold=4.0,
        vol_threshold=2.5,
        top_n=4,
        alert_callback=alert_fn,
    )

    daily_log = executor.run()
    log.info("Session complete: %d trades, P&L ₹%.2f",
             daily_log.trades_placed, daily_log.total_pnl)


def pre_market_scan_job():
    """Run at 9:00 AM — early scan using previous day's data to preview candidates."""
    alert_fn = _get_alert()
    if not alert_fn:
        return

    now = datetime.now()
    if now.weekday() >= 5:
        return

    log.info("Pre-market scan starting...")
    try:
        from project.trading.paper import run_paper_scan_only
        results = run_paper_scan_only(
            capital=float(os.getenv("TRADING_CAPITAL", "20000")),
            gap_threshold=3.0,  # Slightly lower for preview
            vol_threshold=2.0,
        )

        if results:
            msg = f"🔍 <b>Pre-Market Preview</b> — {len(results)} stocks on radar:\n\n"
            for r in results[:5]:
                msg += (
                    f"{'🟢' if r['direction']=='LONG' else '🔴'} "
                    f"<b>{r['ticker']}</b> Gap {r['gap_pct']:+.1f}% "
                    f"Vol {r['rel_vol']:.1f}x\n"
                )
            msg += "\n<i>Full scan at 9:30 AM after first candle closes</i>"
            alert_fn(msg)
        else:
            alert_fn("🔍 Pre-market: No obvious candidates yet. Will scan again at 9:30.")

    except Exception as exc:
        log.error("Pre-market scan failed: %s", exc)


def evening_report_job():
    """Run at 4:00 PM — send end-of-day summary."""
    alert_fn = _get_alert()
    if not alert_fn:
        return

    now = datetime.now()
    if now.weekday() >= 5:
        return

    from project.trading.paper import get_paper_trade_history
    history = get_paper_trade_history()
    if history:
        today = now.strftime("%Y-%m-%d")
        today_log = next((h for h in history if h["date"] == today), None)
        if today_log:
            total = today_log["wins"] + today_log["losses"]
            wr = (today_log["wins"] / total * 100) if total > 0 else 0
            emoji = "📈" if today_log["total_pnl"] >= 0 else "📉"
            msg = (
                f"{emoji} <b>End of Day Summary</b>\n"
                f"━━━━━━━━━━━━━━━\n"
                f"Trades: {total}\n"
                f"Wins: {today_log['wins']} | Losses: {today_log['losses']}\n"
                f"Win Rate: {wr:.0f}%\n"
                f"P&L: ₹{today_log['total_pnl']:+.2f}\n"
                f"━━━━━━━━━━━━━━━"
            )
            alert_fn(msg)


def main():
    os.makedirs("logs", exist_ok=True)
    log.info("Scheduler started. Waiting for scheduled times...")

    alert_fn = _get_alert()
    if alert_fn:
        alert_fn("🤖 <b>Scheduler started!</b>\n\nDaily schedule:\n• 9:00 AM — Pre-market preview\n• 9:15 AM — Main trading session\n• 4:00 PM — End of day report")

    # Schedule jobs (IST times)
    schedule.every().day.at("09:00").do(pre_market_scan_job)
    schedule.every().day.at("09:15").do(morning_scan_job)
    schedule.every().day.at("16:00").do(evening_report_job)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
