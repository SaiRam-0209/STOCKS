"""Telegram bot alerts for trade notifications.

Setup:
    1. Message @BotFather on Telegram → /newbot → get BOT_TOKEN
    2. Message your bot, then visit:
       https://api.telegram.org/bot<TOKEN>/getUpdates
       to find your CHAT_ID
    3. Set env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

Usage:
    from project.alerts.telegram import TelegramAlert
    alert = TelegramAlert()
    alert.send("TATASTEEL gapped +5.2% — BUY signal!")
"""

import os
import logging
import requests

log = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


class TelegramAlert:
    """Send trade alerts via Telegram bot."""

    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._enabled = bool(self.bot_token and self.chat_id)

        if not self._enabled:
            log.warning(
                "Telegram alerts disabled — set TELEGRAM_BOT_TOKEN and "
                "TELEGRAM_CHAT_ID environment variables"
            )

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured Telegram chat.

        Args:
            message: Text message (supports HTML formatting)
            parse_mode: "HTML" or "Markdown"

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._enabled:
            log.debug("Telegram disabled, skipping: %s", message[:80])
            return False

        try:
            url = TELEGRAM_API.format(token=self.bot_token)
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            log.error("Telegram API error %d: %s", resp.status_code, resp.text)
            return False

        except Exception as exc:
            log.error("Telegram send failed: %s", exc)
            return False

    def send_trade_entry(
        self, ticker: str, direction: str, qty: int,
        entry: float, stoploss: float, target: float,
        gap_pct: float, rel_vol: float, mode: str = "PAPER",
    ):
        """Send formatted trade entry alert."""
        emoji = "🟢" if direction == "LONG" else "🔴"
        msg = (
            f"{emoji} <b>{mode} {direction}</b>\n"
            f"<b>{ticker}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Qty:    {qty}\n"
            f"Entry:  ₹{entry:.2f}\n"
            f"SL:     ₹{stoploss:.2f}\n"
            f"Target: ₹{target:.2f}\n"
            f"Gap:    {gap_pct:+.1f}%\n"
            f"Volume: {rel_vol:.1f}x avg\n"
            f"━━━━━━━━━━━━━━━"
        )
        self.send(msg)

    def send_trade_exit(
        self, ticker: str, direction: str, result: str,
        entry: float, exit_price: float, pnl: float, mode: str = "PAPER",
    ):
        """Send formatted trade exit alert."""
        emoji = "✅" if result == "WIN" else "❌"
        msg = (
            f"{emoji} <b>{mode} {result}</b>\n"
            f"<b>{ticker}</b> ({direction})\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Entry: ₹{entry:.2f}\n"
            f"Exit:  ₹{exit_price:.2f}\n"
            f"P&L:   ₹{pnl:+.2f}\n"
            f"━━━━━━━━━━━━━━━"
        )
        self.send(msg)

    def send_daily_report(
        self, date: str, wins: int, losses: int,
        total_pnl: float, capital: float, mode: str = "PAPER",
    ):
        """Send end-of-day summary."""
        total = wins + losses
        wr = (wins / total * 100) if total > 0 else 0
        emoji = "📈" if total_pnl >= 0 else "📉"

        msg = (
            f"{emoji} <b>DAILY REPORT — {date}</b>\n"
            f"Mode: {mode}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Trades:   {total}\n"
            f"Wins:     {wins}\n"
            f"Losses:   {losses}\n"
            f"Win Rate: {wr:.0f}%\n"
            f"P&L:      ₹{total_pnl:+.2f}\n"
            f"Capital:  ₹{capital:,.0f}\n"
            f"━━━━━━━━━━━━━━━"
        )
        self.send(msg)
