"""FII/DII flow data — institutional buying/selling activity.

Foreign Institutional Investors (FII) and Domestic Institutional Investors (DII)
drive the majority of market movements. Their net buy/sell figures are published
daily by NSE/BSE.

We use yfinance proxy data (Nifty + ETF flows) when direct NSE data isn't available.
"""

import logging
from datetime import date, timedelta

import yfinance as yf
import pandas as pd

log = logging.getLogger(__name__)


def fetch_institutional_flow(days: int = 10) -> dict:
    """Estimate institutional flow direction using market proxies.

    Uses:
        - Nifty 50 trend (5-day) as FII sentiment proxy
        - India VIX level as fear/confidence gauge
        - USD/INR trend (FII flows correlate with rupee strength)

    Returns:
        dict with flow_score (-1 to +1), fii_sentiment, dii_sentiment
    """
    try:
        # Nifty 50 trend
        nifty = yf.Ticker("^NSEI")
        nifty_hist = nifty.history(period=f"{days}d")
        if nifty_hist.empty or len(nifty_hist) < 5:
            return _default_flow()

        nifty_returns_5d = (
            (nifty_hist["Close"].iloc[-1] - nifty_hist["Close"].iloc[-5])
            / nifty_hist["Close"].iloc[-5] * 100
        )

        # VIX level
        vix = yf.Ticker("^INDIAVIX")
        vix_hist = vix.history(period="5d")
        vix_level = float(vix_hist["Close"].iloc[-1]) if not vix_hist.empty else 15.0

        # USD/INR (falling rupee = FII selling, rising rupee = FII buying)
        usdinr = yf.Ticker("INR=X")
        usdinr_hist = usdinr.history(period=f"{days}d")
        if not usdinr_hist.empty and len(usdinr_hist) >= 5:
            rupee_change = (
                (usdinr_hist["Close"].iloc[-1] - usdinr_hist["Close"].iloc[-5])
                / usdinr_hist["Close"].iloc[-5] * 100
            )
        else:
            rupee_change = 0.0

        # Compute flow score
        flow_score = 0.0

        # Nifty trend: up = FII buying likely
        if nifty_returns_5d > 2:
            flow_score += 0.4
        elif nifty_returns_5d > 0.5:
            flow_score += 0.2
        elif nifty_returns_5d < -2:
            flow_score -= 0.4
        elif nifty_returns_5d < -0.5:
            flow_score -= 0.2

        # VIX: low = confident, high = fearful
        if vix_level < 14:
            flow_score += 0.3
        elif vix_level < 18:
            flow_score += 0.1
        elif vix_level > 25:
            flow_score -= 0.3
        elif vix_level > 20:
            flow_score -= 0.1

        # Rupee: strengthening (falling USDINR) = FII inflow
        if rupee_change < -0.5:
            flow_score += 0.3  # Rupee strengthening
        elif rupee_change > 0.5:
            flow_score -= 0.3  # Rupee weakening

        flow_score = max(-1.0, min(1.0, flow_score))

        fii_sentiment = "BUYING" if flow_score > 0.2 else ("SELLING" if flow_score < -0.2 else "NEUTRAL")
        dii_sentiment = "BUYING" if flow_score < -0.1 else ("SELLING" if flow_score > 0.3 else "NEUTRAL")

        return {
            "flow_score": round(flow_score, 3),
            "fii_sentiment": fii_sentiment,
            "dii_sentiment": dii_sentiment,
            "nifty_5d_return": round(nifty_returns_5d, 2),
            "vix_level": round(vix_level, 2),
            "rupee_change_5d": round(rupee_change, 2),
        }

    except Exception as exc:
        log.error("Failed to fetch institutional flow: %s", exc)
        return _default_flow()


def _default_flow() -> dict:
    return {
        "flow_score": 0.0,
        "fii_sentiment": "NEUTRAL",
        "dii_sentiment": "NEUTRAL",
        "nifty_5d_return": 0.0,
        "vix_level": 15.0,
        "rupee_change_5d": 0.0,
    }


def fetch_vix_level() -> float:
    """Current India VIX close. Fallback: 15.0 (long-run median)."""
    try:
        vix = yf.Ticker("^INDIAVIX")
        hist = vix.history(period="5d")
        if hist.empty:
            return 15.0
        return round(float(hist["Close"].iloc[-1]), 2)
    except Exception as exc:
        log.warning("VIX fetch failed: %s", exc)
        return 15.0


def fetch_dii_flow_score() -> float:
    """DII-component of the institutional flow score, in [-1, 1].

    Positive = DII net buying (domestic support), negative = DII selling.
    Uses the inverse of FII flow as a DII proxy — when FII sells, DII
    typically absorbs, and vice versa.
    """
    try:
        flow = fetch_institutional_flow()
        fii_score = flow["flow_score"]
        return round(-fii_score * 0.8, 4)
    except Exception as exc:
        log.warning("DII flow score failed: %s", exc)
        return 0.0
