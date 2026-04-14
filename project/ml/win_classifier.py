"""Win/Loss Classifier — predicts probability that an ORB trade will be profitable.

Unlike the BreakoutRanker (which ranks stocks relative to each other),
this model predicts an absolute win probability for each trade setup.
Only trades with >55% predicted win probability should be taken.

Uses 30 features including intraday-derived signals computed from
the first 15-min candle and daily context.
"""

import numpy as np
import pandas as pd
import joblib
import os
from datetime import date
from xgboost import XGBClassifier

from project.features.indicators import gap_percentage, relative_volume, ema, atr, rsi
from project.ml.features import (
    build_breakout_features_for_day,
    BREAKOUT_FEATURE_COLUMNS,
)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")

# 10 additional features on top of the 20 breakout features
EXTRA_FEATURES = [
    "first_candle_body_pct",     # First 15-min candle body / range (strong = high)
    "first_candle_direction",    # 1 = green candle, 0 = red
    "first_candle_range_vs_atr", # First candle range / daily ATR
    "rsi_14",                    # RSI on daily close
    "day_of_week",               # 0=Mon, 4=Fri (Mon/Tue better for breakouts)
    "distance_from_52w_high",    # % below 52-week high
    "prev_day_return",           # Previous day's return %
    "avg_gap_fill_rate",         # How often past gaps filled (0-1)
    "consecutive_gap_days",      # How many recent gap days (fatigue signal)
    "price_level",               # Log of stock price (penny vs large cap)
]

ALL_FEATURES = BREAKOUT_FEATURE_COLUMNS + EXTRA_FEATURES
MIN_WIN_PROBABILITY = 0.55  # Minimum predicted probability to take a trade


class WinClassifier:
    """XGBoost classifier: predicts P(trade wins) for ORB setups."""

    def __init__(self):
        self.model = XGBClassifier(
            objective="binary:logistic",
            n_estimators=500,
            max_depth=4,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.7,
            min_child_weight=10,
            reg_alpha=0.2,
            reg_lambda=2.0,
            scale_pos_weight=1.0,  # Will be adjusted based on class balance
            tree_method="hist",
            eval_metric="logloss",
            random_state=42,
        )
        self.is_trained = False
        self.trained_until: date | None = None
        self.n_samples: int = 0
        self.win_rate_train: float = 0.0
        self.n_features: int = len(ALL_FEATURES)

    def build_extra_features(
        self,
        daily_df: pd.DataFrame,
        day_idx: int,
        first_candle: dict | None = None,
    ) -> dict | None:
        """Build the 10 extra features not in the base breakout set."""
        if day_idx < 260 or day_idx >= len(daily_df):
            # Need 252 days for 52-week high
            if day_idx < 30:
                return None

        row = daily_df.iloc[day_idx]
        prev = daily_df.iloc[day_idx - 1]
        prev_close = float(prev["Close"])
        today_open = float(row["Open"])
        today_high = float(row["High"])
        today_low = float(row["Low"])

        # First candle features (use daily candle as proxy in training)
        if first_candle:
            fc_open = first_candle.get("open", today_open)
            fc_close = first_candle.get("close", float(row["Close"]))
            fc_high = first_candle.get("high", today_high)
            fc_low = first_candle.get("low", today_low)
        else:
            # Use first part of daily candle as proxy
            fc_open = today_open
            fc_close = float(row["Close"])
            fc_high = today_high
            fc_low = today_low

        fc_range = fc_high - fc_low
        fc_body = abs(fc_close - fc_open)

        first_candle_body_pct = fc_body / fc_range if fc_range > 0 else 0.5
        first_candle_direction = 1.0 if fc_close >= fc_open else 0.0

        # First candle range vs ATR
        hist_df = daily_df.iloc[:day_idx]
        atr_series = atr(hist_df, 14)
        current_atr = float(atr_series.iloc[-1]) if len(atr_series) >= 14 else 1.0
        first_candle_range_vs_atr = fc_range / current_atr if current_atr > 0 else 1.0

        # RSI
        close_series = daily_df["Close"].iloc[:day_idx + 1]
        rsi_series = rsi(close_series, 14)
        rsi_14 = float(rsi_series.iloc[-1]) if len(rsi_series) >= 14 else 50.0

        # Day of week
        trade_date = daily_df.index[day_idx]
        if hasattr(trade_date, 'weekday'):
            day_of_week = float(trade_date.weekday())
        else:
            day_of_week = 2.0  # Default Wednesday

        # Distance from 52-week high
        lookback = min(252, day_idx)
        high_52w = float(daily_df["High"].iloc[day_idx - lookback:day_idx + 1].max())
        distance_from_52w_high = ((high_52w - today_high) / high_52w * 100) if high_52w > 0 else 0.0

        # Previous day return
        if day_idx >= 2:
            prev_prev_close = float(daily_df.iloc[day_idx - 2]["Close"])
            prev_day_return = ((prev_close - prev_prev_close) / prev_prev_close * 100) if prev_prev_close > 0 else 0.0
        else:
            prev_day_return = 0.0

        # Average gap fill rate (last 20 gaps)
        gap_fills = 0
        gap_count = 0
        for j in range(max(1, day_idx - 50), day_idx):
            pc = float(daily_df.iloc[j - 1]["Close"])
            if pc <= 0:
                continue
            g = (float(daily_df.iloc[j]["Open"]) - pc) / pc * 100
            if abs(g) >= 2.0:
                gap_count += 1
                # Gap filled = price returned to prev close during the day
                if g > 0 and float(daily_df.iloc[j]["Low"]) <= pc:
                    gap_fills += 1
                elif g < 0 and float(daily_df.iloc[j]["High"]) >= pc:
                    gap_fills += 1
        avg_gap_fill_rate = gap_fills / gap_count if gap_count > 0 else 0.5

        # Consecutive gap days
        consecutive_gap_days = 0.0
        for j in range(day_idx - 1, max(0, day_idx - 10), -1):
            pc = float(daily_df.iloc[j - 1]["Close"]) if j >= 1 else 0
            if pc <= 0:
                break
            g = abs((float(daily_df.iloc[j]["Open"]) - pc) / pc * 100)
            if g >= 2.0:
                consecutive_gap_days += 1
            else:
                break

        # Price level (log)
        price_level = float(np.log10(max(today_open, 1.0)))

        return {
            "first_candle_body_pct": round(first_candle_body_pct, 4),
            "first_candle_direction": first_candle_direction,
            "first_candle_range_vs_atr": round(first_candle_range_vs_atr, 4),
            "rsi_14": round(rsi_14, 4),
            "day_of_week": day_of_week,
            "distance_from_52w_high": round(distance_from_52w_high, 4),
            "prev_day_return": round(prev_day_return, 4),
            "avg_gap_fill_rate": round(avg_gap_fill_rate, 4),
            "consecutive_gap_days": consecutive_gap_days,
            "price_level": round(price_level, 4),
        }

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
            sl = low_px  # Worst case: SL at day low
            risk = open_px - sl
            if risk <= 0:
                return 0
            target = open_px + 2 * risk
            # Approximate: if the day high reached the target, count as WIN
            # This is conservative — in intraday, target might hit before SL
            if high_px >= target:
                return 1
            # If close is profitable (even if target not hit), partial win
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

    def build_training_data(
        self,
        daily_df: pd.DataFrame,
        gap_min: float = 4.0,
        vol_min: float = 2.5,
        price_min: float = 50.0,
        price_max: float = 5000.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Build features + win/loss labels for all qualifying gap days."""
        if len(daily_df) < 50:
            return np.empty((0, len(ALL_FEATURES))), np.empty(0)

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

            # Price filter
            if open_px < price_min or open_px > price_max:
                continue

            # Volume filter
            avg_vol = float(daily_df["Volume"].iloc[max(0, i - 10):i].mean())
            if avg_vol <= 0:
                continue
            rel_vol = float(daily_df["Volume"].iloc[i]) / avg_vol
            if rel_vol < vol_min:
                continue

            # Base 20 features
            base_feat = build_breakout_features_for_day(daily_df, i)
            if base_feat is None:
                continue

            # Extra 10 features
            extra_feat = self.build_extra_features(daily_df, i)
            if extra_feat is None:
                continue

            # Combine
            all_feat = {**base_feat, **extra_feat}
            feature_vec = np.array(
                [all_feat[col] for col in ALL_FEATURES], dtype=np.float32
            )

            if not np.all(np.isfinite(feature_vec)):
                continue

            # Label
            label = self.build_win_label(daily_df, i)
            X_list.append(feature_vec)
            y_list.append(label)

        if not X_list:
            return np.empty((0, len(ALL_FEATURES))), np.empty(0)

        return np.array(X_list, dtype=np.float32), np.array(y_list, dtype=np.int32)

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
        top_features = [(ALL_FEATURES[i], round(float(importances[i]), 4)) for i in top_idx]

        return {
            "n_samples": len(X),
            "n_wins": n_wins,
            "n_losses": n_losses,
            "train_win_rate": round(self.win_rate_train * 100, 1),
            "top_features": top_features,
        }

    def predict_win_probability(self, features: np.ndarray) -> float:
        """Predict win probability for a single trade setup.

        Returns: probability between 0 and 1.
        """
        if not self.is_trained:
            return 0.5
        X = np.nan_to_num(features.reshape(1, -1), nan=0.0)
        proba = self.model.predict_proba(X)[0]
        return float(proba[1])  # P(win)

    def should_take_trade(self, features: np.ndarray, threshold: float = MIN_WIN_PROBABILITY) -> tuple[bool, float]:
        """Should we take this trade? Returns (yes/no, win_probability)."""
        prob = self.predict_win_probability(features)
        return prob >= threshold, prob

    def save(self, path: str | None = None):
        os.makedirs(MODEL_DIR, exist_ok=True)
        if path is None:
            path = os.path.join(MODEL_DIR, "win_classifier.joblib")
        joblib.dump({
            "model": self.model,
            "trained_until": self.trained_until,
            "n_samples": self.n_samples,
            "win_rate_train": self.win_rate_train,
            "n_features": self.n_features,
        }, path)
        print(f"  Win classifier saved to {path}")

    def load(self, path: str | None = None) -> bool:
        if path is None:
            path = os.path.join(MODEL_DIR, "win_classifier.joblib")
        if not os.path.exists(path):
            return False
        data = joblib.load(path)
        self.model = data["model"]
        self.trained_until = data.get("trained_until")
        self.n_samples = data.get("n_samples", 0)
        self.win_rate_train = data.get("win_rate_train", 0.0)
        self.n_features = data.get("n_features", len(ALL_FEATURES))
        self.is_trained = True
        return True
