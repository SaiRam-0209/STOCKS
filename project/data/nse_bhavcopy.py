"""NSE bhavcopy data — delivery %, OI change, PCR, block deals.

Downloads daily CSVs from NSE archives and caches them locally.
Each date's CSV is fetched at most once (file-based 1-day cache).

All public functions return neutral defaults on any failure, never raise.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import zipfile
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)

_CACHE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "cache", "nse_bhavcopy"
)
_SESSION_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
_TIMEOUT = 15


def _ensure_cache_dir():
    os.makedirs(_CACHE_DIR, exist_ok=True)


def _cache_path(tag: str, d: date) -> str:
    return os.path.join(_CACHE_DIR, f"{d.isoformat()}_{tag}.csv")


def _download(url: str, cache_file: str) -> str | None:
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return f.read()
    try:
        resp = requests.get(url, headers=_SESSION_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        content = resp.text
        _ensure_cache_dir()
        with open(cache_file, "w") as f:
            f.write(content)
        return content
    except Exception as exc:
        log.warning("NSE download failed (%s): %s", url.split("/")[-1], exc)
        return None


def _download_zip(url: str, cache_file: str) -> str | None:
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            return f.read()
    try:
        resp = requests.get(url, headers=_SESSION_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            name = zf.namelist()[0]
            content = zf.read(name).decode("utf-8", errors="replace")
        _ensure_cache_dir()
        with open(cache_file, "w") as f:
            f.write(content)
        return content
    except Exception as exc:
        log.warning("NSE zip download failed (%s): %s", url.split("/")[-1], exc)
        return None


# ── Equity bhavcopy (delivery data) ──────────────────────────────────────

def _eq_bhavcopy_url(d: date) -> str:
    return (
        f"https://archives.nseindia.com/products/content/sec_bhavdata_full_"
        f"{d.strftime('%d%m%Y')}.csv"
    )


_eq_cache: dict[date, dict[str, dict]] = {}


def _load_eq_bhavcopy(d: date) -> dict[str, dict]:
    if d in _eq_cache:
        return _eq_cache[d]

    cf = _cache_path("eq", d)
    content = _download(_eq_bhavcopy_url(d), cf)
    if content is None:
        return {}

    rows: dict[str, dict] = {}
    try:
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            sym = (row.get("SYMBOL") or row.get(" SYMBOL") or "").strip()
            if not sym:
                continue
            try:
                deliv = float((row.get("DELIV_PER") or row.get(" DELIV_PER") or "0").strip() or "0")
            except ValueError:
                deliv = 0.0
            rows[sym] = {"delivery_pct": deliv}
    except Exception as exc:
        log.warning("Eq bhavcopy parse error: %s", exc)
        return {}

    _eq_cache[d] = rows
    return rows


def get_delivery_pct(symbol: str, d: date | None = None) -> float:
    if d is None:
        d = date.today() - timedelta(days=1)
    sym = symbol.replace(".NS", "").strip()
    data = _load_eq_bhavcopy(d)
    if sym in data:
        return data[sym]["delivery_pct"]
    yesterday = d - timedelta(days=1)
    data2 = _load_eq_bhavcopy(yesterday)
    if sym in data2:
        return data2[sym]["delivery_pct"]
    return 50.0


# ── F&O bhavcopy (OI, PCR) ──────────────────────────────────────────────

def _fo_bhavcopy_url(d: date) -> str:
    month_upper = d.strftime("%b").upper()
    return (
        f"https://archives.nseindia.com/content/historical/DERIVATIVES/"
        f"{d.year}/{month_upper}/fo{d.strftime('%d%b%Y').upper()}bhav.csv.zip"
    )


_fo_cache: dict[date, list[dict]] = {}


def _load_fo_bhavcopy(d: date) -> list[dict]:
    if d in _fo_cache:
        return _fo_cache[d]

    cf = _cache_path("fo", d)
    content = _download_zip(_fo_bhavcopy_url(d), cf)
    if content is None:
        return []

    rows: list[dict] = []
    try:
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            rows.append(row)
    except Exception as exc:
        log.warning("FO bhavcopy parse error: %s", exc)
        return []

    _fo_cache[d] = rows
    return rows


def get_oi_change_pct(symbol: str, d: date | None = None) -> float:
    if d is None:
        d = date.today() - timedelta(days=1)
    sym = symbol.replace(".NS", "").strip()

    rows = _load_fo_bhavcopy(d)
    if not rows:
        return 0.0

    total_oi = 0
    total_chg = 0
    for row in rows:
        rsym = (row.get("SYMBOL") or "").strip()
        instr = (row.get("INSTRUMENT") or "").strip()
        if rsym != sym or instr not in ("FUTSTK", "FUTIDX"):
            continue
        try:
            oi = int((row.get("OPEN_INT") or "0").strip() or "0")
            chg = int((row.get("CHG_IN_OI") or "0").strip() or "0")
            total_oi += oi
            total_chg += chg
        except (ValueError, TypeError):
            continue

    if total_oi <= 0:
        return 0.0
    return round(total_chg / total_oi * 100, 4)


def get_pcr_oi(d: date | None = None) -> float:
    if d is None:
        d = date.today() - timedelta(days=1)

    rows = _load_fo_bhavcopy(d)
    if not rows:
        return 1.0

    put_oi = 0
    call_oi = 0
    for row in rows:
        instr = (row.get("INSTRUMENT") or "").strip()
        opt_type = (row.get("OPTION_TYP") or "").strip()
        if instr not in ("OPTSTK", "OPTIDX"):
            continue
        try:
            oi = int((row.get("OPEN_INT") or "0").strip() or "0")
        except (ValueError, TypeError):
            continue
        if opt_type == "PE":
            put_oi += oi
        elif opt_type == "CE":
            call_oi += oi

    if call_oi <= 0:
        return 1.0
    return round(put_oi / call_oi, 4)


# ── Bulk/Block deals ────────────────────────────────────────────────────

def _block_deal_url(d: date) -> str:
    return (
        f"https://archives.nseindia.com/content/equities/bulk_"
        f"{d.strftime('%d%m%Y')}.csv"
    )


_block_cache: dict[date, set[str]] = {}


def _load_block_deals(d: date) -> set[str]:
    if d in _block_cache:
        return _block_cache[d]

    cf = _cache_path("block", d)
    content = _download(_block_deal_url(d), cf)
    symbols: set[str] = set()
    if content is None:
        return symbols

    try:
        reader = csv.DictReader(io.StringIO(content))
        for row in reader:
            sym = (row.get("Symbol") or row.get("SYMBOL") or "").strip()
            if sym:
                symbols.add(sym)
    except Exception as exc:
        log.warning("Block deals parse error: %s", exc)

    _block_cache[d] = symbols
    return symbols


def get_block_deal_flag(symbol: str, d: date | None = None) -> int:
    if d is None:
        d = date.today() - timedelta(days=1)
    sym = symbol.replace(".NS", "").strip()
    deals = _load_block_deals(d)
    return 1 if sym in deals else 0
