"""BreakoutRanker: XGBoost Learning-to-Rank model for ORB trade quality.

Replaces the XGBoost + MLP binary classifier with a ranking model that
answers "of today's gap stocks, which will have the strongest breakout?"
rather than just "will this stock boom?"

The ranker uses rank:ndcg — within each group (trading day), it learns to
order stocks by expected breakout strength.
"""

from __future__ import annotations

import numpy as np
import joblib
import os
from datetime import date
from xgboost import XGBRanker

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


class BreakoutRanker:
    """XGBoost Learning-to-Rank model for ranking gap breakout trades.

    Training groups = trading dates (stocks on the same day compete).
    Label = actual move in multiples of the gap size (higher = better).
    Sample weights emphasize +2/+3 trades so the model focuses on
    the rare high-quality setups rather than average ones.
    """

    def __init__(self):
        self.model = XGBRanker(
            objective="rank:pairwise",  # pairwise supports float labels directly
            n_estimators=400,
            max_depth=5,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.75,
            min_child_weight=5,
            reg_alpha=0.15,
            reg_lambda=1.5,
            tree_method="hist",
            nthread=-1,              # use all CPU cores
            random_state=42,
        )
        self.is_trained = False
        self.trained_until: date | None = None
        self.n_samples: int = 0
        self.n_groups: int = 0

    def train(self, X: np.ndarray, y: np.ndarray, groups: list[int]) -> dict:
        """Train the ranker on historical gap-day data.

        Args:
            X: Feature matrix (n_samples, n_features).
            y: Relevance scores — actual breakout strength labels, range [-2, 6].
            groups: Group sizes (number of gap stocks per trading day).

        Returns:
            Training metrics dict.
        """
        if len(X) < 100:
            return {"error": f"Not enough training samples ({len(X)} < 100)"}
        if sum(groups) != len(X):
            return {"error": f"Group size mismatch: sum={sum(groups)} != len(X)={len(X)}"}

        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # XGBRanker requires non-negative integer relevance labels.
        # Quantize float move labels [-2, 6] → integer grades [0, 8]:
        #   grade 0 = strong reversal, grade 4 = no move, grade 8 = 6× gap move
        y_int = np.clip(np.round(y + 2.0).astype(np.int32), 0, 8)

        # XGBRanker sample_weight must be one value PER GROUP (not per sample).
        # Weight each day by the best trade quality in that group.
        group_weights = []
        idx = 0
        for g in groups:
            best_grade = int(y_int[idx:idx + g].max())
            w = 4.0 if best_grade >= 6 else (2.0 if best_grade >= 5 else 1.0)
            group_weights.append(w)
            idx += g
        group_weights = np.array(group_weights, dtype=np.float32)

        self.model.fit(X, y_int, group=groups, sample_weight=group_weights)

        self.is_trained = True
        self.trained_until = date.today()
        self.n_samples = len(X)
        self.n_groups = len(groups)

        return {
            "n_samples": len(X),
            "n_groups": len(groups),
            "avg_group_size": round(len(X) / len(groups), 1),
            "strong_labels": int((y >= 2.0).sum()),
            "decent_labels": int(((y >= 1.0) & (y < 2.0)).sum()),
            "weak_labels": int((y < 1.0).sum()),
            "strong_pct": round((y >= 2.0).mean() * 100, 1),
        }

    def score(self, X: np.ndarray) -> np.ndarray:
        """Compute ranking scores — higher means stronger expected breakout."""
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        return self.model.predict(X)

    def score_single(self, features: np.ndarray) -> float:
        """Score a single feature vector."""
        return float(self.score(features.reshape(1, -1))[0])

    def save(self, path: str | None = None, universe: str | None = None):
        os.makedirs(MODEL_DIR, exist_ok=True)
        if path is None:
            label = (universe or "all_nse").lower().replace(" ", "_")
            path = os.path.join(MODEL_DIR, f"breakout_ranker_{label}.joblib")
        joblib.dump({
            "model": self.model,
            "trained_until": self.trained_until,
            "n_samples": self.n_samples,
            "n_groups": self.n_groups,
        }, path)
        print(f"  Ranker saved to {path}")

    def load(self, path: str | None = None, universe: str | None = None) -> bool:
        if path is None:
            label = (universe or "all_nse").lower().replace(" ", "_")
            path = os.path.join(MODEL_DIR, f"breakout_ranker_{label}.joblib")
        if not os.path.exists(path):
            return False
        data = joblib.load(path)
        self.model = data["model"]
        self.trained_until = data.get("trained_until")
        self.n_samples = data.get("n_samples", 0)
        self.n_groups = data.get("n_groups", 0)
        self.is_trained = True
        return True


# Alias so existing UI import `from project.ml.model import BoomPredictor` keeps working
BoomPredictor = BreakoutRanker
