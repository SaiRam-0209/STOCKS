"""Streamlit web UI — AI Stock Scanner for All / Largecap / Midcap / Smallcap."""

import streamlit as st
import pandas as pd

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
    from datetime import date as _date
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
        with st.spinner(f"Running AI pipeline on {len(symbols)} {universe_name} stocks..."):
            candidates, context = predict_boom_stocks(symbols, top_n=top_n, universe=universe_name)

        if not candidates:
            st.error("Failed to generate predictions. Check logs for errors.")
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

        with st.spinner("Simulating trades..."):
            report = run_backtest(symbols, stock_intraday, stock_daily)

        triggered = report.wins + report.losses

        if triggered == 0:
            st.warning("No trades were triggered.")
        else:
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
