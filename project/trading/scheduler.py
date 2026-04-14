"""Auto-scheduler — runs the trading bot on schedule.

Deployed on Railway.app as a worker process.
Runs 24/7 but only executes jobs during IST market hours.

Can also run locally:
    python -m project.trading.scheduler
"""

import os
import sys
import time
import logging
import schedule
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # Railway injects env vars directly

from project.trading.executor import TradingExecutor
from project.alerts.telegram import TelegramAlert

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

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


def _now_ist() -> datetime:
    """Get current time in IST regardless of server timezone."""
    return datetime.now(IST)


def _get_alert():
    tg = TelegramAlert()
    return tg.send if tg.is_enabled else None


def _is_weekday() -> bool:
    return _now_ist().weekday() < 5


def morning_scan_job():
    """Run at 9:30 AM IST — the main daily trading session."""
    if not _is_weekday():
        log.info("Weekend — skipping")
        return

    now = _now_ist()
    log.info("=" * 50)
    log.info("MORNING SCAN — %s", now.strftime("%Y-%m-%d %H:%M IST"))
    log.info("=" * 50)

    alert_fn = _get_alert()
    if alert_fn:
        alert_fn(f"🌅 Good morning! Starting daily scan at {now.strftime('%H:%M')} IST...")

    capital = float(os.getenv("TRADING_CAPITAL", "10000"))
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
    """Run at 9:00 AM IST — early scan to preview candidates."""
    if not _is_weekday():
        return

    alert_fn = _get_alert()
    if not alert_fn:
        return

    log.info("Pre-market scan starting...")
    try:
        from project.trading.paper import run_paper_scan_only
        results = run_paper_scan_only(
            capital=float(os.getenv("TRADING_CAPITAL", "10000")),
            gap_threshold=3.0,
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
    """Run at 4:00 PM IST — send end-of-day summary."""
    if not _is_weekday():
        return

    alert_fn = _get_alert()
    if not alert_fn:
        return

    from project.trading.paper import get_paper_trade_history
    history = get_paper_trade_history()
    if history:
        today = _now_ist().strftime("%Y-%m-%d")
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


def heartbeat_job():
    """Run every hour — log that the scheduler is alive."""
    now = _now_ist()
    log.info("Heartbeat — %s IST, scheduler alive", now.strftime("%H:%M"))


def main():
    log.info("=" * 50)
    log.info("STOCKBOT SCHEDULER STARTING")
    log.info("Server time: %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"))
    log.info("IST time:    %s", _now_ist().strftime("%Y-%m-%d %H:%M:%S IST"))
    log.info("Mode:        %s", os.getenv("TRADING_MODE", "paper"))
    log.info("Capital:     ₹%s", os.getenv("TRADING_CAPITAL", "10000"))
    log.info("=" * 50)

    alert_fn = _get_alert()
    if alert_fn:
        alert_fn(
            "🤖 <b>StockBot Scheduler Started!</b>\n\n"
            f"🕐 Server time: {datetime.now().strftime('%H:%M %Z')}\n"
            f"🇮🇳 IST time: {_now_ist().strftime('%H:%M')}\n"
            f"💰 Mode: {os.getenv('TRADING_MODE', 'paper')}\n"
            f"💵 Capital: ₹{os.getenv('TRADING_CAPITAL', '10000')}\n\n"
            "Daily schedule (IST):\n"
            "• 9:00 AM — Pre-market preview\n"
            "• 9:30 AM — Main trading session\n"
            "• 4:00 PM — End of day report"
        )

    # Convert IST times to server local time for scheduling
    # Railway servers may be in different timezone, so we calculate offset
    server_now = datetime.now()
    ist_now = _now_ist().replace(tzinfo=None)
    offset_hours = (ist_now - server_now).total_seconds() / 3600

    def ist_to_local(ist_hour: int, ist_minute: int) -> str:
        """Convert IST HH:MM to server local time string."""
        ist_mins = ist_hour * 60 + ist_minute
        local_mins = ist_mins - int(offset_hours * 60)
        local_mins = local_mins % (24 * 60)
        h, m = divmod(local_mins, 60)
        return f"{h:02d}:{m:02d}"

    t_pre = ist_to_local(9, 0)
    t_scan = ist_to_local(9, 30)
    t_eod = ist_to_local(16, 0)

    log.info("Scheduled (local): pre-market=%s, scan=%s, eod=%s", t_pre, t_scan, t_eod)

    schedule.every().day.at(t_pre).do(pre_market_scan_job)
    schedule.every().day.at(t_scan).do(morning_scan_job)
    schedule.every().day.at(t_eod).do(evening_report_job)
    schedule.every().hour.do(heartbeat_job)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
