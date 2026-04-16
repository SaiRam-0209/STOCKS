"""V3 features — external data signals not derivable from OHLCV alone.

Seven features requiring live data fetches or cross-stock computation:
    1. vix_level          — India VIX (market fear gauge)
    2. dii_flow_score     — DII net buy/sell proxy
    3. delivery_pct       — NSE delivery % (conviction signal)
    4. oi_change_pct      — F&O OI change (smart money positioning)
    5. pcr_oi             — Put/Call ratio from F&O OI
    6. block_deal_flag    — 0/1 bulk/block deal activity
    7. peer_co_movement   — Avg same-sector peer return today

All values can be pre-fetched and passed in (batch training) or
auto-fetched (live scan). Every fetch has a silent fallback.
"""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


V3_FEATURE_COLUMNS = [
    "vix_level",
    "dii_flow_score",
    "delivery_pct",
    "oi_change_pct",
    "pcr_oi",
    "block_deal_flag",
    "peer_co_movement",
]


def build_v3_features(
    symbol: str,
    trade_date: date | None,
    daily_df: pd.DataFrame,
    day_idx: int,
    *,
    vix_level: float | None = None,
    dii_flow_score: float | None = None,
    delivery_pct: float | None = None,
    oi_change_pct: float | None = None,
    pcr_oi: float | None = None,
    block_deal_flag: int | None = None,
    peer_co_movement: float | None = None,
) -> dict:
    """Compute V3 features for a single day.

    Any kwarg that is None will be auto-fetched (with fallback).
    Pass pre-fetched values for batch efficiency.
    """
    if trade_date is None:
        try:
            td = daily_df.index[day_idx]
            trade_date = td.date() if hasattr(td, "date") else td
        except Exception:
            trade_date = date.today()

    sym_clean = symbol.replace(".NS", "").strip()

    if vix_level is None:
        vix_level = _safe_vix()

    if dii_flow_score is None:
        dii_flow_score = _safe_dii()

    if delivery_pct is None:
        delivery_pct = _safe_delivery(sym_clean, trade_date)

    if oi_change_pct is None:
        oi_change_pct = _safe_oi_change(sym_clean, trade_date)

    if pcr_oi is None:
        pcr_oi = _safe_pcr(trade_date)

    if block_deal_flag is None:
        block_deal_flag = _safe_block(sym_clean, trade_date)

    if peer_co_movement is None:
        peer_co_movement = _calc_peer_co_movement(symbol, daily_df, day_idx)

    return {
        "vix_level": round(float(vix_level), 2),
        "dii_flow_score": round(float(dii_flow_score), 4),
        "delivery_pct": round(float(delivery_pct), 2),
        "oi_change_pct": round(float(oi_change_pct), 4),
        "pcr_oi": round(float(pcr_oi), 4),
        "block_deal_flag": int(block_deal_flag),
        "peer_co_movement": round(float(peer_co_movement), 4),
    }


def _defaults() -> dict:
    return {
        "vix_level": 15.0,
        "dii_flow_score": 0.0,
        "delivery_pct": 50.0,
        "oi_change_pct": 0.0,
        "pcr_oi": 1.0,
        "block_deal_flag": 0,
        "peer_co_movement": 0.0,
    }


# ── Safe fetchers (never raise) ─────────────────────────────────────────

def _safe_vix() -> float:
    try:
        from project.data.fii_dii import fetch_vix_level
        return fetch_vix_level()
    except Exception as exc:
        log.warning("V3 vix_level fallback: %s", exc)
        return 15.0


def _safe_dii() -> float:
    try:
        from project.data.fii_dii import fetch_dii_flow_score
        return fetch_dii_flow_score()
    except Exception as exc:
        log.warning("V3 dii_flow_score fallback: %s", exc)
        return 0.0


def _safe_delivery(sym: str, d: date) -> float:
    try:
        from project.data.nse_bhavcopy import get_delivery_pct
        return get_delivery_pct(sym, d)
    except Exception as exc:
        log.warning("V3 delivery_pct fallback for %s: %s", sym, exc)
        return 50.0


def _safe_oi_change(sym: str, d: date) -> float:
    try:
        from project.data.nse_bhavcopy import get_oi_change_pct
        return get_oi_change_pct(sym, d)
    except Exception as exc:
        log.warning("V3 oi_change_pct fallback for %s: %s", sym, exc)
        return 0.0


def _safe_pcr(d: date) -> float:
    try:
        from project.data.nse_bhavcopy import get_pcr_oi
        return get_pcr_oi(d)
    except Exception as exc:
        log.warning("V3 pcr_oi fallback: %s", exc)
        return 1.0


def _safe_block(sym: str, d: date) -> int:
    try:
        from project.data.nse_bhavcopy import get_block_deal_flag
        return get_block_deal_flag(sym, d)
    except Exception as exc:
        log.warning("V3 block_deal_flag fallback for %s: %s", sym, exc)
        return 0


def _calc_peer_co_movement(
    symbol: str,
    daily_df: pd.DataFrame,
    day_idx: int,
) -> float:
    """Avg same-day return of up-to-5 sector peers.

    Uses daily_df's date to look up peer data via yfinance.
    In training mode (historical), this is expensive but only runs once.
    """
    try:
        from project.data.sectors import get_sector, get_sector_stocks

        sector = get_sector(symbol)
        if not sector:
            return 0.0

        peers = get_sector_stocks(sector)
        sym_ns = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        peers = [p for p in peers if p != sym_ns][:5]

        if not peers or day_idx < 1:
            return 0.0

        trade_date = daily_df.index[day_idx]
        prev_date = daily_df.index[day_idx - 1]

        peer_returns: list[float] = []
        import yfinance as yf

        for peer in peers:
            try:
                pdf = yf.download(peer, start=prev_date, end=trade_date + pd.Timedelta(days=1),
                                  interval="1d", progress=False)
                if hasattr(pdf.columns, "levels"):
                    pdf.columns = pdf.columns.droplevel(1)
                if pdf is None or len(pdf) < 2:
                    continue
                pc = float(pdf["Close"].iloc[-2])
                tc = float(pdf["Close"].iloc[-1])
                if pc > 0:
                    peer_returns.append((tc - pc) / pc * 100)
            except Exception:
                continue

        if not peer_returns:
            return 0.0
        return round(float(np.mean(peer_returns)), 4)

    except Exception as exc:
        log.warning("V3 peer_co_movement fallback: %s", exc)
        return 0.0
