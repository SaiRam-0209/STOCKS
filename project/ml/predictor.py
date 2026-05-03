"""Boom predictor: orchestrates news + macro + ML to rank gap breakout stocks."""

from __future__ import annotations

import numpy as np
import os
import joblib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from dataclasses import dataclass
from itertools import groupby

from project.data.fetcher import fetch_daily
from project.data.symbols import ALL_STOCKS, RANK_MAP
from project.data.symbols_fetcher import get_fno_stocks, classify_intraday_eligibility
from project.ml.model import MODEL_DIR, BreakoutRanker
from project.news.fetcher import fetch_news
from project.news.sentiment import aggregate_sentiment_for_stock
from project.macro.global_data import (
    fetch_global_snapshot, compute_macro_score, get_sector_rotation_signals,
)
from project.ml.features import (
    build_breakout_features_for_day,
    build_breakout_training_data,
    label_to_expected_move,
    BREAKOUT_FEATURE_COLUMNS,
    GAP_THRESHOLD,
    REL_VOL_THRESHOLD,
)
from project.features.indicators import gap_percentage, relative_volume, rsi, ema
from project.data.sectors import get_sector


SYMBOL_SECTOR_MAP = {
    # Technology
    "KPITTECH.NS": "technology", "CYIENT.NS": "technology",
    "HAPPSTMNDS.NS": "technology", "MASTEK.NS": "technology",
    "ZENSARTECH.NS": "technology", "BSOFT.NS": "technology",
    "NEWGEN.NS": "technology", "SONATSOFTW.NS": "technology",
    "LATENTVIEW.NS": "technology", "RATEGAIN.NS": "technology",
    # Fintech / Banking
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
    # Power / Metals
    "HBLPOWER.NS": "metals", "JPPOWER.NS": "metals",
    "CESC.NS": "metals", "POWERINDIA.NS": "metals",
    # Railway / Oil / Jewellery / Solar
    "TITAGARH.NS": "infrastructure",
    "MRPL.NS": "oil_gas", "SPLPETRO.NS": "oil_gas",
    "KALYANKJIL.NS": "gold_jewellery", "SENCO.NS": "gold_jewellery",
    "SUZLON.NS": "metals", "INOXWIND.NS": "metals", "SWSOLAR.NS": "metals",
    "KAYNES.NS": "technology", "SYRMA.NS": "technology", "AMBER.NS": "technology",
}


@dataclass
class BoomCandidate:
    symbol: str
    index_rank: int
    boom_probability: float    # Normalized ranking score 0–100 (higher = better ranked)
    sentiment_score: float
    sentiment_label: str
    macro_score: float
    market_mood: str
    sector_score: float
    technical_summary: dict
    top_headlines: list[dict]
    confidence: str            # HIGH / MEDIUM / LOW (based on score percentile)
    trade_type: str            # FNO_INTRADAY / NON_FNO_INTRADAY / DELIVERY_ONLY
    expected_move: str = "?"   # "+3", "+2", "+1", "0", "-1" — predicted breakout category
    move_score: float = 0.0    # Raw ranker score (for sorting)


# ─── Checkpoint helpers ───────────────────────────────────────────────────────

def _checkpoint_path(universe: str | None) -> str:
    os.makedirs(MODEL_DIR, exist_ok=True)
    label = (universe or "all_stocks").lower().replace(" ", "_")
    return os.path.join(MODEL_DIR, f"checkpoint_{label}.joblib")


def _save_checkpoint(path: str, done_symbols: list[str],
                     all_samples: list, total_days: int):
    joblib.dump({
        "done_symbols": done_symbols,
        "all_samples": all_samples,
        "total_days": total_days,
    }, path)


def _load_checkpoint(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        return joblib.load(path)
    except Exception:
        return None


# ─── Training ─────────────────────────────────────────────────────────────────

def train_model(
    symbols: list[str] | None = None,
    universe: str | None = None,
    progress_callback=None,
    months: int | None = None,
) -> tuple[BreakoutRanker, dict]:
    """Train the BreakoutRanker on historical gap-day data.

    Collects (date, features, label) samples from all stocks, groups them
    by trading date, then trains the XGBRanker so it learns cross-stock
    ranking within each day.

    Supports resumable training — checkpoints every 25 stocks.

    Args:
        symbols: Stocks to train on.
        universe: Universe name for model file naming.
        progress_callback: Optional callable(phase, progress, message).
        months: If set, only use data from the last N months (e.g. 12 for
                time-aware training). None = full history.
    """
    if symbols is None:
        symbols = ALL_STOCKS

    def _update(phase, progress, message):
        if progress_callback:
            progress_callback(phase, progress, message)
        print(f"  {message}")

    ckpt_path = _checkpoint_path(universe)
    ckpt = _load_checkpoint(ckpt_path)

    if ckpt:
        done_set = set(ckpt["done_symbols"])
        all_samples = ckpt["all_samples"]
        total_days = ckpt["total_days"]
        _update("fetch", 0.0,
                f"Resuming from checkpoint: {len(done_set)}/{len(symbols)} done...")
    else:
        done_set = set()
        all_samples = []
        total_days = 0
        _update("fetch", 0.0, f"Fetching gap-day data for {len(symbols)} stocks...")

    done_symbols = list(done_set)
    cutoff_date = date.today() - timedelta(days=months * 30) if months is not None else None
    remaining = [s for s in symbols if s not in done_set]

    def _fetch_and_extract(symbol: str) -> tuple[str, list, int]:
        """Fetch daily data and extract gap-day samples for one symbol."""
        try:
            if months is None:
                daily_df = fetch_daily(symbol, max_data=True)
            else:
                daily_df = fetch_daily(symbol, days=months * 31)
            if daily_df is None or len(daily_df) < 50:
                return symbol, [], 0
            if cutoff_date is not None:
                daily_df = daily_df[daily_df.index.date >= cutoff_date]
                if len(daily_df) < 50:
                    return symbol, [], 0
            samples = build_breakout_training_data(daily_df)
            return symbol, samples, len(daily_df)
        except Exception:
            return symbol, [], 0

    # Parallel fetch — yfinance is I/O bound, 8 threads saturates M2 network
    completed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_and_extract, s): s for s in remaining}
        for future in as_completed(futures):
            symbol, samples, n_days = future.result()
            all_samples.extend(samples)
            total_days += n_days
            done_symbols.append(symbol)
            done_set.add(symbol)
            completed += 1

            # Checkpoint every 100 completed stocks
            if completed % 100 == 0:
                _save_checkpoint(ckpt_path, done_symbols, all_samples, total_days)

            pct = len(done_set) / len(symbols)
            _update("fetch", pct * 0.70,
                    f"[{len(done_set)}/{len(symbols)}] {symbol} | "
                    f"{len(all_samples):,} gap samples | {total_days:,} total days")

    if not all_samples:
        if os.path.exists(ckpt_path):
            os.remove(ckpt_path)
        return BreakoutRanker(), {"error": "No gap-day samples found"}

    # Sort by date and build rank groups
    all_samples.sort(key=lambda x: x[0])

    X_list, y_list, groups = [], [], []
    for _, group_iter in groupby(all_samples, key=lambda x: x[0]):
        group = list(group_iter)
        if len(group) < 2:
            continue  # Ranker needs >=2 items per group for pairwise comparison
        groups.append(len(group))
        for _, feat_vec, label in group:
            X_list.append(feat_vec)
            y_list.append(label)

    if not X_list:
        if os.path.exists(ckpt_path):
            os.remove(ckpt_path)
        return BreakoutRanker(), {"error": "No multi-stock gap days found for ranking"}

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)

    _update("train", 0.72,
            f"Training BreakoutRanker: {len(X):,} samples, "
            f"{len(groups):,} date-groups, avg {len(X)/len(groups):.1f} stocks/day...")

    model = BreakoutRanker()
    metrics = model.train(X, y, groups)
    metrics["total_daily_candles"] = total_days
    metrics["total_gap_samples"] = len(X)

    _update("save", 0.96, "Saving model...")
    model.save(universe=universe)

    if os.path.exists(ckpt_path):
        os.remove(ckpt_path)

    _update("save", 1.0,
            f"Done! {len(X):,} gap samples from {len(groups):,} trading days. "
            f"Strong setups: {metrics.get('strong_pct', '?')}%")

    return model, metrics


def update_model(
    symbols: list[str] | None = None,
    universe: str | None = None,
    progress_callback=None,
) -> tuple[BreakoutRanker, dict]:
    """Retrain on the last 12 months of data (time-aware refresh).

    XGBRanker does not support warm-start, so updates retrain on a rolling
    12-month window. This is actually better for non-stationarity — recent
    market behavior matters more than data from 3 years ago.
    """
    if symbols is None:
        symbols = ALL_STOCKS

    def _update(phase, progress, message):
        if progress_callback:
            progress_callback(phase, progress, message)
        print(f"  {message}")

    model = BreakoutRanker()
    uni_label = universe or "All Stocks"

    if not model.load(universe=uni_label):
        _update("fetch", 0.0, f"No existing model for '{uni_label}'. Running full train...")
        return train_model(symbols, universe=universe,
                           progress_callback=progress_callback)

    today = date.today()
    trained_until = model.trained_until

    if trained_until is not None:
        gap_days = (today - trained_until).days
        if gap_days <= 0:
            _update("save", 1.0, "Model is already up to date!")
            return model, {"status": "up_to_date", "trained_until": str(trained_until), "gap_days": 0}
        _update("fetch", 0.0,
                f"Model trained until {trained_until} ({gap_days}d behind). "
                f"Retraining on last 12 months...")
    else:
        _update("fetch", 0.0, "Retraining on last 12 months (time-aware refresh)...")

    new_model, metrics = train_model(
        symbols, universe=universe,
        progress_callback=progress_callback,
        months=12,
    )
    if trained_until:
        metrics["gap_days"] = gap_days
        metrics["trained_from"] = str(trained_until)
    return new_model, metrics


# ─── Prediction ───────────────────────────────────────────────────────────────

def predict_boom_stocks(
    symbols: list[str] | None = None,
    top_n: int = 15,
    universe: str | None = None,
) -> tuple[list[BoomCandidate], dict]:
    """Run the full AI pipeline to rank today's gap breakout candidates.

    Pipeline:
    1. Fetch global macro data
    2. Fetch news sentiment
    3. Load BreakoutRanker model
    4. Find stocks currently gapping >= 2% with volume >= 1.5x
    5. Score each with the ranker, return top N ranked by score

    Returns:
        (ranked candidates, context dict)
    """
    if symbols is None:
        symbols = ALL_STOCKS

    # ── 1. Macro + Institutional Flow ─────────────────────
    print("  [1/5] Fetching global macro + institutional flow data...")
    global_snapshot = fetch_global_snapshot()
    macro_result = compute_macro_score(global_snapshot)
    sector_signals = get_sector_rotation_signals(global_snapshot)
    macro_score = macro_result["macro_score"]

    # FII/DII flow
    from project.data.fii_dii import fetch_institutional_flow
    _fii_data = fetch_institutional_flow()
    _fii_flow_score = _fii_data["flow_score"]
    print(f"         Macro score: {macro_score} ({macro_result['market_mood']})")
    print(f"         FII flow: {_fii_data['fii_sentiment']} (score: {_fii_flow_score})")

    # ── 2. News ──────────────────────────────────────────
    print("  [2/5] Fetching news & analyzing sentiment...")
    all_news = fetch_news(max_age_hours=48)
    print(f"         {len(all_news)} news items")

    # ── 3. Load model ────────────────────────────────────
    uni_label = universe or "All Stocks"
    print(f"  [3/5] Loading BreakoutRanker for '{uni_label}'...")
    model = BreakoutRanker()
    if not model.load(universe=uni_label):
        if uni_label != "All Stocks" and model.load(universe="All Stocks"):
            print("         No universe-specific model. Using All Stocks model.")
        else:
            print(f"         No saved model. Training on {len(symbols)} stocks...")
            model, _ = train_model(symbols, universe=uni_label)
            if not model.is_trained:
                return [], {"error": "Model training failed"}

    # ── 3.5. F&O classification ──────────────────────────
    fno_set = get_fno_stocks()
    intraday_map = classify_intraday_eligibility(symbols, fno_set)
    fno_count = sum(1 for v in intraday_map.values() if v == "FNO_INTRADAY")
    print(f"         F&O stocks in scan: {fno_count}")

    # ── 4. Score gap stocks ──────────────────────────────
    print(f"  [4/5] Scanning {len(symbols)} stocks for gap setups...")
    gap_stocks = []

    for i, symbol in enumerate(symbols):
        try:
            daily_df = fetch_daily(symbol, days=80)
            if daily_df is None or len(daily_df) < 30:
                continue

            last_idx = len(daily_df) - 1
            last_row = daily_df.iloc[last_idx]
            prev_close = float(daily_df.iloc[last_idx - 1]["Close"])

            if prev_close <= 0:
                continue

            gap_pct = gap_percentage(float(last_row["Open"]), prev_close)
            if abs(gap_pct) < GAP_THRESHOLD:
                continue

            avg_vol = float(daily_df["Volume"].iloc[last_idx - 10:last_idx].mean())
            rel_vol = relative_volume(float(last_row["Volume"]), avg_vol)
            if rel_vol < REL_VOL_THRESHOLD:
                continue

            # Build features at breakout moment
            from project.data.sectors import get_sector as _get_sector
            sector = _get_sector(symbol) or SYMBOL_SECTOR_MAP.get(symbol, "")
            sec_score = sector_signals.get(sector, 0.0)

            # Earnings likelihood
            from project.data.earnings import earnings_likelihood as _earn_like
            _stock_headlines = [
                a["title"] for a in all_news
                if symbol.replace(".NS", "").lower() in a.get("title", "").lower()
            ]
            _earn_flag = _earn_like(gap_pct, rel_vol, news_headlines=_stock_headlines)

            # News sentiment for this stock
            _sent_data = aggregate_sentiment_for_stock(all_news, symbol)
            _news_sent = _sent_data["avg_sentiment"]

            feat = build_breakout_features_for_day(
                daily_df, last_idx,
                macro_score=macro_score / 10,
                sector_score=sec_score,
                earnings_flag=_earn_flag,
                news_sentiment=_news_sent,
                fii_flow_score=_fii_flow_score,
            )
            if feat is None:
                continue

            feat_vec = np.array(
                [feat[col] for col in BREAKOUT_FEATURE_COLUMNS], dtype=np.float32
            )
            if not np.all(np.isfinite(feat_vec)):
                continue

            # Compute display-only indicators (not used by ranker)
            close_series = daily_df["Close"]
            rsi_val = float(rsi(close_series, 14).iloc[-1])
            ema20_val = float(ema(close_series, 20).iloc[-1])
            returns_5d = float(
                (close_series.iloc[-1] - close_series.iloc[-6]) /
                close_series.iloc[-6] * 100
            ) if len(close_series) >= 6 else 0.0

            gap_stocks.append({
                "symbol": symbol,
                "feat_vec": feat_vec,
                "feat": feat,
                "gap_pct": gap_pct,
                "rel_vol": rel_vol,
                "avg_vol": avg_vol,
                "rsi": rsi_val,
                "ema20_bullish": close_series.iloc[-1] > ema20_val,
                "returns_5d": returns_5d,
                "sec_score": sec_score,
            })
        except Exception:
            continue

        if (i + 1) % 50 == 0:
            print(f"         ... scanned {i+1}/{len(symbols)}, {len(gap_stocks)} gap stocks found")

    if not gap_stocks:
        return [], {
            "macro": macro_result,
            "global_snapshot": global_snapshot,
            "sector_signals": sector_signals,
            "total_news": len(all_news),
            "stocks_scored": 0,
            "gap_stocks_found": 0,
            "warning": "No stocks passing gap+volume filter today",
        }

    print(f"         {len(gap_stocks)} stocks with gap >= {GAP_THRESHOLD}% and vol >= {REL_VOL_THRESHOLD}x")

    # ── 5. Rank ──────────────────────────────────────────
    print("  [5/5] Ranking by breakout quality...")

    X_all = np.array([s["feat_vec"] for s in gap_stocks], dtype=np.float32)
    scores = model.score(X_all)

    # Normalize scores to 0–100 for display
    score_min, score_max = scores.min(), scores.max()
    score_range = score_max - score_min if score_max > score_min else 1.0
    norm_scores = (scores - score_min) / score_range * 100

    # Score percentile thresholds for confidence
    p75 = float(np.percentile(scores, 75))
    p50 = float(np.percentile(scores, 50))

    candidates = []
    for stock, raw_score, norm_score in zip(gap_stocks, scores, norm_scores):
        symbol = stock["symbol"]
        sentiment_data = aggregate_sentiment_for_stock(all_news, symbol)

        confidence = "HIGH" if raw_score >= p75 else ("MEDIUM" if raw_score >= p50 else "LOW")

        raw_type = intraday_map.get(symbol, "NON_FNO")
        if raw_type == "FNO_INTRADAY":
            trade_type = "FNO_INTRADAY"
        elif stock["avg_vol"] >= 500_000:
            trade_type = "NON_FNO_INTRADAY"
        else:
            trade_type = "DELIVERY_ONLY"

        candidates.append(BoomCandidate(
            symbol=symbol,
            index_rank=RANK_MAP.get(symbol, 999),
            boom_probability=round(float(norm_score), 1),
            sentiment_score=round(sentiment_data["avg_sentiment"], 4),
            sentiment_label=sentiment_data["sentiment_label"],
            macro_score=macro_score,
            market_mood=macro_result["market_mood"],
            sector_score=round(stock["sec_score"], 2),
            technical_summary={
                "gap_pct": stock["gap_pct"],
                "gap_vs_atr": stock["feat"]["gap_vs_atr"],
                "rel_vol": round(stock["rel_vol"], 2),
                "ema20_slope": stock["feat"]["ema20_slope"],
                "ema_bullish": 1.0 if stock["ema20_bullish"] else 0.0,
                "rsi": round(stock["rsi"], 1),
                "returns_5d": round(stock["returns_5d"], 1),
                "range_compression": stock["feat"]["range_compression"],
            },
            top_headlines=sentiment_data["top_headlines"],
            confidence=confidence,
            trade_type=trade_type,
            expected_move=label_to_expected_move(float(raw_score)),
            move_score=round(float(raw_score), 3),
        ))

    # Sort by raw ranker score descending
    candidates.sort(key=lambda c: -c.move_score)

    context = {
        "macro": macro_result,
        "global_snapshot": global_snapshot,
        "sector_signals": sector_signals,
        "total_news": len(all_news),
        "stocks_scored": len(candidates),
        "gap_stocks_found": len(gap_stocks),
    }

    return candidates[:top_n], context
