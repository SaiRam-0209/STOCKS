"""Angel One SmartAPI broker connection.

Handles authentication, session management, and raw API calls.
Credentials are loaded from environment variables — never hardcoded.

Required env vars:
    ANGEL_API_KEY      — from SmartAPI developer portal
    ANGEL_CLIENT_ID    — your Angel One client/user ID
    ANGEL_PASSWORD     — your trading password
    ANGEL_TOTP_SECRET  — base32 secret from authenticator setup
"""

import os
import logging
from dataclasses import dataclass
from SmartApi import SmartConnect
import pyotp

log = logging.getLogger(__name__)


@dataclass
class BrokerConfig:
    api_key: str
    client_id: str
    password: str
    totp_secret: str

    @classmethod
    def from_env(cls) -> "BrokerConfig":
        """Load credentials from environment variables."""
        api_key = os.getenv("ANGEL_API_KEY", "")
        client_id = os.getenv("ANGEL_CLIENT_ID", "")
        password = os.getenv("ANGEL_PASSWORD", "")
        totp_secret = os.getenv("ANGEL_TOTP_SECRET", "")

        missing = []
        if not api_key:
            missing.append("ANGEL_API_KEY")
        if not client_id:
            missing.append("ANGEL_CLIENT_ID")
        if not password:
            missing.append("ANGEL_PASSWORD")
        if not totp_secret:
            missing.append("ANGEL_TOTP_SECRET")

        if missing:
            raise EnvironmentError(
                f"Missing broker credentials: {', '.join(missing)}. "
                "Set them as environment variables or in a .env file."
            )
        return cls(api_key, client_id, password, totp_secret)


class AngelBroker:
    """Wrapper around Angel One SmartAPI for session + order management."""

    def __init__(self, config: BrokerConfig | None = None):
        self.config = config or BrokerConfig.from_env()
        self.smart = SmartConnect(api_key=self.config.api_key)
        self._session_token: str | None = None
        self._feed_token: str | None = None
        self._is_logged_in = False

    # ── Authentication ────────────────────────────────────────────────────

    def login(self) -> bool:
        """Authenticate with Angel One using TOTP. Call once per trading day."""
        try:
            totp = pyotp.TOTP(self.config.totp_secret).now()
            data = self.smart.generateSession(
                self.config.client_id,
                self.config.password,
                totp,
            )
            if not data or data.get("status") is False:
                log.error("Login failed: %s", data)
                return False

            self._session_token = data["data"]["jwtToken"]
            self._feed_token = self.smart.getfeedToken()
            self._is_logged_in = True
            log.info("Logged in to Angel One as %s", self.config.client_id)
            return True

        except Exception as exc:
            log.exception("Login error: %s", exc)
            self._is_logged_in = False
            return False

    def logout(self):
        """End the session."""
        try:
            self.smart.terminateSession(self.config.client_id)
        except Exception:
            pass
        self._is_logged_in = False
        log.info("Logged out of Angel One")

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in

    # ── Account Info ──────────────────────────────────────────────────────

    def get_profile(self) -> dict:
        """Fetch user profile (name, email, broker ID, etc.)."""
        self._require_login()
        resp = self.smart.getProfile(self.smart.refresh_token)
        return resp.get("data", {}) if resp else {}

    def get_funds(self) -> dict:
        """Fetch available funds/margins."""
        self._require_login()
        resp = self.smart.rmsLimit()
        return resp.get("data", {}) if resp else {}

    def get_available_cash(self) -> float:
        """Return available cash for trading."""
        funds = self.get_funds()
        try:
            return float(funds.get("availablecash", 0))
        except (TypeError, ValueError):
            return 0.0

    # ── Market Data ───────────────────────────────────────────────────────

    def get_ltp(self, ticker: str, exchange: str = "NSE") -> float | None:
        """Get last traded price for a ticker (auto-resolves symbol token)."""
        self._require_login()
        token, trading_sym = self._resolve_symbol(ticker)
        if not token:
            log.error("Cannot resolve symbol token for %s", ticker)
            return None
        try:
            resp = self.smart.ltpData(exchange, trading_sym, token)
            if resp and resp.get("data"):
                return float(resp["data"]["ltp"])
        except Exception as exc:
            log.error("LTP fetch failed for %s: %s", ticker, exc)
        return None

    def get_candle_data(
        self,
        ticker: str,
        exchange: str = "NSE",
        interval: str = "FIFTEEN_MINUTE",
        from_date: str = "",
        to_date: str = "",
    ) -> list[dict]:
        """Fetch historical/intraday candle data (auto-resolves symbol token)."""
        self._require_login()
        token, _ = self._resolve_symbol(ticker)
        if not token:
            log.error("Cannot resolve symbol token for %s", ticker)
            return []
        try:
            params = {
                "exchange": exchange,
                "symboltoken": token,
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date,
            }
            resp = self.smart.getCandleData(params)
            if resp and resp.get("data"):
                return resp["data"]
        except Exception as exc:
            log.error("Candle data fetch failed: %s", exc)
        return []

    def _resolve_symbol(self, ticker: str) -> tuple[str | None, str | None]:
        """Resolve a ticker name to (token, trading_symbol) using SymbolMapper."""
        if not hasattr(self, "_symbol_mapper"):
            from project.broker.symbols import SymbolMapper
            self._symbol_mapper = SymbolMapper()
        token = self._symbol_mapper.get_token(ticker)
        trading_sym = self._symbol_mapper.get_trading_symbol(ticker)
        return token, trading_sym

    # ── Order Placement ───────────────────────────────────────────────────

    def place_order(self, order_params: dict) -> str | None:
        """Place an order. Returns order ID or None on failure.

        order_params should include:
            variety, tradingsymbol, symboltoken, transactiontype,
            exchange, ordertype, producttype, duration, price,
            quantity, triggerprice, squareoff, stoploss
        """
        self._require_login()
        try:
            resp = self.smart.placeOrder(order_params)
            if resp:
                log.info("Order placed: %s → %s", order_params.get("tradingsymbol"), resp)
                return str(resp)
            log.error("Order failed: %s", order_params)
        except Exception as exc:
            log.exception("Order error: %s", exc)
        return None

    def cancel_order(self, order_id: str, variety: str = "NORMAL") -> bool:
        """Cancel a pending order."""
        self._require_login()
        try:
            resp = self.smart.cancelOrder(order_id, variety)
            log.info("Order %s cancelled: %s", order_id, resp)
            return True
        except Exception as exc:
            log.error("Cancel failed for %s: %s", order_id, exc)
            return False

    def get_order_book(self) -> list[dict]:
        """Fetch all orders for today."""
        self._require_login()
        resp = self.smart.orderBook()
        return resp.get("data", []) if resp and resp.get("data") else []

    def get_positions(self) -> list[dict]:
        """Fetch current open positions."""
        self._require_login()
        resp = self.smart.position()
        return resp.get("data", []) if resp and resp.get("data") else []

    def get_holdings(self) -> list[dict]:
        """Fetch portfolio holdings."""
        self._require_login()
        resp = self.smart.holding()
        return resp.get("data", []) if resp and resp.get("data") else []

    # ── Internal ──────────────────────────────────────────────────────────

    def _require_login(self):
        if not self._is_logged_in:
            raise RuntimeError(
                "Not logged in to Angel One. Call broker.login() first."
            )
