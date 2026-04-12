"""Fetch global macro data that impacts Indian stock market."""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


# Global tickers to track
GLOBAL_TICKERS = {
    # US Markets
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    # Asian Markets
    "nikkei": "^N225",
    "hangseng": "^HSI",
    "shanghai": "000001.SS",
    # European
    "ftse": "^FTSE",
    "dax": "^GDAXI",
    # India
    "nifty50": "^NSEI",
    "sensex": "^BSESN",
    "india_vix": "^INDIAVIX",
    "nifty_smallcap": "^NSMIDCP",
    # Commodities
    "crude_oil": "CL=F",
    "gold": "GC=F",
    "silver": "SI=F",
    "natural_gas": "NG=F",
    "copper": "HG=F",
    # Currency
    "usd_inr": "INR=X",
    # Bonds
    "us_10y": "^TNX",
    "india_10y": "^IRX",
    # Volatility
    "vix_us": "^VIX",
}


def fetch_global_snapshot() -> dict:
    """Fetch current prices and daily changes for all global indicators.

    Returns:
        Dict with indicator name → {price, change_pct, prev_close, signal}
    """
    snapshot = {}
    tickers_str = " ".join(GLOBAL_TICKERS.values())

    try:
        data = yf.download(tickers_str, period="5d", interval="1d",
                           group_by="ticker", progress=False)
    except Exception as e:
        print(f"[WARN] Bulk download failed: {e}")
        return snapshot

    for name, ticker in GLOBAL_TICKERS.items():
        try:
            if len(GLOBAL_TICKERS) == 1:
                df = data
            else:
                df = data[ticker] if ticker in data.columns.get_level_values(0) else None

            if df is None or df.empty:
                continue

            df = df.dropna(subset=["Close"])
            if len(df) < 2:
                continue

            current = float(df["Close"].iloc[-1])
            prev = float(df["Close"].iloc[-2])
            change_pct = ((current - prev) / prev) * 100

            # Signal interpretation
            if abs(change_pct) < 0.3:
                signal = "FLAT"
            elif change_pct > 0:
                signal = "UP" if change_pct < 1.5 else "STRONG_UP"
            else:
                signal = "DOWN" if change_pct > -1.5 else "STRONG_DOWN"

            snapshot[name] = {
                "price": round(current, 2),
                "prev_close": round(prev, 2),
                "change_pct": round(change_pct, 2),
                "signal": signal,
            }
        except Exception:
            continue

    return snapshot


def compute_macro_score(snapshot: dict) -> dict:
    """Compute an overall macro environment score from global data.

    Score ranges from -10 (very bearish) to +10 (very bullish).
    Also returns per-factor scores for transparency.

    Returns:
        Dict with total_score, factors dict, and market_mood label.
    """
    factors = {}
    total = 0.0

    # --- US Markets (high weight — overnight sentiment) ---
    for market, weight in [("sp500", 2.0), ("nasdaq", 1.5), ("dow", 1.0)]:
        if market in snapshot:
            chg = snapshot[market]["change_pct"]
            score = max(-2, min(2, chg * weight * 0.5))
            factors[f"us_{market}"] = round(score, 2)
            total += score

    # --- Asian Markets (medium weight — same-day sentiment) ---
    for market in ["nikkei", "hangseng", "shanghai"]:
        if market in snapshot:
            chg = snapshot[market]["change_pct"]
            score = max(-1, min(1, chg * 0.3))
            factors[f"asia_{market}"] = round(score, 2)
            total += score

    # --- India VIX (inverse — high VIX = bearish for smallcaps) ---
    if "india_vix" in snapshot:
        vix_price = snapshot["india_vix"]["price"]
        if vix_price > 20:
            score = -2.0
        elif vix_price > 15:
            score = -0.5
        elif vix_price < 12:
            score = 1.5
        else:
            score = 0.5
        factors["india_vix"] = round(score, 2)
        total += score

    # --- Crude Oil (inverse for India — importer) ---
    if "crude_oil" in snapshot:
        chg = snapshot["crude_oil"]["change_pct"]
        score = max(-1.5, min(1.5, -chg * 0.3))  # Inverse
        factors["crude_oil"] = round(score, 2)
        total += score

    # --- Gold (safe haven — up means risk-off) ---
    if "gold" in snapshot:
        chg = snapshot["gold"]["change_pct"]
        score = max(-1, min(1, -chg * 0.2))  # Inverse
        factors["gold"] = round(score, 2)
        total += score

    # --- USD/INR (rupee weakening = negative) ---
    if "usd_inr" in snapshot:
        chg = snapshot["usd_inr"]["change_pct"]
        score = max(-1, min(1, -chg * 0.5))  # Inverse: USD up = bad
        factors["usd_inr"] = round(score, 2)
        total += score

    # --- US VIX (fear gauge — high = bearish) ---
    if "vix_us" in snapshot:
        vix_price = snapshot["vix_us"]["price"]
        if vix_price > 30:
            score = -2.0
        elif vix_price > 20:
            score = -1.0
        elif vix_price < 15:
            score = 1.0
        else:
            score = 0.0
        factors["vix_us"] = round(score, 2)
        total += score

    # --- Nifty Smallcap trend ---
    if "nifty_smallcap" in snapshot:
        chg = snapshot["nifty_smallcap"]["change_pct"]
        score = max(-1.5, min(1.5, chg * 0.5))
        factors["nifty_smallcap"] = round(score, 2)
        total += score

    total = round(max(-10, min(10, total)), 2)

    if total >= 4:
        mood = "VERY_BULLISH"
    elif total >= 1.5:
        mood = "BULLISH"
    elif total >= -1.5:
        mood = "NEUTRAL"
    elif total >= -4:
        mood = "BEARISH"
    else:
        mood = "VERY_BEARISH"

    return {
        "macro_score": total,
        "factors": factors,
        "market_mood": mood,
    }


def get_sector_rotation_signals(snapshot: dict) -> dict:
    """Determine which sectors benefit from current macro conditions.

    Returns:
        Dict of sector → score (+ve = favorable, -ve = unfavorable).
    """
    signals = {}

    crude_chg = snapshot.get("crude_oil", {}).get("change_pct", 0)
    gold_chg = snapshot.get("gold", {}).get("change_pct", 0)
    usd_chg = snapshot.get("usd_inr", {}).get("change_pct", 0)
    us_chg = snapshot.get("sp500", {}).get("change_pct", 0)
    nasdaq_chg = snapshot.get("nasdaq", {}).get("change_pct", 0)

    # IT/Tech: benefits from USD strength + Nasdaq up
    signals["technology"] = round(usd_chg * 0.5 + nasdaq_chg * 0.3, 2)

    # Pharma: benefits from USD strength (export revenue)
    signals["pharma"] = round(usd_chg * 0.4, 2)

    # Oil & Gas: benefits from crude up
    signals["oil_gas"] = round(crude_chg * 0.5, 2)

    # Auto: hurt by crude up (input cost)
    signals["auto"] = round(-crude_chg * 0.3 + us_chg * 0.2, 2)

    # Banking/Finance: benefits from stable macro
    signals["banking"] = round(us_chg * 0.2 - abs(crude_chg) * 0.1, 2)

    # Metals: benefits from global growth signals
    copper_chg = snapshot.get("copper", {}).get("change_pct", 0)
    signals["metals"] = round(copper_chg * 0.4 + us_chg * 0.2, 2)

    # Gold/Jewellery: benefits from gold price up
    signals["gold_jewellery"] = round(gold_chg * 0.5, 2)

    # Defence: relatively immune to macro, but budget/policy driven
    signals["defence"] = 0.0

    # Real Estate: hurt by rate hikes, helped by growth
    signals["real_estate"] = round(us_chg * 0.2 - crude_chg * 0.1, 2)

    # Chemicals/Fertiliser: mixed — input costs vs demand
    signals["chemicals"] = round(-crude_chg * 0.2 + us_chg * 0.1, 2)

    # Infrastructure: benefits from domestic growth
    signals["infrastructure"] = round(us_chg * 0.1, 2)

    return signals
