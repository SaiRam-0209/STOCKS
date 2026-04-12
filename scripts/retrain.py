"""Standalone retraining script for GitHub Actions (or local use).

Usage:
    python scripts/retrain.py              # full 12-month retrain
    python scripts/retrain.py --full       # full history retrain

Exit codes: 0 = success, 1 = failure
"""

import sys
import os
import argparse
from datetime import datetime

# Ensure project package is importable when run from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from project.data.symbols_fetcher import get_all_nse_stocks
from project.ml.predictor import train_model, update_model


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true",
                        help="Full history retrain instead of 12-month rolling window")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  BreakoutRanker Retrain — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Mode: {'Full history' if args.full else '12-month rolling window'}")
    print(f"{'='*60}\n")

    print("  Fetching NSE stock universe...")
    symbols = get_all_nse_stocks()
    if not symbols:
        print("  [ERROR] Could not fetch NSE symbols. Aborting.")
        sys.exit(1)
    print(f"  Universe: {len(symbols)} NSE stocks\n")

    def progress(phase, pct, message):
        bar_len = 30
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"  [{bar}] {pct*100:5.1f}%  {message}", flush=True)

    universe = "All NSE"

    # If no saved model exists yet → always do full history first
    from project.ml.model import BreakoutRanker, MODEL_DIR
    import os
    model_path = os.path.join(MODEL_DIR, "breakout_ranker_all_nse.joblib")
    first_run = not os.path.exists(model_path)

    if args.full or first_run:
        if first_run:
            print("  No existing model found — running FULL history training...")
        model, metrics = train_model(
            symbols, universe=universe, progress_callback=progress
        )
    else:
        # Model exists → 12-month rolling update (fast nightly)
        model, metrics = update_model(
            symbols, universe=universe, progress_callback=progress
        )

    if "error" in metrics:
        print(f"\n  [ERROR] Training failed: {metrics['error']}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  TRAINING COMPLETE")
    print(f"{'='*60}")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"  trained_until: {model.trained_until}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        import traceback
        print("\n[FATAL ERROR]")
        traceback.print_exc()
        sys.exit(1)
