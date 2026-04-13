"""Streamlit web UI — AI Stock Scanner for All / Largecap / Midcap / Smallcap."""

import sys, os
# Ensure repo root is on sys.path (needed for Streamlit Cloud)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import hmac
from datetime import date as _date

from project.data.fetcher import fetch_all_stocks, fetch_daily
from project.data.symbols import UNIVERSES
from project.features.builder import build_features
from project.strategy.filter import compute_score, build_reason
from project.strategy.signals import enrich_candidates
from project.backtest.engine import run_backtest
from project.ml.predictor import predict_boom_stocks, train_model, update_model
from project.ml.model import BreakoutRanker as _BoomPredictor

# --- Page config ---
st.set_page_config(page_title="AI Stock Scanner", page_icon="🚀", layout="wide")

# --- Authentication Gate ---
def _check_password() -> bool:
    """Block access unless the user enters the correct password.

    Password is read from:
        1. Streamlit secrets: st.secrets["APP_PASSWORD"]
        2. Environment variable: APP_PASSWORD
        3. Fallback default for local dev (change before deploying!)
    """
    try:
        correct_pw = st.secrets["APP_PASSWORD"]
    except (FileNotFoundError, KeyError):
        correct_pw = os.getenv("APP_PASSWORD", "")

    if not correct_pw:
        # No password configured — allow access (local dev)
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("🔒 AI Stock Scanner")
    st.markdown("Enter your password to access the trading dashboard.")

    password = st.text_input("Password", type="password", key="login_pw")
    if st.button("Login", type="primary", use_container_width=True):
        if hmac.compare_digest(password, correct_pw):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False


if not _check_password():
    st.stop()

st.title("🚀 AI-Powered Stock Scanner")

# --- Sidebar: Universe selector ---
st.sidebar.header("📌 Stock Universe")
universe_name = st.sidebar.radio(
    "Select universe",
    list(UNIVERSES.keys()),
    index=0,
    help="All Stocks = Largecap + Midcap + Smallcap combined",
)
universe = UNIVERSES[universe_name]
universe_symbols = universe["symbols"]
universe_rank_map = universe["rank_map"]

st.sidebar.caption(f"**{universe_name}** — {universe['count']} stocks")

# --- Sidebar: Mode ---
st.sidebar.header("⚙️ Mode")
mode = st.sidebar.radio("Select mode", [
    "🤖 AI Boom Predictor",
    "📊 Live Scan",
    "⏮️ Backtest",
    "🧠 Train Model",
    "⚡ Live Trading",
])

# --- Sidebar: Filters ---
st.sidebar.header("🔧 Filters")
top_n = st.sidebar.slider("Top N candidates", 1, 30, 15)

max_rank = universe["count"]
rank_range = st.sidebar.slider(
    f"Rank range (1 = highest weight)",
    1, max_rank, (1, max_rank),
)

stock_subset = st.sidebar.multiselect(
    "Pick specific stocks (optional)",
    universe_symbols,
    default=[],
)

if stock_subset:
    symbols = stock_subset
else:
    symbols = [s for s in universe_symbols
               if rank_range[0] <= universe_rank_map.get(s, 999) <= rank_range[1]]

st.sidebar.metric("Stocks in scan", len(symbols))

# Scanner-specific thresholds
if mode == "📊 Live Scan":
    st.sidebar.subheader("Scanner Thresholds")
    gap_thresh = st.sidebar.slider("Min Gap %", 0.5, 5.0, 2.0, 0.5)
    vol_thresh = st.sidebar.slider("Min Relative Volume", 1.0, 5.0, 1.5, 0.25)


# =====================================================
# AI BOOM PREDICTOR
# =====================================================
if mode == "🤖 AI Boom Predictor":
    st.markdown(f"""
    **Scanning {universe_name} ({len(symbols)} stocks) for high-quality gap breakout trades:**
    - 🌍 **Global Macro** — US markets, crude oil, gold, VIX, USD/INR, Asian markets
    - 📰 **News Sentiment** — Real-time RSS feeds analyzed with financial NLP
    - 📈 **BreakoutRanker** — XGBoost Learning-to-Rank on 15 breakout-quality features.
      Ranks gap stocks by *expected move strength* (+1/+2/+3×), not just win probability.
    """)

    # --- Check if model is stale ---
    _check_model = _BoomPredictor()
    _model_loaded = _check_model.load(universe=universe_name)
    if _model_loaded and _check_model.trained_until:
        _gap = (_date.today() - _check_model.trained_until).days
        if _gap > 0:
            st.warning(
                f"⚠️ Model was last trained on **{_check_model.trained_until}** "
                f"({_gap} day{'s' if _gap != 1 else ''} behind). "
                f"Click below to update it with the latest data before predicting."
            )
            if st.button(f"🔄 Update Model (+{_gap} days)", use_container_width=True):
                _prog = st.progress(0, text="Updating model...")
                def _on_update_progress(phase, progress, message):
                    _prog.progress(min(progress, 1.0), text=message)
                _, _update_metrics = update_model(
                    symbols, universe=universe_name,
                    progress_callback=_on_update_progress,
                )
                _prog.empty()
                if "error" in _update_metrics:
                    st.error(f"Update failed: {_update_metrics['error']}")
                else:
                    st.success(
                        f"✅ Model updated! Added {_update_metrics.get('update_samples', 0):,} "
                        f"new samples from {_update_metrics.get('stocks_updated', 0)} stocks."
                    )
        else:
            st.success(f"✅ Model is up to date (trained until {_check_model.trained_until})")
    elif _model_loaded and not _check_model.trained_until:
        st.info("ℹ️ Model exists but has no training date. Retrain to enable auto-update tracking.")

    if st.button(f"🚀 Find Tomorrow's Boom Stocks — {universe_name}", type="primary", use_container_width=True):
        try:
            with st.spinner(f"Running AI pipeline on {len(symbols)} {universe_name} stocks..."):
                candidates, context = predict_boom_stocks(symbols, top_n=top_n, universe=universe_name)
        except Exception as _pred_exc:
            st.error(f"Prediction pipeline error: {_pred_exc}")
            candidates, context = [], {}

        if not candidates:
            if context.get("warning"):
                st.warning(f"No predictions: {context['warning']}")
            elif context.get("error"):
                st.error(f"Pipeline error: {context['error']}")
            else:
                st.error("Failed to generate predictions. No stocks passed gap + volume filter today.")
        else:
            # --- Universe badge ---
            st.info(f"🏷️ Universe: **{universe_name}** | Stocks scored: **{context['stocks_scored']}** | News analyzed: **{context['total_news']}**")

            # --- Global Macro Dashboard ---
            st.subheader("🌍 Global Market Mood")
            macro = context["macro"]
            snapshot = context["global_snapshot"]

            mood_colors = {
                "VERY_BULLISH": "🟢🟢", "BULLISH": "🟢",
                "NEUTRAL": "🟡", "BEARISH": "🔴", "VERY_BEARISH": "🔴🔴"
            }
            mood_emoji = mood_colors.get(macro["market_mood"], "⚪")

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric("Macro Score", f"{macro['macro_score']}/10")
            mc2.metric("Market Mood", f"{mood_emoji} {macro['market_mood']}")
            if "sp500" in snapshot:
                mc3.metric("S&P 500", f"{snapshot['sp500']['price']}",
                           delta=f"{snapshot['sp500']['change_pct']}%")
            if "nasdaq" in snapshot:
                mc4.metric("Nasdaq", f"{snapshot['nasdaq']['price']}",
                           delta=f"{snapshot['nasdaq']['change_pct']}%")

            mc5, mc6, mc7, mc8 = st.columns(4)
            if "crude_oil" in snapshot:
                mc5.metric("Crude Oil", f"${snapshot['crude_oil']['price']}",
                           delta=f"{snapshot['crude_oil']['change_pct']}%")
            if "gold" in snapshot:
                mc6.metric("Gold", f"${snapshot['gold']['price']}",
                           delta=f"{snapshot['gold']['change_pct']}%")
            if "india_vix" in snapshot:
                mc7.metric("India VIX", f"{snapshot['india_vix']['price']}",
                           delta=f"{snapshot['india_vix']['change_pct']}%",
                           delta_color="inverse")
            if "usd_inr" in snapshot:
                mc8.metric("USD/INR", f"₹{snapshot['usd_inr']['price']}",
                           delta=f"{snapshot['usd_inr']['change_pct']}%",
                           delta_color="inverse")

            with st.expander("📊 Macro Factor Breakdown"):
                factors_df = pd.DataFrame([
                    {"Factor": k, "Score": v} for k, v in macro["factors"].items()
                ])
                st.dataframe(factors_df, use_container_width=True, hide_index=True)

            with st.expander("🔄 Sector Rotation Signals"):
                sector_df = pd.DataFrame([
                    {"Sector": k.replace("_", " ").title(), "Score": v,
                     "Signal": "Favorable" if v > 0.1 else ("Unfavorable" if v < -0.1 else "Neutral")}
                    for k, v in context["sector_signals"].items()
                ]).sort_values("Score", ascending=False)
                st.dataframe(sector_df, use_container_width=True, hide_index=True)

            st.divider()

            # --- Split candidates by trade type ---
            intraday_candidates = [
                c for c in candidates
                if c.trade_type in ("FNO_INTRADAY", "NON_FNO_INTRADAY")
            ]
            delivery_candidates = [
                c for c in candidates if c.trade_type == "DELIVERY_ONLY"
            ]

            st.subheader(f"🔥 Top {len(candidates)} Boom Candidates — {universe_name}")

            def _build_boom_table(cands):
                data = []
                for c in cands:
                    trade_label = {
                        "FNO_INTRADAY": "F&O",
                        "NON_FNO_INTRADAY": "Non-F&O",
                        "DELIVERY_ONLY": "Delivery",
                    }.get(c.trade_type, c.trade_type)
                    data.append({
                        "Rank": c.index_rank,
                        "Stock": c.symbol.replace(".NS", ""),
                        "Score": c.boom_probability,
                        "Move": getattr(c, "expected_move", "?"),
                        "Confidence": c.confidence,
                        "Trade Type": trade_label,
                        "Gap %": f"{c.technical_summary.get('gap_pct', 0):+.1f}%",
                        "Rel Vol": c.technical_summary.get("rel_vol", ""),
                        "Gap/ATR": f"{c.technical_summary.get('gap_vs_atr', 0):.2f}",
                        "EMA Trend": "Up" if c.technical_summary.get("ema_bullish") else "Down",
                        "RSI": c.technical_summary.get("rsi", ""),
                        "5D Ret": f"{c.technical_summary.get('returns_5d', 0):.1f}%",
                        "Sentiment": c.sentiment_label,
                    })
                if not data:
                    st.info("No candidates in this category.")
                    return
                df = pd.DataFrame(data)
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Score": st.column_config.ProgressColumn(
                            "Breakout Score", min_value=0, max_value=100, format="%.0f"
                        ),
                        "Move": st.column_config.TextColumn("Expected Move"),
                        "Rank": st.column_config.NumberColumn("Index Rank", format="%d"),
                    },
                )

            tab_intraday, tab_delivery, tab_all = st.tabs([
                f"⚡ Intraday ({len(intraday_candidates)})",
                f"📦 Delivery Only ({len(delivery_candidates)})",
                f"📊 All ({len(candidates)})",
            ])

            with tab_intraday:
                st.caption("F&O stocks + high-volume non-F&O stocks eligible for intraday trading")
                _build_boom_table(intraday_candidates)

            with tab_delivery:
                st.caption("Lower volume stocks — suitable for delivery/positional trades only")
                _build_boom_table(delivery_candidates)

            with tab_all:
                _build_boom_table(candidates)

            # --- Detail cards ---
            st.subheader("📋 Detailed Analysis")
            for c in candidates:
                conf_icon = {"HIGH": "🟢", "MEDIUM": "🟡", "LOW": "🔴"}[c.confidence]
                sent_icon = {"BULLISH": "📈", "BEARISH": "📉", "NEUTRAL": "➖", "NO_DATA": "❓"}[c.sentiment_label]

                trade_icon = {"FNO_INTRADAY": "⚡", "NON_FNO_INTRADAY": "⚡", "DELIVERY_ONLY": "📦"}.get(c.trade_type, "")
                with st.expander(
                    f"{conf_icon} **{c.symbol.replace('.NS', '')}** — "
                    f"Boom: {c.boom_probability}% — "
                    f"Rank #{c.index_rank} — "
                    f"{c.confidence} confidence — "
                    f"{trade_icon} {c.trade_type.replace('_', ' ').title()}"
                ):
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Boom Probability", f"{c.boom_probability}%")
                    col2.metric("Sentiment", f"{sent_icon} {c.sentiment_label}",
                                delta=f"{c.sentiment_score:.3f}")
                    col3.metric("Sector Score", f"{c.sector_score}")
                    col4.metric("Market Mood", macro["market_mood"])

                    col5, col6, col7, col8 = st.columns(4)
                    col5.metric("RSI", f"{c.technical_summary.get('rsi', 'N/A'):.1f}")
                    col6.metric("5D Return", f"{c.technical_summary.get('returns_5d', 0):.1f}%")
                    col7.metric("10D Return", f"{c.technical_summary.get('returns_10d', 0):.1f}%")
                    col8.metric("Rel Volume", f"{c.technical_summary.get('rel_vol', 0):.1f}x")

                    if c.top_headlines:
                        st.markdown("**📰 Related News:**")
                        for h in c.top_headlines:
                            sent_color = "green" if h["label"] == "BULLISH" else ("red" if h["label"] == "BEARISH" else "gray")
                            st.markdown(f"- :{sent_color}[{h['label']}] {h['title']} *(via {h['source']})*")
                    else:
                        st.caption("No direct news found for this stock")

            st.divider()
            st.caption(f"📰 {context['total_news']} news items | "
                       f"🏢 {context['stocks_scored']} stocks scored | "
                       f"🌍 Macro: {macro['market_mood']} ({macro['macro_score']}/10)")


# =====================================================
# LIVE SCAN
# =====================================================
elif mode == "📊 Live Scan":
    st.markdown(f"**Scanning {universe_name} ({len(symbols)} stocks) with rule-based filters.**")

    if st.button(f"🔍 Run Scan — {universe_name}", type="primary", use_container_width=True):
        with st.spinner(f"Fetching data for {len(symbols)} stocks..."):
            stock_data = fetch_all_stocks(symbols)

        progress = st.progress(0)
        all_features = []
        for i, (symbol, df) in enumerate(stock_data.items()):
            features = build_features(symbol, df)
            if features is not None:
                features["index_rank"] = universe_rank_map.get(symbol, 999)
                all_features.append(features)
            progress.progress((i + 1) / len(stock_data))
        progress.empty()

        candidates = []
        for f in all_features:
            if (abs(f["gap_pct"]) >= gap_thresh
                    and f["rel_vol"] >= vol_thresh
                    and f["price_above_vwap"]):
                f["score"] = compute_score(f)
                f["reason"] = build_reason(f)
                candidates.append(f)

        candidates.sort(key=lambda x: (-x["score"], x["index_rank"]))
        candidates = candidates[:top_n]
        candidates = enrich_candidates(candidates)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Stocks Scanned", len(all_features))
        col2.metric("Candidates Found", len(candidates))
        col3.metric("Gap Threshold", f"{gap_thresh}%")
        col4.metric("Volume Threshold", f"{vol_thresh}x")

        if not candidates:
            st.warning("No stocks matched all primary filters. Try lowering thresholds.")
        else:
            st.subheader(f"🎯 Trade Signals — {universe_name}")
            signals_df = pd.DataFrame(candidates)
            display_cols = [c for c in [
                "index_rank", "symbol", "score", "direction", "entry", "stoploss",
                "target", "risk", "reward", "gap_pct", "rel_vol", "vwap",
                "ema_bullish", "reason",
            ] if c in signals_df.columns]
            st.dataframe(
                signals_df[display_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "index_rank": st.column_config.NumberColumn("Rank", format="%d"),
                    "symbol": st.column_config.TextColumn("Stock"),
                    "score": st.column_config.NumberColumn("Score", format="%d / 9"),
                    "entry": st.column_config.NumberColumn("Entry ₹", format="%.2f"),
                    "stoploss": st.column_config.NumberColumn("SL ₹", format="%.2f"),
                    "target": st.column_config.NumberColumn("Target ₹", format="%.2f"),
                    "gap_pct": st.column_config.NumberColumn("Gap %", format="%.1f%%"),
                    "rel_vol": st.column_config.NumberColumn("Rel Vol", format="%.1fx"),
                },
            )

            for c in candidates:
                with st.expander(f"**{c['symbol']}** — Rank #{c.get('index_rank','?')} — Score {c['score']}/9"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Entry", f"₹{c['entry']}")
                    c2.metric("Stoploss", f"₹{c['stoploss']}")
                    c3.metric("Target", f"₹{c['target']}")
                    c4.metric("R:R", "1:2")
                    st.caption(f"**Reason:** {c['reason']}")

        with st.expander("📊 All Stocks Overview"):
            if all_features:
                overview_df = pd.DataFrame(all_features)
                overview_cols = [c for c in [
                    "index_rank", "symbol", "gap_pct", "rel_vol", "price_above_vwap",
                    "ema_bullish", "current_price", "vwap", "rsi",
                ] if c in overview_df.columns]
                st.dataframe(overview_df[overview_cols].sort_values("index_rank"),
                             use_container_width=True, hide_index=True)


# =====================================================
# BACKTEST
# =====================================================
elif mode == "⏮️ Backtest":
    st.info(f"Backtests the ORB strategy on ~60 days of 15-min data for **{len(symbols)} {universe_name}** stocks.")

    # ── Entry thresholds ─────────────────────────────────────────────────
    st.subheader("🎯 Entry Thresholds")
    st.caption("Higher gap% and volume filters = fewer but stronger trades")

    th_col1, th_col2 = st.columns(2)
    with th_col1:
        bt_gap_thresh = st.slider(
            "Min Gap %", min_value=1.0, max_value=6.0, value=2.0, step=0.5,
            help="Only trade stocks that gap by at least this % from previous close"
        )
    with th_col2:
        bt_vol_thresh = st.slider(
            "Min Relative Volume", min_value=1.0, max_value=5.0, value=1.5, step=0.5,
            help="Only trade when volume is at least this multiple of 10-day average"
        )

    # ── Improvement toggles ───────────────────────────────────────────────
    st.subheader("⚙️ Strategy Improvements")
    st.caption("Toggle each improvement to see its impact on Profit Factor")

    col_a, col_b = st.columns(2)
    with col_a:
        use_tight_sl = st.checkbox(
            "Tighter Stop Loss (50% of candle)",
            value=False,
            help="Use half the opening candle as SL instead of full candle. Reduces avg loss."
        )
        use_trailing = st.checkbox(
            "Trailing Stop",
            value=False,
            help="Move SL to breakeven at 1R profit. Trail by 0.5R after 2R. Lets winners run."
        )
    with col_b:
        use_candle_filter = st.checkbox(
            "Skip Wide Candles (>1.5× ATR)",
            value=False,
            help="Skip trades where the opening candle is unusually large — too chaotic."
        )
        use_nifty_filter = st.checkbox(
            "Nifty Direction Filter",
            value=False,
            help="Skip LONG signals when Nifty gaps down, skip SHORT when Nifty gaps up."
        )

    sl_fraction = 0.5 if use_tight_sl else 1.0
    max_atr = 1.5 if use_candle_filter else None

    if st.button(f"⏮️ Run Backtest — {universe_name}", type="primary", use_container_width=True):
        with st.spinner("Fetching historical data..."):
            stock_intraday = fetch_all_stocks(symbols, interval="15m", period="60d")
            stock_daily = {}
            for symbol in symbols:
                try:
                    df = fetch_daily(symbol, days=90)
                    if not df.empty:
                        stock_daily[symbol] = df
                except Exception:
                    pass

            # Fetch Nifty if needed
            nifty_df = None
            if use_nifty_filter:
                try:
                    nifty_df = fetch_daily("^NSEI", days=90)
                except Exception:
                    pass

        with st.spinner("Simulating trades..."):
            report = run_backtest(
                symbols, stock_intraday, stock_daily,
                nifty_daily=nifty_df,
                gap_threshold=bt_gap_thresh,
                vol_threshold=bt_vol_thresh,
                sl_fraction=sl_fraction,
                trailing_stop=use_trailing,
                max_candle_atr_ratio=max_atr,
                nifty_filter=use_nifty_filter,
            )

        triggered = report.wins + report.losses

        if triggered == 0:
            st.warning("No trades were triggered.")
        else:
            # Active improvements summary
            active = [f"Gap≥{bt_gap_thresh}%", f"Vol≥{bt_vol_thresh}x"]
            if use_tight_sl: active.append("Tight SL")
            if use_trailing: active.append("Trailing Stop")
            if use_candle_filter: active.append("Wide Candle Filter")
            if use_nifty_filter: active.append("Nifty Filter")
            st.success(f"✅ Active: {' + '.join(active)}")

            st.subheader(f"📈 Backtest Results — {universe_name}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Trades", triggered)
            c2.metric("Win Rate", f"{report.win_rate:.1f}%")
            c3.metric("Total P&L", f"₹{report.total_pnl:.2f}",
                       delta=f"{'Profit' if report.total_pnl > 0 else 'Loss'}")
            c4.metric("Max Drawdown", f"₹{report.max_drawdown:.2f}")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Wins", report.wins)
            c6.metric("Losses", report.losses)
            c7.metric("Avg Gain", f"₹{report.avg_gain:.2f}")
            c8.metric("Avg Loss", f"₹{report.avg_loss:.2f}")

            # Profit Factor — highlighted
            pf = report.profit_factor
            pf_color = "green" if pf >= 2.0 else ("orange" if pf >= 1.5 else "red")
            st.markdown(
                f"**Profit Factor:** :{pf_color}[{pf:.3f}]"
                f"{'  ✅ Target reached!' if pf >= 2.0 else f'  (Target: 2.0 — need +{2.0 - pf:.2f} more)'}"
            )

            if report.trades:
                st.subheader("📉 Equity Curve")
                equity = []
                cumulative = 0.0
                for t in report.trades:
                    if t.result != "NO_TRIGGER":
                        cumulative += t.pnl
                        equity.append({"Trade #": len(equity) + 1, "P&L": cumulative})
                if equity:
                    st.line_chart(pd.DataFrame(equity), x="Trade #", y="P&L")

            st.subheader("📋 Trade Log")
            trade_data = [
                {"Symbol": t.symbol, "Date": t.date, "Dir": t.direction,
                 "Entry": t.entry, "SL": t.stoploss, "Target": t.target,
                 "Exit": t.exit_price, "P&L": round(t.pnl, 2), "Result": t.result}
                for t in report.trades if t.result != "NO_TRIGGER"
            ]
            if trade_data:
                st.dataframe(pd.DataFrame(trade_data), use_container_width=True, hide_index=True)

            st.divider()
            if report.total_pnl > 0:
                st.success("✅ Strategy is profitable. Past results don't guarantee future performance.")
            else:
                st.error("❌ Not profitable. Refine filters before using live.")


# =====================================================
# TRAIN MODEL
# =====================================================
elif mode == "🧠 Train Model":
    st.markdown(f"""
    **Train the AI model on ALL {len(symbols)} {universe_name} stocks using their FULL available history.**
    yfinance provides 10-20+ years of daily data per stock. For {len(symbols)} stocks, this means
    potentially **millions of training samples** — giving the model deep market cycle experience
    across bull runs, crashes, corrections, and recoveries.
    Each universe gets its own saved model file.
    """)

    # --- Update existing model (incremental) ---
    _train_model = _BoomPredictor()
    _train_loaded = _train_model.load(universe=universe_name)
    if _train_loaded and _train_model.trained_until:
        _train_gap = (_date.today() - _train_model.trained_until).days
        if _train_gap > 0:
            st.info(
                f"📅 Existing model trained until **{_train_model.trained_until}** "
                f"— **{_train_gap} day{'s' if _train_gap != 1 else ''}** of new data available."
            )
            if st.button(
                f"🔄 Quick Update (+{_train_gap} days, ~30 seconds)",
                use_container_width=True,
            ):
                upd_bar = st.progress(0, text="Updating...")
                def _on_upd(phase, progress, message):
                    upd_bar.progress(min(progress, 1.0), text=message)
                _, upd_metrics = update_model(
                    symbols, universe=universe_name,
                    progress_callback=_on_upd,
                )
                upd_bar.empty()
                if "error" in upd_metrics:
                    st.error(f"Update failed: {upd_metrics['error']}")
                else:
                    st.success(
                        f"✅ Model updated with {upd_metrics.get('update_samples', 0):,} "
                        f"new samples from {upd_metrics.get('stocks_updated', 0)} stocks."
                    )
            st.divider()
        else:
            st.success(f"✅ Model is already up to date (trained until {_train_model.trained_until})")
    elif _train_loaded:
        st.info("ℹ️ Model exists but has no training date. Full retrain will enable auto-update.")

    # --- Check for interrupted training checkpoint ---
    from project.ml.predictor import _checkpoint_path, _load_checkpoint
    _ckpt = _load_checkpoint(_checkpoint_path(universe_name))
    if _ckpt:
        _done_count = len(_ckpt["done_symbols"])
        _total_count = len(symbols)
        _pct_done = round(_done_count / _total_count * 100, 1)
        st.warning(
            f"⚠️ Previous training was interrupted! "
            f"**{_done_count}/{_total_count}** stocks already fetched ({_pct_done}%). "
            f"Click Train below to **resume from where it stopped**."
        )

    _btn_label = (
        f"▶️ Resume Training ({_ckpt and len(_ckpt['done_symbols']) or 0}/{len(symbols)} done)"
        if _ckpt
        else f"🧠 Train on ALL {len(symbols)} {universe_name} Stocks (Full History)"
    )

    if st.button(_btn_label, type="primary", use_container_width=True):
        # --- Live progress bar ---
        progress_bar = st.progress(0, text="Starting...")
        status_text = st.empty()
        phase_container = st.container()

        with phase_container:
            phase_cols = st.columns(3)
            phase_cols[0].markdown("**Phase 1:** Fetching data")
            phase_cols[1].markdown("**Phase 2:** Training ML")
            phase_cols[2].markdown("**Phase 3:** Saving model")

        def on_progress(phase, progress, message):
            progress_bar.progress(min(progress, 1.0), text=message)

        model, metrics = train_model(symbols, universe=universe_name, progress_callback=on_progress)

        progress_bar.empty()
        status_text.empty()
        phase_container.empty()

        if "error" in metrics:
            st.error(f"Training failed: {metrics['error']}")
        else:
            st.success(f"✅ Model trained on {universe_name} and saved!")

            st.subheader("📊 Training Metrics")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mean AUC", f"{metrics['mean_auc']:.4f}")
            c2.metric("Total Samples", f"{metrics['n_samples']:,}")
            c3.metric("Positive (Boom)", f"{metrics['n_positive']:,} ({metrics['positive_ratio']}%)")
            c4.metric("Negative", f"{metrics['n_negative']:,}")

            c5, c6 = st.columns(2)
            if metrics.get("total_daily_candles"):
                c5.metric("Total Daily Candles Ingested", f"{metrics['total_daily_candles']:,}")
            if metrics.get("stocks_used"):
                c6.metric("Stocks Used", metrics["stocks_used"])

            if metrics.get("cv_auc_scores"):
                st.markdown("**Cross-Validation AUC Scores:**")
                for i, score in enumerate(metrics["cv_auc_scores"], 1):
                    st.write(f"  Fold {i}: {score:.4f}")

            if metrics.get("feature_importances"):
                st.subheader("🔍 Feature Importance")
                from project.ml.features import FEATURE_COLUMNS
                imp_df = pd.DataFrame({
                    "Feature": FEATURE_COLUMNS,
                    "Importance": metrics["feature_importances"],
                }).sort_values("Importance", ascending=False)
                st.bar_chart(imp_df.set_index("Feature"))

# =====================================================
# LIVE TRADING
# =====================================================
elif mode == "⚡ Live Trading":
    import os as _os

    st.markdown("""
    **Automated ORB Trading Engine** — Scans, ranks, and trades automatically.
    - 📋 **Paper Mode**: Simulates trades with real prices, no real money
    - 🟢 **Live Mode**: Places real orders via Angel One SmartAPI
    - 📱 **Telegram Alerts**: Get notified on every trade entry/exit
    """)

    # --- Trading Configuration ---
    st.subheader("⚙️ Trading Configuration")

    tcol1, tcol2, tcol3 = st.columns(3)
    with tcol1:
        trading_mode = st.radio("Trading Mode", ["📋 Paper", "🟢 Live"],
                                help="Start with Paper mode to validate before going live")
    with tcol2:
        trading_capital = st.number_input("Capital (₹)", min_value=1000, max_value=10_00_000,
                                          value=20_000, step=5000)
    with tcol3:
        max_trades = st.slider("Max Simultaneous Trades", 1, 8, 4)

    tcol4, tcol5, tcol6 = st.columns(3)
    with tcol4:
        lt_gap_threshold = st.slider("Min Gap %", 1.0, 8.0, 4.0, 0.5, key="lt_gap")
    with tcol5:
        lt_vol_threshold = st.slider("Min Rel Volume", 1.0, 8.0, 2.5, 0.5, key="lt_vol")
    with tcol6:
        daily_loss_pct = st.slider("Daily Loss Limit %", 1.0, 10.0, 3.0, 0.5)

    st.divider()

    # --- Risk Summary ---
    st.subheader("🛡️ Risk Parameters")
    rcol1, rcol2, rcol3, rcol4 = st.columns(4)
    max_per_trade = trading_capital * 0.25
    daily_loss_limit = trading_capital * (daily_loss_pct / 100)
    rcol1.metric("Capital", f"₹{trading_capital:,}")
    rcol2.metric("Max Per Trade", f"₹{max_per_trade:,.0f}")
    rcol3.metric("Daily Loss Limit", f"₹{daily_loss_limit:,.0f}")
    rcol4.metric("Max Trades", max_trades)

    st.divider()

    # --- Broker Connection Status ---
    is_live = "Live" in trading_mode
    if is_live:
        st.subheader("🔌 Broker Connection")
        has_creds = all([
            _os.getenv("ANGEL_API_KEY"),
            _os.getenv("ANGEL_CLIENT_ID"),
            _os.getenv("ANGEL_PASSWORD"),
            _os.getenv("ANGEL_TOTP_SECRET"),
        ])
        if has_creds:
            st.success("✅ Angel One credentials found")
        else:
            st.error(
                "❌ Angel One credentials not configured. Set these environment variables:\n"
                "- `ANGEL_API_KEY`\n"
                "- `ANGEL_CLIENT_ID`\n"
                "- `ANGEL_PASSWORD`\n"
                "- `ANGEL_TOTP_SECRET`"
            )
            st.stop()

    # --- Telegram Setup ---
    st.subheader("📱 Telegram Alerts")
    has_telegram = bool(_os.getenv("TELEGRAM_BOT_TOKEN") and _os.getenv("TELEGRAM_CHAT_ID"))
    if has_telegram:
        st.success("✅ Telegram alerts enabled")
    else:
        st.info(
            "📱 Telegram alerts not configured (optional). To enable:\n"
            "1. Message **@BotFather** on Telegram → `/newbot` → get your bot token\n"
            "2. Message your bot, then find your chat ID\n"
            "3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` env vars"
        )

    st.divider()

    # --- Scan Now (doesn't wait for market hours) ---
    st.subheader("🔍 Scan Now")
    st.caption("Run the scanner immediately to see which stocks qualify right now")

    if st.button("🔍 Run ORB Scan", type="primary", use_container_width=True):
        with st.spinner("Scanning stocks for ORB setups..."):
            from project.trading.paper import run_paper_scan_only
            scan_results = run_paper_scan_only(
                capital=trading_capital,
                gap_threshold=lt_gap_threshold,
                vol_threshold=lt_vol_threshold,
                symbols=[s for s in symbols],
            )

        if not scan_results:
            st.warning("No qualifying stocks found right now. This is normal outside market hours or when no stocks meet the gap/volume thresholds.")
        else:
            st.success(f"Found {len(scan_results)} qualifying stocks!")

            scan_df = pd.DataFrame(scan_results)
            scan_df = scan_df.rename(columns={
                "ticker": "Stock", "direction": "Direction",
                "gap_pct": "Gap %", "rel_vol": "Rel Vol",
                "entry": "Entry ₹", "stoploss": "SL ₹",
                "target": "Target ₹", "quantity": "Qty",
                "risk_amount": "Risk ₹", "reward_amount": "Reward ₹",
                "score": "Score",
            })
            st.dataframe(scan_df, use_container_width=True, hide_index=True)

            # Per-trade breakdown
            for r in scan_results:
                with st.expander(f"{r['ticker']} — {r['direction']} | Gap {r['gap_pct']:+.1f}%"):
                    ec1, ec2, ec3, ec4 = st.columns(4)
                    ec1.metric("Entry", f"₹{r['entry']:.2f}")
                    ec2.metric("Stoploss", f"₹{r['stoploss']:.2f}")
                    ec3.metric("Target", f"₹{r['target']:.2f}")
                    ec4.metric("Quantity", r["quantity"])

                    ec5, ec6, ec7 = st.columns(3)
                    ec5.metric("Risk", f"₹{r['risk_amount']:.2f}")
                    ec6.metric("Potential Reward", f"₹{r['reward_amount']:.2f}")
                    ec7.metric("Risk:Reward", "1:2")

    st.divider()

    # --- Start Automated Trading ---
    st.subheader("🤖 Automated Trading")

    mode_label = "PAPER" if "Paper" in trading_mode else "LIVE"
    mode_color = "blue" if "Paper" in trading_mode else "red"

    if is_live:
        st.warning(
            "⚠️ **LIVE MODE** — Real money will be used! "
            "Make sure you've tested thoroughly in Paper mode first."
        )

    if st.button(
        f"▶️ Start {mode_label} Trading Session",
        type="primary" if not is_live else "secondary",
        use_container_width=True,
    ):
        st.info(
            f"🕘 The trading engine will:\n"
            f"1. Wait for market open (9:15 AM)\n"
            f"2. Scan after first 15-min candle (9:30 AM)\n"
            f"3. Place top {max_trades} trades automatically\n"
            f"4. Monitor until 3:15 PM\n"
            f"5. Exit remaining positions\n"
            f"6. Send daily report"
        )

        log_container = st.empty()
        status_container = st.empty()

        from project.trading.executor import TradingExecutor
        from project.trading.risk import RiskConfig

        alert_fn = None
        if has_telegram:
            from project.alerts.telegram import TelegramAlert
            _tg = TelegramAlert()
            alert_fn = _tg.send

        executor = TradingExecutor(
            mode="paper" if "Paper" in trading_mode else "live",
            capital=trading_capital,
            gap_threshold=lt_gap_threshold,
            vol_threshold=lt_vol_threshold,
            top_n=max_trades,
            symbols=[s for s in symbols],
            alert_callback=alert_fn,
        )
        executor.risk.config.daily_loss_limit_pct = daily_loss_pct / 100

        daily_log = executor.run()

        # Show results
        st.subheader("📊 Session Results")
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("Trades", daily_log.trades_placed)
        rc2.metric("Wins", daily_log.wins)
        rc3.metric("Losses", daily_log.losses)
        rc4.metric("P&L", f"₹{daily_log.total_pnl:+.2f}",
                    delta_color="normal" if daily_log.total_pnl >= 0 else "inverse")

        if daily_log.events:
            st.subheader("📋 Event Log")
            for event in daily_log.events:
                st.text(event)

    st.divider()

    # --- Paper Trade History ---
    st.subheader("📜 Paper Trade History")
    from project.trading.paper import get_paper_trade_history
    history = get_paper_trade_history()
    if history:
        for day_log in reversed(history[-10:]):
            with st.expander(
                f"{day_log['date']} — "
                f"P&L: ₹{day_log['total_pnl']:+.2f} | "
                f"W:{day_log['wins']} L:{day_log['losses']}"
            ):
                if day_log.get("trades"):
                    trades_df = pd.DataFrame(day_log["trades"])
                    st.dataframe(trades_df, use_container_width=True, hide_index=True)
    else:
        st.info("No paper trades yet. Run a paper trading session to see results here.")
