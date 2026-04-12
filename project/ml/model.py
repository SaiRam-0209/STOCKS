"""ML models: XGBoost + MLP ensemble for boom prediction."""

import numpy as np
import joblib
import os
from datetime import date
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import roc_auc_score
from xgboost import XGBClassifier

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


class BoomPredictor:
    """Ensemble model combining XGBoost + MLP for stock boom prediction."""

    def __init__(self):
        self.xgb = XGBClassifier(
            n_estimators=200,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            reg_alpha=0.1,
            reg_lambda=1.0,
            eval_metric="logloss",
            random_state=42,
        )
        self.mlp = MLPClassifier(
            hidden_layer_sizes=(64, 32, 16),
            activation="relu",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self.is_trained = False
        self.xgb_weight = 0.6  # XGBoost gets more weight (better on tabular)
        self.mlp_weight = 0.4
        self.trained_until: date | None = None  # Last date of training data

    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Train both models and return evaluation metrics.

        Uses TimeSeriesSplit to avoid look-ahead bias.
        """
        if len(X) < 50:
            return {"error": "Not enough training data (need >= 50 samples)"}

        # Clean NaN/inf values — replace with 0
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Handle class imbalance
        n_positive = y.sum()
        n_negative = len(y) - n_positive
        if n_positive == 0 or n_negative == 0:
            return {"error": "Only one class present in labels"}

        scale_pos_weight = n_negative / n_positive
        self.xgb.set_params(scale_pos_weight=scale_pos_weight)

        # Scale features for MLP
        X_scaled = self.scaler.fit_transform(X)

        # Time-series aware cross-validation
        tscv = TimeSeriesSplit(n_splits=3)
        cv_scores = []

        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            X_train_s, X_val_s = X_scaled[train_idx], X_scaled[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            if y_train.sum() == 0 or y_val.sum() == 0:
                continue

            self.xgb.fit(X_train, y_train)
            self.mlp.fit(X_train_s, y_train)

            xgb_proba = self.xgb.predict_proba(X_val)[:, 1]
            mlp_proba = self.mlp.predict_proba(X_val_s)[:, 1]
            ensemble_proba = (xgb_proba * self.xgb_weight +
                              mlp_proba * self.mlp_weight)

            try:
                auc = roc_auc_score(y_val, ensemble_proba)
                cv_scores.append(auc)
            except ValueError:
                pass

        # Final training on all data
        self.xgb.fit(X, y)
        self.mlp.fit(X_scaled, y)
        self.is_trained = True
        self.trained_until = date.today()

        # Feature importance from XGBoost
        importances = self.xgb.feature_importances_

        return {
            "cv_auc_scores": [round(s, 4) for s in cv_scores],
            "mean_auc": round(np.mean(cv_scores), 4) if cv_scores else 0.0,
            "n_samples": len(X),
            "n_positive": int(n_positive),
            "n_negative": int(n_negative),
            "positive_ratio": round(n_positive / len(y) * 100, 1),
            "feature_importances": importances.tolist(),
        }

    def update(self, X: np.ndarray, y: np.ndarray) -> dict:
        """Incrementally update the model on new data without full retrain.

        XGBoost: continues boosting from existing trees (xgb_model param).
        MLP: continues gradient descent from existing weights (warm_start).
        """
        if not self.is_trained:
            return self.train(X, y)

        if len(X) < 10:
            return {"error": "Not enough new data (need >= 10 samples)"}

        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        n_positive = y.sum()
        n_negative = len(y) - n_positive
        if n_positive == 0 or n_negative == 0:
            return {"error": "Only one class present in new data"}

        # XGBoost: continue boosting with 50 more rounds on new data
        self.xgb.set_params(
            n_estimators=self.xgb.n_estimators + 50,
            scale_pos_weight=n_negative / n_positive,
        )
        self.xgb.fit(X, y, xgb_model=self.xgb.get_booster())

        # MLP: warm-start continues from existing weights
        self.mlp.set_params(warm_start=True, max_iter=100)
        X_scaled = self.scaler.transform(X)
        self.mlp.fit(X_scaled, y)

        self.trained_until = date.today()

        return {
            "update_samples": len(X),
            "update_positive": int(n_positive),
            "update_negative": int(n_negative),
            "trained_until": str(self.trained_until),
        }

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict boom probability for each sample.

        Returns:
            Array of probabilities (0 to 1).
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")

        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        X_scaled = self.scaler.transform(X)

        xgb_proba = self.xgb.predict_proba(X)[:, 1]
        mlp_proba = self.mlp.predict_proba(X_scaled)[:, 1]

        return xgb_proba * self.xgb_weight + mlp_proba * self.mlp_weight

    def predict_single(self, features: np.ndarray) -> float:
        """Predict boom probability for a single stock.

        Args:
            features: 1D array of feature values.

        Returns:
            Probability (0 to 1).
        """
        X = features.reshape(1, -1)
        return float(self.predict_proba(X)[0])

    def save(self, path: str | None = None, universe: str | None = None):
        """Save trained model to disk using joblib (safe serialization).

        Args:
            path: Override file path.
            universe: Universe name (e.g. "Smallcap 250") — used for per-universe model files.
        """
        if path is None:
            os.makedirs(MODEL_DIR, exist_ok=True)
            filename = f"boom_{universe.lower().replace(' ', '_')}.joblib" if universe else "boom_predictor.joblib"
            path = os.path.join(MODEL_DIR, filename)
        joblib.dump({
            "xgb": self.xgb,
            "mlp": self.mlp,
            "scaler": self.scaler,
            "xgb_weight": self.xgb_weight,
            "mlp_weight": self.mlp_weight,
            "trained_until": self.trained_until,
        }, path)
        print(f"  Model saved to {path}")

    def load(self, path: str | None = None, universe: str | None = None) -> bool:
        """Load trained model from disk.

        Args:
            path: Override file path.
            universe: Universe name to load the matching model.
        """
        if path is None:
            filename = f"boom_{universe.lower().replace(' ', '_')}.joblib" if universe else "boom_predictor.joblib"
            path = os.path.join(MODEL_DIR, filename)
        if not os.path.exists(path):
            return False
        data = joblib.load(path)
        self.xgb = data["xgb"]
        self.mlp = data["mlp"]
        self.scaler = data["scaler"]
        self.xgb_weight = data["xgb_weight"]
        self.mlp_weight = data["mlp_weight"]
        self.trained_until = data.get("trained_until")
        self.is_trained = True
        return True
