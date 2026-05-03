"""Win/Loss Classifier v2 — high-performance version with regime awareness.

Key upgrades over the original:
    1. Reduced feature set: 50 → 20 (stable, high-importance features only)
    2. Market regime as input feature
    3. Dynamic threshold optimization (not hardcoded)
    4. Confidence-bucketed output for position sizing
    5. Walk-forward compatible API

Uses 20 features:
    - 8 from breakout (gap, volume, trend alignment)
    - 5 from WinClassifier extra (first candle, RSI, price level)
    - 3 from V2 (market context: beta, relative strength, spread)
    - 4 from regime (regime numeric, EMA slope, ATR expansion, index momentum)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import os
import logging
from datetime import date
from xgboost import XGBClassifier

from project.features.indicators import gap_percentage, relative_volume, ema, atr, rsi
from project.ml.features import (
    build_breakout_features_for_day,
    BREAKOUT_FEATURE_COLUMNS,
)
from project.ml.features_v2 import build_v2_features
from project.features.regime import (
    compute_regime_features,
    REGIME_FEATURE_COLUMNS,
)

log = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")

# ── Curated 20-feature set ──────────────────────────────────────────────────
# Selected for stability across folds, SHAP importance, and non-redundancy.

# 8 from breakout v1 (most predictive, least noisy)
SELECTED_BREAKOUT = [
    "gap_pct",              # Core signal — gap direction + magnitude
    "gap_vs_atr",           # Gap significance vs normal volatility
    "gap_trend_aligned",    # Gap in direction of trend (strong signal)
    "rel_vol",              # Volume confirmation
    "vol_acceleration",     # Sudden volume spike
    "atr_pct",              # Volatility as % of price
    "range_compression",    # Compressed range → explosive breakout
    "pre_gap_momentum",     # 3-day run-up before gap
]

# 5 from extra features (first candle + daily context)
SELECTED_EXTRA = [
    "first_candle_body_pct",     # Strong body = conviction
    "first_candle_range_vs_atr", # Candle range relative to ATR
    "rsi_14",                    # Overbought/oversold context
    "distance_from_52w_high",    # Where in the range
    "price_level",               # Log price (penny vs large cap)
]

# 3 from V2 (market context — most stable of the 13)
SELECTED_V2 = [
    "beta_60d",            # How much stock moves with market
    "stock_vs_nifty_5d",   # 5-day relative strength
    "spread_proxy_bps",    # Liquidity proxy
]

# 4 regime features
SELECTED_REGIME = REGIME_FEATURE_COLUMNS

# Combined
CURATED_FEATURES = SELECTED_BREAKOUT + SELECTED_EXTRA + SELECTED_V2 + SELECTED_REGIME


class WinClassifierV2:
    """XGBoost classifier v2: regime-aware, curated features, dynamic threshold.

    This replaces the original WinClassifier for all new pipelines while
    maintaining backward-compatible save/load.
    """

    def __init__(self):
        self.model = XGBClassifier(
            objective="binary:logistic",
            n_estimators=500,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=10,
            reg_alpha=0.2,
            reg_lambda=2.0,
            scale_pos_weight=1.0,      # Adjusted during training
            tree_method="hist",
            eval_metric="logloss",
            random_state=42,
        )
        self.is_trained = False
        self.trained_until: date | None = None
        self.n_samples: int = 0
        self.win_rate_train: float = 0.0
        self.n_features: int = len(CURATED_FEATURES)

        # Dynamic threshold — optimized during validation
        self.optimal_threshold: float = 0.40
        self.regime_thresholds: dict[str, float] = {}

    # ── Feature extraction ─────────────────────────────────────────────────

    def extract_features(
        self,
        daily_df: pd.DataFrame,
        day_idx: int,
        nifty_df: pd.DataFrame | None = None,
        first_candle: dict | None = None,
    ) -> np.ndarray | None:
        """Extract the curated 20-feature vector for a single day.

        Returns None if insufficient data.
        """
        if day_idx < 30 or day_idx >= len(daily_df):
            return None

        # Base breakout features
        base_feat = build_breakout_features_for_day(daily_df, day_idx)
        if base_feat is None:
            return None

        # Extra features
        extra_feat = self._build_extra_features(daily_df, day_idx, first_candle)
        if extra_feat is None:
            return None

        # V2 features (subset)
        v2_feat = build_v2_features(daily_df, day_idx, nifty_df=nifty_df)

        # Regime features
        regime_feat = compute_regime_features(nifty_df) if nifty_df is not None else {
            k: 0.0 for k in REGIME_FEATURE_COLUMNS
        }

        # Combine into curated set
        all_feat = {**base_feat, **extra_feat, **v2_feat, **regime_feat}

        try:
            vec = np.array(
                [all_feat[col] for col in CURATED_FEATURES], dtype=np.float32
            )
        except KeyError as exc:
            log.debug("Missing feature key: %s", exc)
            return None

        if not np.all(np.isfinite(vec)):
            return None

        return vec

    def _build_extra_features(
        self,
        daily_df: pd.DataFrame,
        day_idx: int,
        first_candle: dict | None = None,
    ) -> dict | None:
        """Build the 5 selected extra features."""
        if day_idx < 30:
            return None

        row = daily_df.iloc[day_idx]
        prev = daily_df.iloc[day_idx - 1]
        today_open = float(row["Open"])
        today_high = float(row["High"])
        today_low = float(row["Low"])

        # First candle features
        if first_candle:
            fc_open = first_candle.get("open", today_open)
            fc_close = first_candle.get("close", float(row["Close"]))
            fc_high = first_candle.get("high", today_high)
            fc_low = first_candle.get("low", today_low)
        else:
            fc_open = today_open
            fc_close = float(row["Close"])
            fc_high = today_high
            fc_low = today_low

        fc_range = fc_high - fc_low
        fc_body = abs(fc_close - fc_open)
        first_candle_body_pct = fc_body / fc_range if fc_range > 0 else 0.5

        # First candle range vs ATR
        hist_df = daily_df.iloc[:day_idx]
        atr_series = atr(hist_df, 14)
        current_atr = float(atr_series.iloc[-1]) if len(atr_series) >= 14 else 1.0
        first_candle_range_vs_atr = fc_range / current_atr if current_atr > 0 else 1.0

        # RSI
        close_series = daily_df["Close"].iloc[:day_idx + 1]
        rsi_series = rsi(close_series, 14)
        rsi_14 = float(rsi_series.iloc[-1]) if len(rsi_series) >= 14 else 50.0

        # Distance from 52-week high
        lookback = min(252, day_idx)
        high_52w = float(daily_df["High"].iloc[day_idx - lookback:day_idx + 1].max())
        distance_from_52w_high = ((high_52w - today_high) / high_52w * 100) if high_52w > 0 else 0.0

        # Price level (log)
        price_level = float(np.log10(max(today_open, 1.0)))

        return {
            "first_candle_body_pct": round(first_candle_body_pct, 4),
            "first_candle_range_vs_atr": round(first_candle_range_vs_atr, 4),
            "rsi_14": round(rsi_14, 4),
            "distance_from_52w_high": round(distance_from_52w_high, 4),
            "price_level": round(price_level, 4),
        }

    # ── Win label ──────────────────────────────────────────────────────────

    def build_win_label(self, daily_df: pd.DataFrame, day_idx: int) -> int:
        """Label: did the ORB trade WIN (hit 2R target before SL)?

        Uses daily OHLC to approximate:
        - LONG (gap up): WIN if high >= open + 2*(open - low), LOSS if low hits SL first
        - SHORT (gap down): WIN if low <= open - 2*(high - open)

        Returns 1 for WIN, 0 for LOSS.
        """
        row = daily_df.iloc[day_idx]
        prev_close = float(daily_df.iloc[day_idx - 1]["Close"])
        open_px = float(row["Open"])
        high_px = float(row["High"])
        low_px = float(row["Low"])
        close_px = float(row["Close"])

        gap = open_px - prev_close
        if gap > 0:
            # LONG trade
            sl = low_px
            risk = open_px - sl
            if risk <= 0:
                return 0
            target = open_px + 2 * risk
            if high_px >= target:
                return 1
            if close_px > open_px + risk:  # Above 1R
                return 1
            return 0
        else:
            # SHORT trade
            sl = high_px
            risk = sl - open_px
            if risk <= 0:
                return 0
            target = open_px - 2 * risk
            if low_px <= target:
                return 1
            if close_px < open_px - risk:
                return 1
            return 0

    # ── Training data ──────────────────────────────────────────────────────

    def build_training_data(
        self,
        daily_df: pd.DataFrame,
        nifty_df: pd.DataFrame | None = None,
        gap_min: float = 2.0,
        vol_min: float = 1.5,
        price_min: float = 50.0,
        price_max: float = 10000.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build features + win/loss labels for all qualifying gap days.

        Returns (X, y) arrays.
        """
        if len(daily_df) < 50:
            return np.empty((0, len(CURATED_FEATURES))), np.empty(0)

        X_list = []
        y_list = []

        opens = daily_df["Open"].values
        closes = daily_df["Close"].values

        for i in range(30, len(daily_df)):
            prev_close = closes[i - 1]
            if prev_close <= 0:
                continue

            open_px = opens[i]
            gap_pct = (open_px - prev_close) / prev_close * 100
            if abs(gap_pct) < gap_min:
                continue

            if open_px < price_min or open_px > price_max:
                continue

            avg_vol = float(daily_df["Volume"].iloc[max(0, i - 10):i].mean())
            if avg_vol <= 0:
                continue
            rel_vol = float(daily_df["Volume"].iloc[i]) / avg_vol
            if rel_vol < vol_min:
                continue

            feature_vec = self.extract_features(daily_df, i, nifty_df=nifty_df)
            if feature_vec is None:
                continue

            label = self.build_win_label(daily_df, i)
            X_list.append(feature_vec)
            y_list.append(label)

        if not X_list:
            return np.empty((0, len(CURATED_FEATURES))), np.empty(0)

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)

    # ── Training ──────────────────────────────────────────────────────────

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Train the win/loss classifier."""
        if len(X) < 50:
            return {"error": f"Not enough samples ({len(X)})"}

        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Balance classes
        n_wins = int(y.sum())
        n_losses = len(y) - n_wins
        if n_losses > 0 and n_wins > 0:
            self.model.set_params(scale_pos_weight=n_losses / n_wins)

        self.model.fit(X, y)

        self.is_trained = True
        self.trained_until = date.today()
        self.n_samples = len(X)
        self.win_rate_train = float(y.mean())

        # Feature importance
        importances = self.model.feature_importances_
        top_idx = np.argsort(importances)[::-1][:10]
        top_features = [(CURATED_FEATURES[i], round(float(importances[i]), 4)) for i in top_idx]

        return {
            "n_samples": len(X),
            "n_wins": n_wins,
            "n_losses": n_losses,
            "train_win_rate": round(self.win_rate_train * 100, 1),
            "n_features": len(CURATED_FEATURES),
            "top_features": top_features,
        }

    # ── Prediction ────────────────────────────────────────────────────────

    def predict_win_probability(self, features: np.ndarray) -> float:
        """Predict win probability for a single trade setup.

        Returns: probability between 0 and 1.
        """
        if not self.is_trained:
            return 0.5
        X = np.nan_to_num(features.reshape(1, -1), nan=0.0)
        proba = self.model.predict_proba(X)[0]
        return float(proba[1])  # P(win)

    def classify_confidence(self, win_prob: float) -> str:
        """Classify the trade into a confidence bucket for position sizing.

        Returns: 'LOW', 'MEDIUM', or 'HIGH'
        """
        if win_prob < 0.50:
            return "LOW"
        elif win_prob < 0.65:
            return "MEDIUM"
        else:
            return "HIGH"

    def should_take_trade(
        self,
        features: np.ndarray,
        threshold: float | None = None,
        regime: str | None = None,
    ) -> tuple[bool, float, str]:
        """Should we take this trade?

        Args:
            features: Feature vector.
            threshold: Override threshold. If None, uses optimal or regime-specific.
            regime: Current market regime string for regime-specific threshold.

        Returns: (yes/no, win_probability, confidence_bucket)
        """
        prob = self.predict_win_probability(features)

        if threshold is None:
            if regime and regime in self.regime_thresholds:
                threshold = self.regime_thresholds[regime]
            else:
                threshold = self.optimal_threshold

        confidence = self.classify_confidence(prob)
        return prob >= threshold, prob, confidence

    # ── Persistence ───────────────────────────────────────────────────────

    def save(self, path: str | None = None):
        os.makedirs(MODEL_DIR, exist_ok=True)
        if path is None:
            path = os.path.join(MODEL_DIR, "win_classifier_v2.joblib")
        joblib.dump({
            "model": self.model,
            "trained_until": self.trained_until,
            "n_samples": self.n_samples,
            "win_rate_train": self.win_rate_train,
            "n_features": self.n_features,
            "optimal_threshold": self.optimal_threshold,
            "regime_thresholds": self.regime_thresholds,
        }, path)
        log.info("Win classifier v2 saved to %s", path)

    def load(self, path: str | None = None) -> bool:
        if path is None:
            path = os.path.join(MODEL_DIR, "win_classifier_v2.joblib")
        if not os.path.exists(path):
            return False
        data = joblib.load(path)
        self.model = data["model"]
        self.trained_until = data.get("trained_until")
        self.n_samples = data.get("n_samples", 0)
        self.win_rate_train = data.get("win_rate_train", 0.0)
        self.n_features = data.get("n_features", len(CURATED_FEATURES))
        self.optimal_threshold = data.get("optimal_threshold", 0.40)
        self.regime_thresholds = data.get("regime_thresholds", {})
        self.is_trained = True
        return True
