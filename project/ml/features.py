"""ML feature pipeline: breakout-quality features for ORB gap trade ranking.

Replaces the old generic daily features (RSI, EMA crossover, MACD-style)
with features specifically designed to measure breakout quality at the
exact moment a gap trade is entered.

All features are computable from data known BEFORE market open, so there
is zero look-ahead bias in live prediction.
"""

import numpy as np
import pandas as pd
from project.features.indicators import gap_percentage, relative_volume, ema, atr
from project.data.sectors import get_sector
from project.data.earnings import earnings_likelihood, is_result_season

# Live prediction filter (same as backtest engine)
GAP_THRESHOLD = 2.0
REL_VOL_THRESHOLD = 1.5

# Slightly looser thresholds for training to capture more examples
TRAIN_GAP_THRESHOLD = 1.5
TRAIN_REL_VOL_THRESHOLD = 1.2

BREAKOUT_FEATURE_COLUMNS = [
    # Gap characteristics
    "gap_pct",            # Gap size in % (signed: +ve = gap-up, -ve = gap-down)
    "gap_abs",            # Absolute gap magnitude
    "gap_vs_atr",         # Gap / ATR — how significant is this gap vs normal volatility
    "gap_percentile",     # Where this gap ranks vs last 252 trading days (0–1)
    "gap_trend_aligned",  # 1 if gap direction matches the 20d EMA trend
    # Volume dynamics
    "rel_vol",            # Volume vs 10d average
    "vol_rank_20d",       # Volume percentile in last 20 days (0–1)
    "vol_acceleration",   # Today vol / 3d avg vol — sudden spike detection
    # Price structure & trend
    "open_vs_ema20",      # % distance of today's open from EMA20
    "ema20_slope",        # EMA20 slope over last 5 days (trend momentum)
    "pre_gap_momentum",   # 3d return before gap day (stock already running?)
    # Volatility & compression
    "atr_pct",            # ATR as % of price
    "range_compression",  # ATR5 / ATR20 — lower = more compressed = sharper breakout expected
    # External context
    "macro_score",
    "sector_score",
    # ── NEW: 5 upgraded features ──────────────────────────
    "earnings_flag",      # 0-1: likelihood this gap is earnings-driven
    "news_sentiment",     # -1 to +1: news sentiment score for this stock
    "fii_flow_score",     # -1 to +1: institutional money flow direction
    "prev_day_pattern",   # 0-3: candle pattern (0=none, 1=doji, 2=inside bar, 3=narrow range)
    "prev_day_body_pct",  # body/range ratio of previous candle (0-1)
]


def build_breakout_features_for_day(
    daily_df: pd.DataFrame,
    day_idx: int,
    macro_score: float = 0.0,
    sector_score: float = 0.0,
    _precomputed_gap_percentile: float | None = None,
    # ── New feature inputs ──
    earnings_flag: float = 0.0,
    news_sentiment: float = 0.0,
    fii_flow_score: float = 0.0,
) -> dict | None:
    """Build breakout-quality features for one gap day.

    Args:
        daily_df: Full daily OHLCV DataFrame.
        day_idx: Index of the day in daily_df.
        macro_score: Global macro score.
        sector_score: Sector rotation score.
        _precomputed_gap_percentile: Optional precomputed value (pass from
            build_breakout_training_data for speed — avoids recomputing the
            252-day window for every sample).

    Returns:
        Feature dict, or None if insufficient history.
    """
    if day_idx < 25 or day_idx >= len(daily_df):
        return None

    row = daily_df.iloc[day_idx]
    prev = daily_df.iloc[day_idx - 1]

    open_px = float(row["Open"])
    prev_close = float(prev["Close"])
    volume = float(row["Volume"])

    if prev_close <= 0 or open_px <= 0:
        return None

    # ── Gap ─────────────────────────────────────────────
    gap_pct = gap_percentage(open_px, prev_close)
    gap_abs = abs(gap_pct)

    # ATR from data up to (but not including) today
    hist_df = daily_df.iloc[:day_idx]
    atr_series = atr(hist_df, 14)
    if len(atr_series) < 14:
        return None
    current_atr = float(atr_series.iloc[-1])
    if current_atr <= 0:
        return None

    atr_pct = (current_atr / prev_close) * 100
    gap_vs_atr = gap_abs / atr_pct if atr_pct > 0 else 0.0

    # Gap percentile vs last 252 days (expensive if called per-sample; pass
    # _precomputed_gap_percentile from build_breakout_training_data instead)
    if _precomputed_gap_percentile is not None:
        gap_percentile = _precomputed_gap_percentile
    else:
        start = max(1, day_idx - 252)
        hist_gaps = [
            abs(gap_percentage(
                float(daily_df["Open"].iloc[j]),
                float(daily_df["Close"].iloc[j - 1]),
            ))
            for j in range(start, day_idx)
            if float(daily_df["Close"].iloc[j - 1]) > 0
        ]
        gap_percentile = (
            float(np.searchsorted(np.sort(hist_gaps), gap_abs) / len(hist_gaps))
            if hist_gaps else 0.5
        )

    # Gap aligned with 20d trend?
    close_hist = daily_df["Close"].iloc[:day_idx]
    ema20 = ema(close_hist, 20)
    ema20_now = float(ema20.iloc[-1])
    ema20_5ago = float(ema20.iloc[-5]) if len(ema20) >= 5 else ema20_now
    trend_up = ema20_now > ema20_5ago
    gap_trend_aligned = 1.0 if (
        (gap_pct > 0 and trend_up) or (gap_pct < 0 and not trend_up)
    ) else 0.0

    # ── Volume ───────────────────────────────────────────
    avg_vol_10 = float(daily_df["Volume"].iloc[day_idx - 10:day_idx].mean())
    rel_vol = relative_volume(volume, avg_vol_10)

    vol_20d = daily_df["Volume"].iloc[day_idx - 20:day_idx]
    vol_rank_20d = float((vol_20d < volume).sum()) / len(vol_20d) if len(vol_20d) > 0 else 0.5

    avg_vol_3 = float(daily_df["Volume"].iloc[day_idx - 3:day_idx].mean())
    vol_acceleration = min(volume / avg_vol_3, 20.0) if avg_vol_3 > 0 else 1.0

    # ── Price structure ──────────────────────────────────
    open_vs_ema20 = ((open_px - ema20_now) / ema20_now) * 100 if ema20_now > 0 else 0.0
    ema20_slope = ((ema20_now - ema20_5ago) / ema20_5ago) * 100 if ema20_5ago > 0 else 0.0

    pre_gap_momentum = 0.0
    if day_idx >= 4:
        close_3ago = float(daily_df["Close"].iloc[day_idx - 4])
        if close_3ago > 0:
            pre_gap_momentum = ((prev_close - close_3ago) / close_3ago) * 100

    # ── Volatility compression ───────────────────────────
    atr5_series = atr(hist_df, 5)
    atr5 = float(atr5_series.iloc[-1]) if len(atr5_series) >= 5 else current_atr
    range_compression = atr5 / current_atr if current_atr > 0 else 1.0

    # ── NEW: Previous day candle pattern ──────────────────
    prev_open = float(prev["Open"])
    prev_high = float(prev["High"])
    prev_low = float(prev["Low"])
    prev_range = prev_high - prev_low

    # Body as % of total range (small body = indecision)
    prev_body = abs(float(prev["Close"]) - prev_open)
    prev_day_body_pct = prev_body / prev_range if prev_range > 0 else 0.5

    # Pattern detection
    prev_day_pattern = 0.0
    if prev_range > 0:
        body_ratio = prev_body / prev_range
        if body_ratio < 0.1:
            prev_day_pattern = 1.0   # Doji — extreme indecision → breakout imminent
        elif day_idx >= 2:
            # Inside bar: today's prev candle fits inside the one before it
            pprev = daily_df.iloc[day_idx - 2]
            if prev_high <= float(pprev["High"]) and prev_low >= float(pprev["Low"]):
                prev_day_pattern = 2.0   # Inside bar — compression → explosion
        # Narrow range day: range < 50% of ATR
        if current_atr > 0 and prev_range < 0.5 * current_atr:
            prev_day_pattern = max(prev_day_pattern, 3.0)  # NR day

    return {
        "gap_pct": round(gap_pct, 4),
        "gap_abs": round(gap_abs, 4),
        "gap_vs_atr": round(gap_vs_atr, 4),
        "gap_percentile": round(gap_percentile, 4),
        "gap_trend_aligned": gap_trend_aligned,
        "rel_vol": round(rel_vol, 4),
        "vol_rank_20d": round(vol_rank_20d, 4),
        "vol_acceleration": round(vol_acceleration, 4),
        "open_vs_ema20": round(open_vs_ema20, 4),
        "ema20_slope": round(ema20_slope, 4),
        "pre_gap_momentum": round(pre_gap_momentum, 4),
        "atr_pct": round(atr_pct, 4),
        "range_compression": round(range_compression, 4),
        "macro_score": round(macro_score, 4),
        "sector_score": round(sector_score, 4),
        # ── New features ──
        "earnings_flag": round(earnings_flag, 4),
        "news_sentiment": round(news_sentiment, 4),
        "fii_flow_score": round(fii_flow_score, 4),
        "prev_day_pattern": prev_day_pattern,
        "prev_day_body_pct": round(prev_day_body_pct, 4),
    }


def compute_breakout_label(daily_df: pd.DataFrame, day_idx: int) -> float:
    """Compute how strongly the stock moved after the gap, in multiples of the gap.

    For LONG (gap-up):  label = (day_high - day_open) / gap_amount
    For SHORT (gap-down): label = (day_open - day_low) / |gap_amount|

    Interpretation:
        >= 3.0 → exceptional: moved 3× gap (ORB target at 2R comfortably exceeded)
        >= 2.0 → strong: ORB target hit
        >= 1.0 → decent: halfway to ORB target
           0.0 → no move
        <  0.0 → reversal

    Capped at [-2.0, 6.0].
    """
    row = daily_df.iloc[day_idx]
    prev_close = float(daily_df.iloc[day_idx - 1]["Close"])

    open_px = float(row["Open"])
    high_px = float(row["High"])
    low_px = float(row["Low"])

    gap_amount = open_px - prev_close
    if abs(gap_amount) < 1e-6:
        return 0.0

    if gap_amount > 0:
        move = high_px - open_px
    else:
        move = open_px - low_px
        gap_amount = abs(gap_amount)

    return float(np.clip(move / gap_amount, -2.0, 6.0))


def build_breakout_training_data(
    daily_df: pd.DataFrame,
    gap_min: float = TRAIN_GAP_THRESHOLD,
    rel_vol_min: float = TRAIN_REL_VOL_THRESHOLD,
) -> list[tuple[str, np.ndarray, float]]:
    """Extract (date, features, label) tuples for every qualifying gap day.

    Only includes days where gap >= gap_min% AND relative volume >= rel_vol_min.
    This focuses the dataset entirely on actual ORB trade scenarios.

    Returns:
        List of (date_str, feature_vector, label) for grouping by date
        in train_model().
    """
    if len(daily_df) < 30:
        return []

    # Precompute all daily gaps (vectorized) to speed up gap_percentile calc
    opens = daily_df["Open"].values
    closes = daily_df["Close"].values
    all_gaps_abs = np.where(
        closes[:-1] > 0,
        np.abs((opens[1:] - closes[:-1]) / closes[:-1] * 100),
        0.0,
    )  # all_gaps_abs[i] = gap for daily_df.iloc[i+1]

    samples: list[tuple[str, np.ndarray, float]] = []

    for i in range(25, len(daily_df)):
        prev_close = closes[i - 1]
        if prev_close <= 0:
            continue

        gap_pct_raw = (opens[i] - prev_close) / prev_close * 100
        gap_abs_val = abs(gap_pct_raw)
        if gap_abs_val < gap_min:
            continue

        avg_vol_10 = float(daily_df["Volume"].iloc[i - 10:i].mean())
        if avg_vol_10 <= 0:
            continue
        rel_vol_val = float(daily_df["Volume"].iloc[i]) / avg_vol_10
        if rel_vol_val < rel_vol_min:
            continue

        # Fast gap_percentile using precomputed array + binary search
        start = max(0, i - 1 - 252)
        window = all_gaps_abs[start:i - 1]
        gap_percentile = (
            float(np.searchsorted(np.sort(window), gap_abs_val) / len(window))
            if len(window) > 0 else 0.5
        )

        # Compute earnings likelihood for training data
        trade_date = daily_df.index[i]
        _earn_flag = earnings_likelihood(
            gap_pct_raw, rel_vol_val,
            today=trade_date.date() if hasattr(trade_date, 'date') else None,
        )

        feat = build_breakout_features_for_day(
            daily_df, i,
            _precomputed_gap_percentile=gap_percentile,
            earnings_flag=_earn_flag,
            # news_sentiment and fii_flow_score are 0 during training
            # (historical sentiment data not available — model learns
            # to use them as bonus signals when present at prediction time)
        )
        if feat is None:
            continue

        label = compute_breakout_label(daily_df, i)
        feature_vector = np.array(
            [feat[col] for col in BREAKOUT_FEATURE_COLUMNS], dtype=np.float32
        )

        if not np.all(np.isfinite(feature_vector)):
            continue

        date_str = str(daily_df.index[i].date())
        samples.append((date_str, feature_vector, label))

    return samples


def label_to_expected_move(score: float) -> str:
    """Convert ranker score to a human-readable expected move category."""
    # Score from the ranker is shifted by +2 from the raw label
    label = score - 2.0
    if label >= 3.0:
        return "+3"
    elif label >= 2.0:
        return "+2"
    elif label >= 1.0:
        return "+1"
    elif label >= 0.0:
        return "0"
    elif label >= -1.0:
        return "-1"
    else:
        return "-2"


# ─── Legacy compatibility ─────────────────────────────────────────────────────
# These keep predictor.py's update_model and any other callers working.

FEATURE_COLUMNS = BREAKOUT_FEATURE_COLUMNS


def build_ml_features_for_day(
    daily_df: pd.DataFrame,
    day_idx: int,
    sentiment_score: float = 0.0,
    macro_score: float = 0.0,
    sector_score: float = 0.0,
) -> dict | None:
    """Legacy wrapper — redirects to build_breakout_features_for_day."""
    return build_breakout_features_for_day(daily_df, day_idx, macro_score, sector_score)


def build_training_data(
    daily_df: pd.DataFrame,
    sentiment_score: float = 0.0,
    macro_score: float = 0.0,
    sector_score: float = 0.0,
    target_horizon: int = 1,
    boom_threshold: float = 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Legacy wrapper for update_model compatibility.

    Returns (X, y) where y is float breakout labels (not binary).
    """
    samples = build_breakout_training_data(daily_df)
    if not samples:
        n = len(BREAKOUT_FEATURE_COLUMNS)
        return np.empty((0, n), dtype=np.float32), np.empty(0, dtype=np.float32)
    _, X_list, y_list = zip(*samples)
    return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.float32)
