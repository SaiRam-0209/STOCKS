"""Profit-maximizing ranker — the missing piece between P(win) and expected profit.

The WinClassifier predicts probability a trade wins (hits 2R target).
But ranking by P(win) alone is NOT profit-maximizing, because:

    Stock A: P(win)=60%, R:R=2:1 -> E[R] = 0.6*2 - 0.4*1 = +0.80R
    Stock B: P(win)=70%, R:R=1.5:1 -> E[R] = 0.7*1.5 - 0.3*1 = +0.75R

Stock A wins despite lower P(win), because its risk:reward is better.

This module produces a profit-oriented score. Below is the data you have
per candidate at scan time — use it to build an expected-profit score.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Candidate:
    ticker: str
    entry: float          # Planned entry price (today's open)
    stop_loss: float      # Planned SL price
    target: float         # Planned 2R target price
    p_win: float          # From WinClassifier (0.0 - 1.0)
    gap_pct: float        # Overnight gap %
    rel_vol: float        # Relative volume multiple
    liquidity_cr: float   # 20d avg daily value in crores (NEW from V2)
    spread_bps: float     # (high-low)/close in bps proxy     (NEW from V2)
    rs_vs_nifty_5d: float # 5d relative strength vs Nifty pp  (NEW from V2)


def expected_profit_score(c: Candidate) -> float:
    """Return a score used to rank candidates for maximum expected profit.

    DESIGN DECISION — implement this function body (5-10 lines).

    Things you have to trade off:
    --------------------------------
      1. Base expected return:
           reward = c.target - c.entry
           risk   = c.entry  - c.stop_loss    (always positive for longs)
           E[R]   = c.p_win * reward - (1 - c.p_win) * risk

      2. Liquidity penalty:
           Thin stocks (c.liquidity_cr < 10) have large slippage -> real
           fill is worse than quoted. Penalize or hard-reject.

      3. Spread penalty:
           Large spread_bps eats profit on small moves. Subtract cost.

      4. Regime kicker:
           If rs_vs_nifty_5d > 0, the stock is already outperforming;
           on trend-up days that's a good sign, on reversal days it's
           crowded. Your call whether to boost/penalize.

      5. Conviction gate:
           Below a p_win threshold (e.g. 0.55) the edge is too thin —
           either hard-filter or linearly damp the score.

    Two reasonable shapes:

      (a) Pure-EV:   score = E[R_money] - liquidity_penalty - spread_cost
      (b) Risk-adj:  score = E[R_money] / risk  (Kelly-ish), filtered on liquidity

    Pick (a) if you're optimizing total rupees. Pick (b) if you want the
    best risk-adjusted trade regardless of position size. The Day-1 data
    (MTARTECH at 48% of capital delivering the win) suggests you may
    want (b) so position sizing isn't dominated by high-priced stocks.

    Fill in below. Return a higher score for more attractive trades.
    """
    # TODO: implement expected-profit scoring here
    reward = c.target - c.entry
    risk = c.entry - c.stop_loss
    raise NotImplementedError("Implement the profit-ranker body — see docstring")


def rank_candidates(candidates: list[Candidate], top_n: int = 4) -> list[Candidate]:
    """Rank by expected-profit score; keep top N."""
    scored = sorted(candidates, key=expected_profit_score, reverse=True)
    return scored[:top_n]
