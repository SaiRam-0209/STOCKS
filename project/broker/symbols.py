"""Angel One symbol token mapper.

Angel One API uses numeric 'symboltoken' values, not ticker names.
This module downloads the master instrument list and provides fast lookups.
"""

from __future__ import annotations

import os
import json
import logging
from datetime import datetime

import requests

log = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")
INSTRUMENT_CACHE = os.path.join(CACHE_DIR, "angel_instruments.json")
INSTRUMENT_URL = "https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json"


def _load_instruments(force_refresh: bool = False) -> list[dict]:
    """Download or load cached instrument master list."""
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Use cache if less than 12 hours old
    if not force_refresh and os.path.exists(INSTRUMENT_CACHE):
        age_hours = (datetime.now().timestamp() - os.path.getmtime(INSTRUMENT_CACHE)) / 3600
        if age_hours < 12:
            with open(INSTRUMENT_CACHE) as f:
                return json.load(f)

    log.info("Downloading Angel One instrument master...")
    try:
        resp = requests.get(INSTRUMENT_URL, timeout=30)
        resp.raise_for_status()
        instruments = resp.json()
        with open(INSTRUMENT_CACHE, "w") as f:
            json.dump(instruments, f)
        log.info("Cached %d instruments", len(instruments))
        return instruments
    except Exception as exc:
        log.error("Failed to download instruments: %s", exc)
        if os.path.exists(INSTRUMENT_CACHE):
            with open(INSTRUMENT_CACHE) as f:
                return json.load(f)
        return []


class SymbolMapper:
    """Maps NSE ticker names to Angel One symbol tokens."""

    def __init__(self):
        self._instruments = _load_instruments()
        self._nse_eq: dict[str, dict] = {}
        self._build_index()

    def _build_index(self):
        """Build a lookup dict: ticker → instrument info."""
        for inst in self._instruments:
            if inst.get("exch_seg") == "NSE" and inst.get("instrumenttype") == "":
                # NSE equity — symbol is like "RELIANCE-EQ"
                name = inst.get("name", "")
                symbol = inst.get("symbol", "")
                if name:
                    self._nse_eq[name] = {
                        "token": inst["token"],
                        "symbol": symbol,
                        "name": name,
                        "lot_size": int(inst.get("lotsize", 1)),
                        "tick_size": float(inst.get("tick_size", 0.05)),
                    }

    def get_token(self, ticker: str) -> str | None:
        """Get Angel One symbol token for an NSE ticker.

        Args:
            ticker: NSE ticker like "RELIANCE" or "RELIANCE.NS"

        Returns:
            Symbol token string or None if not found.
        """
        # Clean up ticker — remove .NS suffix if present
        clean = ticker.replace(".NS", "").replace(".BO", "").strip().upper()
        info = self._nse_eq.get(clean)
        return info["token"] if info else None

    def get_trading_symbol(self, ticker: str) -> str | None:
        """Get the full trading symbol (e.g., 'RELIANCE-EQ')."""
        clean = ticker.replace(".NS", "").replace(".BO", "").strip().upper()
        info = self._nse_eq.get(clean)
        return info["symbol"] if info else None

    def get_lot_size(self, ticker: str) -> int:
        """Get lot size for a ticker (1 for cash equity)."""
        clean = ticker.replace(".NS", "").replace(".BO", "").strip().upper()
        info = self._nse_eq.get(clean)
        return info["lot_size"] if info else 1

    def get_info(self, ticker: str) -> dict | None:
        """Get full instrument info for a ticker."""
        clean = ticker.replace(".NS", "").replace(".BO", "").strip().upper()
        return self._nse_eq.get(clean)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search for instruments by partial name match."""
        query = query.upper()
        results = []
        for name, info in self._nse_eq.items():
            if query in name:
                results.append(info)
                if len(results) >= limit:
                    break
        return results
