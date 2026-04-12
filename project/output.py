"""Output formatting for scan results."""

import csv
import os
from datetime import datetime


def print_results(candidates: list[dict]) -> None:
    """Print structured scan results to console."""
    if not candidates:
        print("\n  No candidates found matching all primary filters.")
        return

    print(f"\n{'='*60}")
    print(f"  INTRADAY SCAN RESULTS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Top {len(candidates)} candidates")
    print(f"{'='*60}")

    for i, c in enumerate(candidates, 1):
        print(f"\n  #{i}  {c['symbol']}")
        print(f"  {'─'*40}")
        print(f"  Score:     {c['score']} / 9")
        print(f"  Direction: {c['direction']}")
        print(f"  Entry:     ₹{c['entry']}")
        print(f"  Stoploss:  ₹{c['stoploss']}")
        print(f"  Target:    ₹{c['target']}")
        print(f"  Risk:      ₹{c['risk']}  →  Reward: ₹{c['reward']}")
        print(f"  Gap:       {c['gap_pct']}%")
        print(f"  Rel Vol:   {c['rel_vol']}x")
        print(f"  VWAP:      ₹{c['vwap']}")
        print(f"  EMA 9/20:  {c['ema_9']} / {c['ema_20']}  ({'Bullish' if c['ema_bullish'] else 'Bearish'})")
        if c.get("rsi") is not None:
            print(f"  RSI:       {c['rsi']}")
        print(f"  Reason:    {c['reason']}")

    print(f"\n{'='*60}\n")


def save_to_csv(candidates: list[dict], output_dir: str = "output") -> str:
    """Save scan results to a timestamped CSV file.

    Returns:
        Path to the saved CSV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filepath = os.path.join(output_dir, f"scan_{timestamp}.csv")

    if not candidates:
        return filepath

    fields = [
        "symbol", "score", "direction", "entry", "stoploss", "target",
        "risk", "reward", "gap_pct", "rel_vol", "vwap", "ema_9", "ema_20",
        "ema_bullish", "rsi", "reason",
    ]

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(candidates)

    print(f"  Results saved to {filepath}")
    return filepath
