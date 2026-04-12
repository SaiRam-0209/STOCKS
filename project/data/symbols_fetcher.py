"""Dynamic NSE stock symbol fetcher with local caching.

Fetches all NSE equity stocks + F&O list from NSE endpoints.
Caches results locally to avoid repeated API calls.
"""

import csv
import io
import json
import os
import requests
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache")
EQUITY_CACHE = os.path.join(CACHE_DIR, "nse_equities.json")
FNO_CACHE = os.path.join(CACHE_DIR, "nse_fno.json")
CACHE_MAX_AGE_DAYS = 7  # Refresh weekly

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json,*/*",
}


def _cache_is_fresh(path: str) -> bool:
    """Check if a cache file exists and is less than CACHE_MAX_AGE_DAYS old."""
    if not os.path.exists(path):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - mtime < timedelta(days=CACHE_MAX_AGE_DAYS)


def _save_cache(path: str, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)


def _load_cache(path: str):
    with open(path) as f:
        return json.load(f)


def fetch_all_nse_symbols() -> list[str]:
    """Fetch all NSE equity (EQ series) stock symbols.

    Returns symbols WITHOUT the '.NS' suffix.
    Uses local cache if fresh, otherwise fetches from NSE.
    """
    if _cache_is_fresh(EQUITY_CACHE):
        return _load_cache(EQUITY_CACHE)

    try:
        r = requests.get(
            "https://archives.nseindia.com/content/equities/EQUITY_L.csv",
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()

        reader = csv.DictReader(io.StringIO(r.text))
        symbols = []
        for row in reader:
            series = row.get(" SERIES", "").strip()
            symbol = row.get("SYMBOL", "").strip()
            if series == "EQ" and symbol:
                symbols.append(symbol)

        if symbols:
            _save_cache(EQUITY_CACHE, symbols)
            print(f"  Fetched {len(symbols)} NSE equity symbols from NSE")
            return symbols
    except Exception as e:
        print(f"  [WARN] Failed to fetch NSE equity list: {e}")

    # Fallback to cache even if stale
    if os.path.exists(EQUITY_CACHE):
        print("  Using stale cache for equity symbols")
        return _load_cache(EQUITY_CACHE)

    return []


def fetch_fno_symbols() -> list[str]:
    """Fetch all F&O-eligible stock symbols from NSE.

    Returns symbols WITHOUT the '.NS' suffix.
    """
    if _cache_is_fresh(FNO_CACHE):
        return _load_cache(FNO_CACHE)

    try:
        session = requests.Session()
        session.headers.update(_HEADERS)
        # Hit main page first for cookies
        session.get("https://www.nseindia.com", timeout=10)
        r = session.get(
            "https://www.nseindia.com/api/master-quote",
            params={"segment": "fo-stock"},
            timeout=10,
        )
        r.raise_for_status()
        symbols = r.json()

        if isinstance(symbols, list) and symbols:
            _save_cache(FNO_CACHE, symbols)
            print(f"  Fetched {len(symbols)} F&O symbols from NSE")
            return symbols
    except Exception as e:
        print(f"  [WARN] Failed to fetch F&O list: {e}")

    if os.path.exists(FNO_CACHE):
        print("  Using stale cache for F&O symbols")
        return _load_cache(FNO_CACHE)

    return []


def get_all_nse_stocks() -> list[str]:
    """Get all NSE equity symbols with '.NS' suffix (for yfinance).

    Returns deduplicated, sorted list.
    """
    raw = fetch_all_nse_symbols()
    return sorted(set(f"{s}.NS" for s in raw))


def get_fno_stocks() -> set[str]:
    """Get F&O-eligible symbols as a set with '.NS' suffix."""
    raw = fetch_fno_symbols()
    return set(f"{s}.NS" for s in raw)


def classify_intraday_eligibility(
    symbols: list[str],
    fno_set: set[str] | None = None,
) -> dict[str, str]:
    """Classify stocks into intraday eligibility tiers.

    Returns:
        Dict mapping symbol -> tier:
          "FNO_INTRADAY"  : F&O stock, always intraday eligible
          "NON_FNO"       : Not in F&O, needs volume check at prediction time
    """
    if fno_set is None:
        fno_set = get_fno_stocks()

    result = {}
    for symbol in symbols:
        if symbol in fno_set:
            result[symbol] = "FNO_INTRADAY"
        else:
            result[symbol] = "NON_FNO"
    return result
