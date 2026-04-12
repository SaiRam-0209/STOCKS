"""Boom predictor: orchestrates news + macro + ML to rank stocks."""

import numpy as np
import pandas as pd
import os
import joblib
from datetime import date, timedelta
from dataclasses import dataclass

from project.data.fetcher import fetch_daily
from project.data.symbols import ALL_STOCKS, RANK_MAP
from project.data.symbols_fetcher import get_fno_stocks, classify_intraday_eligibility
from project.ml.model import MODEL_DIR
from project.news.fetcher import fetch_news, fetch_stock_news
from project.news.sentiment import aggregate_sentiment_for_stock, analyze_text
from project.macro.global_data import (
    fetch_global_snapshot, compute_macro_score, get_sector_rotation_signals,
)
from project.ml.features import build_ml_features_for_day, FEATURE_COLUMNS, build_training_data
from project.ml.model import BoomPredictor


# Map symbols to their sector for sector rotation signals
SYMBOL_SECTOR_MAP = {
    # Technology
    "KPITTECH.NS": "technology", "CYIENT.NS": "technology",
    "HAPPSTMNDS.NS": "technology", "MASTEK.NS": "technology",
    "ZENSARTECH.NS": "technology", "BSOFT.NS": "technology",
    "NEWGEN.NS": "technology", "SONATSOFTW.NS": "technology",
    "LATENTVIEW.NS": "technology", "RATEGAIN.NS": "technology",
    # Fintech
    "BSE.NS": "banking", "CDSL.NS": "banking",
    "ANGELONE.NS": "banking", "CAMS.NS": "banking",
    "KFINTECH.NS": "banking", "RBLBANK.NS": "banking",
    "EQUITASBNK.NS": "banking", "UJJIVANSFB.NS": "banking",
    "POONAWALLA.NS": "banking", "MANAPPURAM.NS": "banking",
    # Defence
    "BDL.NS": "defence", "MAZDOCK.NS": "defence",
    "COCHINSHIP.NS": "defence", "GRSE.NS": "defence",
    "DATAPATTNS.NS": "defence", "IDEAFORGE.NS": "defence",
    # Pharma
    "JBCHEPHARM.NS": "pharma", "GLAND.NS": "pharma",
    "SPARC.NS": "pharma", "CAPLIPOINT.NS": "pharma",
    "JUBLPHARMA.NS": "pharma", "WOCKPHARMA.NS": "pharma",
    "LALPATHLAB.NS": "pharma", "METROPOLIS.NS": "pharma",
    "SANOFI.NS": "pharma",
    # Infrastructure
    "NCC.NS": "infrastructure", "PNCINFRA.NS": "infrastructure",
    "KEC.NS": "infrastructure", "JSWINFRA.NS": "infrastructure",
    "IRCON.NS": "infrastructure", "RVNL.NS": "infrastructure",
    "RITES.NS": "infrastructure",
    # Auto
    "JAMNAAUTO.NS": "auto", "VARROC.NS": "auto",
    "CEATLTD.NS": "auto", "JKTYRE.NS": "auto",
    "FIEMIND.NS": "auto",
    # Chemicals
    "ATUL.NS": "chemicals", "ALKYLAMINE.NS": "chemicals",
    "BALAMINES.NS": "chemicals", "NOCIL.NS": "chemicals",
    "TATACHEM.NS": "chemicals", "CHEMPLASTS.NS": "chemicals",
    "DEEPAKFERT.NS": "chemicals",
    # Real Estate
    "BRIGADE.NS": "real_estate", "SOBHA.NS": "real_estate",
    "ANANTRAJ.NS": "real_estate", "HEMIPROP.NS": "real_estate",
    # Cement
    "JKCEMENT.NS": "chemicals", "SAGCEM.NS": "chemicals",
    "BIRLACORPN.NS": "chemicals", "NUVOCO.NS": "chemicals",
    # Power
    "HBLPOWER.NS": "metals", "JPPOWER.NS": "metals",
    "CESC.NS": "metals", "POWERINDIA.NS": "metals",
    # Railway
    "TITAGARH.NS": "infrastructure",
    # Oil
    "MRPL.NS": "oil_gas", "SPLPETRO.NS": "oil_gas",
    # Gold/Jewellery
    "KALYANKJIL.NS": "gold_jewellery", "SENCO.NS": "gold_jewellery",
    # Solar/Renewable
    "SUZLON.NS": "metals", "INOXWIND.NS": "metals", "SWSOLAR.NS": "metals",
    # EMS
    "KAYNES.NS": "technology", "SYRMA.NS": "technology",
    "AMBER.NS": "technology",
}


@dataclass
class BoomCandidate:
    symbol: str
    index_rank: int
    boom_probability: float
    sentiment_score: float
    sentiment_label: str
    macro_score: float
    market_mood: str
    sector_score: float
    technical_summary: dict
    top_headlines: list[dict]
    confidence: str  # HIGH, MEDIUM, LOW
    trade_type: str = "DELIVERY"  # FNO_INTRADAY, NON_FNO, DELIVERY


def _checkpoint_path(universe: str | None) -> str:
    """Get checkpoint file path for a given universe."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    label = (universe or "all_stocks").lower().replace(" ", "_")
    return os.path.join(MODEL_DIR, f"checkpoint_{label}.joblib")


def _save_checkpoint(path: str, done_symbols: list[str],
                     all_X: list, all_y: list,
                     total_days: int):
    """Save training checkpoint so we can resume if interrupted."""
    joblib.dump({
        "done_symbols": done_symbols,
        "all_X": all_X,
        "all_y": all_y,
        "total_days": total_days,
    }, path)


def _load_checkpoint(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


def train_model(symbols: list[str] | None = None,
                universe: str | None = None,
                progress_callback=None) -> tuple[BoomPredictor, dict]:
    """Train the boom prediction model on ALL available historical data.

    Supports resumable training — if interrupted, saves a checkpoint
    after every 25 stocks so the next run picks up where it left off.

    Args:
        symbols: Stocks to include in training data (ALL of them).
        universe: Universe name for model file naming.
        progress_callback: Optional callable(phase, progress, message) for UI updates.

    Returns:
        (trained model, training metrics)
    """
    if symbols is None:
        symbols = ALL_STOCKS

    def _update(phase, progress, message):
        if progress_callback:
            progress_callback(phase, progress, message)
        print(f"  {message}")

    ckpt_path = _checkpoint_path(universe)
    ckpt = _load_checkpoint(ckpt_path)

    # Resume from checkpoint if available
    if ckpt:
        done_set = set(ckpt["done_symbols"])
        all_X = ckpt["all_X"]
        all_y = ckpt["all_y"]
        total_days = ckpt["total_days"]
        stocks_processed = len(done_set)
        _update("fetch", 0.0,
                f"Resuming from checkpoint: {stocks_processed} stocks already done. "
                f"Continuing with remaining...")
    else:
        done_set = set()
        all_X = []
        all_y = []
        total_days = 0
        stocks_processed = 0
        _update("fetch", 0.0,
                f"Fetching data for {len(symbols)} stocks (full history)...")

    # Track newly done symbols (for checkpoint saving)
    done_symbols = list(done_set)
    new_since_ckpt = 0

    for i, symbol in enumerate(symbols):
        if symbol in done_set:
            continue  # Already processed in a previous run

        try:
            daily_df = fetch_daily(symbol, max_data=True)
            if daily_df is None or len(daily_df) < 50:
                done_symbols.append(symbol)
                done_set.add(symbol)
                continue

            total_days += len(daily_df)
            X, y = build_training_data(daily_df)
            if len(X) > 0:
                all_X.append(X)
                all_y.append(y)
                stocks_processed += 1
        except Exception:
            pass

        done_symbols.append(symbol)
        done_set.add(symbol)
        new_since_ckpt += 1

        # Save checkpoint every 25 stocks
        if new_since_ckpt % 25 == 0:
            _save_checkpoint(ckpt_path, done_symbols, all_X, all_y,
                             total_days)

        pct = len(done_set) / len(symbols)
        _update("fetch", pct * 0.70,
                f"[{len(done_set)}/{len(symbols)}] {symbol} — "
                f"{len(daily_df) if 'daily_df' in dir() and daily_df is not None else 0} days | "
                f"{stocks_processed} stocks done | {total_days:,} candles")

    if not all_X:
        # Clean up checkpoint
        if os.path.exists(ckpt_path):
            os.remove(ckpt_path)
        return BoomPredictor(), {"error": "No data"}

    X_combined = np.vstack(all_X)
    y_combined = np.concatenate(all_y)

    _update("train", 0.72,
            f"Data ready: {len(X_combined):,} samples "
            f"({int(y_combined.sum()):,} positive). Training XGBoost + MLP...")

    model = BoomPredictor()
    metrics = model.train(X_combined, y_combined)
    metrics["total_daily_candles"] = total_days
    metrics["stocks_used"] = stocks_processed

    _update("save", 0.96, "Saving model...")
    model.save(universe=universe)

    # Clean up checkpoint — training complete
    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)

    _update("save", 1.0,
            f"Done! {len(X_combined):,} samples from {stocks_processed} stocks.")

    return model, metrics


def update_model(symbols: list[str] | None = None,
                 universe: str | None = None,
                 progress_callback=None) -> tuple[BoomPredictor, dict]:
    """Update an existing model with data from its last training date to today.

    Loads the saved model, checks how many days are missing, fetches only
    those days, and does incremental training (warm-start) instead of full
    retrain. Much faster than train_model() for small gaps.

    Returns:
        (updated model, update metrics including gap_days)
    """
    if symbols is None:
        symbols = ALL_STOCKS

    def _update(phase, progress, message):
        if progress_callback:
            progress_callback(phase, progress, message)
        print(f"  {message}")

    uni_label = universe or "All Stocks"
    model = BoomPredictor()

    if not model.load(universe=uni_label):
        _update("fetch", 0.0, f"No existing model for '{uni_label}'. Running full train...")
        return train_model(symbols, universe=universe,
                           progress_callback=progress_callback)

    today = date.today()
    trained_until = model.trained_until

    if trained_until is None:
        _update("fetch", 0.0,
                "Model has no training date recorded. Running full retrain...")
        return train_model(symbols, universe=universe,
                           progress_callback=progress_callback)

    gap_days = (today - trained_until).days
    if gap_days <= 0:
        _update("save", 1.0, "Model is already up to date!")
        return model, {
            "status": "up_to_date",
            "trained_until": str(trained_until),
            "gap_days": 0,
        }

    _update("fetch", 0.0,
            f"Model trained until {trained_until}. "
            f"Gap: {gap_days} days. Fetching new data...")

    # Fetch extra lookback days so indicators (EMA-20, RSI-14, etc.) can warm up
    lookback_buffer = 60
    fetch_days = gap_days + lookback_buffer

    all_X = []
    all_y = []
    stocks_updated = 0

    for i, symbol in enumerate(symbols):
        try:
            daily_df = fetch_daily(symbol, days=fetch_days)
            if daily_df is None or len(daily_df) < 30:
                continue

            # Only build labels for rows AFTER the training cutoff
            cutoff_mask = daily_df.index.date > trained_until
            if cutoff_mask.sum() < 2:
                continue

            X, y = build_training_data(daily_df)
            if len(X) == 0:
                continue

            # Keep only samples from after the cutoff
            # The last `cutoff_mask.sum()` rows in X correspond to new days
            new_count = min(cutoff_mask.sum(), len(X))
            all_X.append(X[-new_count:])
            all_y.append(y[-new_count:])
            stocks_updated += 1
        except Exception:
            continue

        pct = (i + 1) / len(symbols)
        _update("fetch", pct * 0.70,
                f"[{i+1}/{len(symbols)}] {symbol} | "
                f"{stocks_updated} stocks with new data")

    if not all_X:
        _update("save", 1.0, "No new data found for any stock.")
        return model, {"status": "no_new_data", "gap_days": gap_days}

    X_combined = np.vstack(all_X)
    y_combined = np.concatenate(all_y)

    _update("train", 0.75,
            f"Updating model with {len(X_combined):,} new samples "
            f"({int(y_combined.sum()):,} positive) from {stocks_updated} stocks...")

    metrics = model.update(X_combined, y_combined)
    metrics["gap_days"] = gap_days
    metrics["trained_from"] = str(trained_until)
    metrics["stocks_updated"] = stocks_updated

    _update("save", 0.95, "Saving updated model...")
    model.save(universe=uni_label)

    _update("save", 1.0,
            f"Done! Model updated with {gap_days} days of new data.")

    return model, metrics


def predict_boom_stocks(symbols: list[str] | None = None,
                        top_n: int = 15,
                        universe: str | None = None) -> tuple[list[BoomCandidate], dict]:
    """Run the full AI pipeline to find stocks most likely to boom tomorrow.

    Pipeline:
    1. Fetch global macro data → compute macro score
    2. Fetch news → compute sentiment per stock
    3. Load per-universe ML model (or auto-train on ALL stocks)
    4. Score each stock → get boom probability
    5. Combine all scores → rank stocks

    Args:
        symbols: Stock universe.
        top_n: Number of top candidates to return.
        universe: Universe name (for loading the correct model).

    Returns:
        (list of BoomCandidate, context dict with macro/news info)
    """
    if symbols is None:
        symbols = ALL_STOCKS

    # --- Step 1: Macro data ---
    print("  [1/5] Fetching global macro data...")
    global_snapshot = fetch_global_snapshot()
    macro_result = compute_macro_score(global_snapshot)
    sector_signals = get_sector_rotation_signals(global_snapshot)
    macro_score = macro_result["macro_score"]
    print(f"         Macro score: {macro_score} ({macro_result['market_mood']})")

    # --- Step 2: News sentiment ---
    print("  [2/5] Fetching news & analyzing sentiment...")
    all_news = fetch_news(max_age_hours=48)
    print(f"         Fetched {len(all_news)} news items")

    # --- Step 3: Load model (per-universe, with fallback to All Stocks) ---
    uni_label = universe or "All Stocks"
    print(f"  [3/5] Loading ML model for '{uni_label}'...")
    model = BoomPredictor()
    if not model.load(universe=uni_label):
        # Fallback: try loading the "All Stocks" model (trained on everything)
        if uni_label != "All Stocks" and model.load(universe="All Stocks"):
            print(f"         No '{uni_label}' model found. Using 'All Stocks' model (covers all stocks).")
        else:
            print(f"         No saved model found. Training on ALL {len(symbols)} stocks (full history)...")
            model, train_metrics = train_model(symbols, universe=uni_label)
            if not model.is_trained:
                print("         [ERROR] Model training failed!")
                return [], {"error": "Model training failed"}
            print(f"         Model trained. AUC: {train_metrics.get('mean_auc', 'N/A')}")

    # --- Step 3.5: Load F&O classification ---
    fno_set = get_fno_stocks()
    intraday_map = classify_intraday_eligibility(symbols, fno_set)
    print(f"         F&O stocks in scan: {sum(1 for v in intraday_map.values() if v == 'FNO_INTRADAY')}")

    # --- Step 4: Score each stock ---
    print(f"  [4/5] Scoring {len(symbols)} stocks...")
    candidates = []

    for i, symbol in enumerate(symbols):
        try:
            # Sentiment for this stock
            sentiment_data = aggregate_sentiment_for_stock(all_news, symbol)
            sentiment_score = sentiment_data["avg_sentiment"]

            # Sector rotation score
            sector = SYMBOL_SECTOR_MAP.get(symbol, "")
            sector_score = sector_signals.get(sector, 0.0)

            # Fetch daily data
            daily_df = fetch_daily(symbol, days=60)
            if daily_df is None or len(daily_df) < 25:
                continue

            # Build features for today (last available day)
            feat = build_ml_features_for_day(
                daily_df, len(daily_df) - 1,
                sentiment_score=sentiment_score,
                macro_score=macro_score / 10,  # Normalize to ~(-1, 1)
                sector_score=sector_score,
            )
            if feat is None:
                continue

            # ML prediction
            feature_vector = np.array([feat[col] for col in FEATURE_COLUMNS])
            boom_prob = model.predict_single(feature_vector)

            # Confidence level
            if boom_prob >= 0.7:
                confidence = "HIGH"
            elif boom_prob >= 0.45:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"

            # Classify trade type
            raw_type = intraday_map.get(symbol, "NON_FNO")
            if raw_type == "FNO_INTRADAY":
                trade_type = "FNO_INTRADAY"
            else:
                # Non-F&O: check avg volume — if > 500K, likely
                # broker-allowed for intraday
                avg_vol = float(daily_df["Volume"].tail(10).mean())
                if avg_vol >= 500_000:
                    trade_type = "NON_FNO_INTRADAY"
                else:
                    trade_type = "DELIVERY_ONLY"

            candidates.append(BoomCandidate(
                symbol=symbol,
                index_rank=RANK_MAP.get(symbol, 999),
                boom_probability=round(boom_prob * 100, 1),
                sentiment_score=round(sentiment_score, 4),
                sentiment_label=sentiment_data["sentiment_label"],
                macro_score=macro_score,
                market_mood=macro_result["market_mood"],
                sector_score=round(sector_score, 2),
                technical_summary={
                    "rsi": feat["rsi"],
                    "returns_5d": feat["returns_5d"],
                    "returns_10d": feat["returns_10d"],
                    "rel_vol": feat["rel_vol"],
                    "ema_bullish": feat["ema_bullish"],
                    "gap_pct": feat["gap_pct"],
                },
                top_headlines=sentiment_data["top_headlines"],
                confidence=confidence,
                trade_type=trade_type,
            ))
        except Exception as e:
            continue

        if (i + 1) % 25 == 0:
            print(f"         ... scored {i + 1}/{len(symbols)}")

    # --- Step 5: Rank ---
    print("  [5/5] Ranking candidates...")

    # Sort by boom probability (desc), then index rank (asc) as tiebreaker
    candidates.sort(key=lambda c: (-c.boom_probability, c.index_rank))

    context = {
        "macro": macro_result,
        "global_snapshot": global_snapshot,
        "sector_signals": sector_signals,
        "total_news": len(all_news),
        "stocks_scored": len(candidates),
    }

    return candidates[:top_n], context
