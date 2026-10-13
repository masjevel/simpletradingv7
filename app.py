# ============================================================
# app.py
# ------------------------------------------------------------
# Streamlit-gränssnittet. ALL beräkningslogik ligger i separata
# moduler (data, indicators, signals, backtest, ki_model,
# portfolio, metrics, charts) - den här filen bygger bara UI och
# kopplar ihop dem. Kör med: streamlit run app.py
# ============================================================

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import streamlit as st

import backtest
import charts
import config
import indicators
import ki_model
import metrics
import portfolio
import research
from datetime import date
import signals as signals_mod
from data import fetch_ki_barometer, fetch_fx_rate, fetch_price_series, fetch_vix

logger = logging.getLogger("simpletradingv3.app")

st.set_page_config(page_title="Trend Heatmap & Kvantanalys", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")


# ------------------------------------------------------------
# Hjälpfunktioner för presentation
# ------------------------------------------------------------
def fmt_pct(x: float, decimals: int = 1) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    return f"{x:+.{decimals}f} %"


def fmt_ratio(x: float, decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    return f"{x:.{decimals}f}"


def info_expander(*keys: str) -> None:
    with st.expander("ℹ️ Vad betyder detta?"):
        for k in keys:
            label = k.replace("_", " ").upper()
            st.markdown(f"**{label}:** {config.EXPLANATIONS.get(k, '')}")


# ============================================================
# MODELLERNAS LOKALA INSTÄLLNINGAR
# ============================================================
def reset_model(prefix):
    for key in list(st.session_state):
        if key.startswith(prefix):
            del st.session_state[key]


st.title("Modeller & backtest")
with st.expander("Testperiod", expanded=True):
    st.button("Återställ testperiod", key="reset_period", on_click=reset_model, args=("period_",))
    period_mode = st.radio("Period för backtesten", ["Längsta tillgängliga historik", "Välj datum"], horizontal=True, key="period_mode")
    period_start = period_end = None
    if period_mode == "Välj datum":
        period_start = st.date_input("Startdatum", date(2012, 1, 1), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), key="period_start")
        period_end = st.date_input("Slutdatum", date.today(), min_value=date(1900, 1, 1), max_value=date(2100, 12, 31), key="period_end")
        if period_start > period_end:
            st.error("Startdatum måste vara före eller samma dag som slutdatum.")
            st.stop()
    st.caption("Datumen gäller båda modellerna. Inom KI-backtestet använder alla jämförelser exakt samma handelsdagar. Längsta historik beror på respektive modells valda tillgångar; faktisk period visas vid resultatet.")
st.info(
    "ℹ️ Experimentellt analys- och utbildningsverktyg – inte "
    "investeringsrådgivning. Historiska resultat garanterar inte "
    "framtida avkastning."
)

with st.expander("Om verktyget och riskerna"):
    st.markdown("""
Appen är ett experimentellt analys- och utbildningsverktyg.
Innehållet är inte personlig investeringsrådgivning eller en
rekommendation att köpa eller sälja.

Signaler och backtest bygger på historiska data och förenklade
antaganden. Data och beräkningar kan innehålla fel.
**Historiska resultat garanterar inte framtida avkastning.**

Alla investeringar innebär risk och du kan förlora hela eller
delar av ditt kapital. Du ansvarar själv för dina investeringsbeslut.
Gör en egen, välgrundad bedömning utifrån din ekonomi, dina mål
och din risktolerans. Använd inte appen som enda beslutsunderlag.
""")
st.caption("📈 Teknisk modell: flik 1–2   •   🌍 KI-modellen: flik 3–4")
tab1, tab3, tab2, tab4 = st.tabs(["📈 Teknisk modell – Signaler", "🧪 Teknisk modell – Backtest", "🌍 KI-modellen – Konjunktur", "🏦 KI-modellen – Portföljbacktest"])
with tab1:
    st.info("Den tekniska modellen använder SMA, RSI, MACD och VIX. Dessa signalparametrar används även i Teknisk modell – Backtest.")
    st.button("Återställ standard – teknisk modell", key="reset_technical", on_click=reset_model, args=("tech_",))
    st.subheader("Signalinställningar")
    with st.expander("Använd i strategin", expanded=True):
        use_rsi = st.checkbox("RSI som alternativ köpsignal", True, key="tech_use_rsi")
        use_vix = st.checkbox("VIX som alternativ köpsignal", True, key="tech_use_vix")
        use_macd = st.checkbox("MACD som säljsignal", True, key="tech_use_macd")
        use_sell_rsi = st.checkbox("Kräv högt RSI för MACD-sälj", True, key="tech_use_sell_rsi", disabled=not use_macd)
        use_trend = st.checkbox("Kräv pris över SMA för köp", False, key="tech_use_trend")
        st.caption("RSI ELLER VIX kan ge köp. Trendfiltret måste dessutom uppfyllas om det är valt. MACD ger sälj, med RSI-filter om valt. Sälj prioriteras vid samtidig köp- och säljsignal.")
        if not use_rsi and not use_vix:
            st.warning("Inga köpsignaler är aktiva. Strategin startar i kassa och gör inga köp.")
        if not use_macd:
            st.warning("Ingen säljsignal är aktiv. Eventuella köp behålls till testperiodens slut.")
    active_description = f"Köp: {' + '.join(x for x, enabled in [('RSI', use_rsi), ('VIX', use_vix)] if enabled) or 'inga'} (alternativa signaler) · Sälj: {'MACD' if use_macd else 'av'} · RSI-säljfilter: {'på' if use_macd and use_sell_rsi else 'av'} · Trendvillkor för köp: {'på' if use_trend else 'av'}"
    st.caption(active_description)
    ticker = st.text_input("Tillgång (Ticker, teknisk analys)", value=config.DEFAULT_TICKER, help='Börssymbol för prisdata. Påverkar Teknisk modell – Signaler och Teknisk modell – Backtest.', key="tech_ticker").upper().strip()
    with st.expander("Trösklar och perioder"):
        buy_rsi_threshold = st.slider("RSI köpgräns", 10, 45, config.DEFAULT_BUY_RSI_THRESHOLD, 1, help=config.EXPLANATIONS["rsi"] + ' Påverkar Teknisk modell – Signaler och Teknisk modell – Backtest.', key="tech_buy_rsi_threshold")
        sell_macd_rsi_filter = st.slider("MACD/RSI säljfilter", 50, 80, config.DEFAULT_SELL_RSI_FILTER, 1, help="Kräver RSI över denna nivå samtidigt som MACD korsar ned under sin signallinje för en säljsignal." + ' Påverkar Teknisk modell – Signaler och Teknisk modell – Backtest.', key="tech_sell_macd_rsi_filter")
        cooldown_bars = st.slider("Signal-cooldown (handelsdagar)", 5, 60, config.DEFAULT_COOLDOWN_BARS, 1, help=config.EXPLANATIONS["cooldown"] + ' Påverkar Teknisk modell – Signaler och Teknisk modell – Backtest.', key="tech_cooldown_bars")
        sma_trend_period = st.slider("SMA-period (huvudtrend)", 50, 300, config.DEFAULT_SMA_PERIOD, 10, help=config.EXPLANATIONS["sma"] + ' Påverkar Teknisk modell – Signaler och Teknisk modell – Backtest.', key="tech_sma_trend_period")
        vix_panic_threshold = st.slider("VIX paniktröskel", 20.0, 60.0, config.DEFAULT_VIX_PANIC_THRESHOLD, 0.5, help="När VIX överstiger nivån kan den tekniska modellen skapa en konträr köpsignal efter cooldown." + ' Påverkar Teknisk modell – Signaler och Teknisk modell – Backtest.', key="tech_vix_panic_threshold")
    with st.expander("Grafvisning"):
        show_sma = st.checkbox("Visa SMA och trendfärg", True, key="tech_show_sma")
        show_rsi = st.checkbox("Visa RSI", True, key="tech_show_rsi")
        show_macd = st.checkbox("Visa MACD", True, key="tech_show_macd")
        show_vix = st.checkbox("Visa VIX", True, key="tech_show_vix")
        st.caption("Dessa val ändrar bara diagrammen, aldrig handeln.")
        color_intensity_cap = st.slider("Heatmap-intensitet", 30, 300, config.DEFAULT_HEATMAP_CAP, 10, help="Styr endast färgstyrkan i trendgrafen. Ändrar inga signaler eller backtestresultat.", key="tech_color_intensity_cap")
        st.caption("Heatmap-intensitet ändrar endast grafens utseende, INTE signaler eller backtestresultat.")

with tab3:
    st.info("Detta backtest använder samma RSI-, MACD-, VIX- och SMA-inställningar som Teknisk modell – Signaler.")
    model_box = st.container(border=True)
    st.subheader("Handelsantaganden")
    execution_method_label = st.selectbox("Execution-metod (endast teknisk backtest)", config.EXECUTION_METHODS, index=0, help='Handel sker nästa handelsdag till Open eller Close; saknat Open ersätts med Close. Påverkar endast Teknisk modell – Backtest.', key="tech_execution_method_label")
    cost_bps = st.number_input("Courtage/transaktionskostnad (bps)", 0.0, 500.0, config.DEFAULT_COST_BPS, 1.0, help=config.EXPLANATIONS["cost"] + ' Påverkar endast Teknisk modell – Backtest.', key="tech_cost_bps")
    slippage_bps = st.number_input("Slippage (bps)", 0.0, 500.0, config.DEFAULT_SLIPPAGE_BPS, 1.0, help=config.EXPLANATIONS["slippage"] + ' Påverkar endast Teknisk modell – Backtest.', key="tech_slippage_bps")
    initial_capital = st.number_input("Startkapital, teknisk backtest ($)", 1000.0, 10_000_000.0, config.DEFAULT_INITIAL_CAPITAL, 1000.0, help='Kapital vid testets början i USD. Påverkar endast Teknisk modell – Backtest.', key="tech_initial_capital")
    execution_method = "open" if "Open" in execution_method_label else "close"
    tech_risk_free = st.number_input("Riskfri jämförelseränta (%)", 0.0, 8.0, 0.0, 0.1, help="Används endast i tekniska backtestets Sharpe/Sortino. Teknisk kassa förräntas inte.", key="tech_tech_risk_free") / 100.0
    with model_box:
        st.caption(active_description)
        st.markdown("**Modell som testas just nu**")
        st.write(f"Tillgång: {ticker} · SMA: {sma_trend_period} dagar · RSI köp: <{buy_rsi_threshold} · VIX köp: >{vix_panic_threshold:g} · MACD säljfilter RSI: >{sell_macd_rsi_filter} · Cooldown: {cooldown_bars} handelsdagar")
        st.write(f"Execution: {execution_method_label} · Courtage: {cost_bps/100:.2f} % · Slippage: {slippage_bps/100:.2f} % · Startkapital: {initial_capital:,.0f} USD · Riskfri jämförelseränta: {tech_risk_free:.1%}")

with tab2:
    st.button("Återställ standard – KI Konjunktur", key="reset_ki", on_click=reset_model, args=("ki_",))
    st.info("KI-signalerna är fristående. Ett valbart trendvillkor för handel finns i KI-portföljbacktestet.")
    ki_sell_threshold = st.slider("KI säljgräns (överhettning)", 90, 140, config.DEFAULT_KI_SELL_THRESHOLD, 1, help=config.EXPLANATIONS["ki_sell"] + ' Påverkar endast KI-modellen – Konjunktur.', key="ki_ki_sell_threshold")
    ki_buy_threshold = st.slider("KI köpgräns (lågkonjunktur)", 60, 110, config.DEFAULT_KI_BUY_THRESHOLD, 1, help=config.EXPLANATIONS["ki_buy"] + ' Påverkar endast KI-modellen – Konjunktur.', key="ki_ki_buy_threshold")
    ki_duration_months = st.slider("Antal bekräftande månader", 1, 12, config.DEFAULT_KI_DURATION_MONTHS, 1, help=config.EXPLANATIONS["ki_months"] + ' Påverkar endast KI-modellen – Konjunktur.', key="ki_ki_duration_months")
    ki_buyback_rule = st.selectbox("Återköpsregel", ["classic", "flat_or_up"], format_func=lambda k: config.KI_BUYBACK_RULES[k], key="ki_buyback_rule")
    if ki_buyback_rule == "flat_or_up":
        st.caption(config.EXPLANATIONS["ki_flat_or_up"])
    else:
        st.caption("Klassisk KI-modell: köpgränsen används också som golv, och samma antal månader bekräftar köp och sälj.")
    st.caption("Inställningarna här är separata från portföljbacktestet.")

with tab4:
    st.button("Återställ standard – KI Portföljbacktest", key="reset_pf", on_click=reset_model, args=("pf_",))
    pf_model_box = st.container(border=True)
    st.caption("Inställningarna här påverkar endast KI-portföljbacktestet, inklusive jämförelserna nedan.")
    with st.expander("KI-signal"):
        pf_ki_sell_threshold = st.slider("KI säljgräns (överhettning)", 90, 140, config.DEFAULT_KI_SELL_THRESHOLD, 1, help=config.EXPLANATIONS["ki_sell"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_pf_ki_sell_threshold")
        pf_ki_buy_threshold = st.slider("KI köpgräns (lågkonjunktur)", 60, 110, config.DEFAULT_KI_BUY_THRESHOLD, 1, help=config.EXPLANATIONS["ki_buy"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_pf_ki_buy_threshold")
        pf_ki_duration_months = st.slider("Antal bekräftande månader", 1, 12, config.DEFAULT_KI_DURATION_MONTHS, 1, help=config.EXPLANATIONS["ki_months"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_pf_ki_duration_months")
        pf_ki_buyback_rule = st.selectbox("Återköpsregel", list(config.KI_BUYBACK_RULES.keys()), index=0, format_func=lambda k: config.KI_BUYBACK_RULES[k], help='Välj klassisk bekräftelse, stigande månader efter passerat golv eller oförändrat/stigande KI efter passerad köpgräns. Påverkar endast KI-modellen – Portföljbacktest.', key="pf_pf_ki_buyback_rule")
        pf_ki_floor_threshold = st.slider("Golv som måste passeras före återköp", 60, 110, config.DEFAULT_KI_FLOOR_THRESHOLD, 1, help='KI måste först vara strikt under denna nivå innan återköp kan bekräftas. För den nya regeln används köpgränsen i stället; golvet används fortfarande av övriga regler i jämförelsetabellen.', key="pf_pf_ki_floor_threshold", disabled=pf_ki_buyback_rule == "flat_or_up")
        pf_ki_effective_floor = pf_ki_buy_threshold if pf_ki_buyback_rule == "flat_or_up" else pf_ki_floor_threshold
        if pf_ki_buyback_rule == "flat_or_up":
            st.caption(config.EXPLANATIONS["ki_flat_or_up"] + " Det separata golvet används inte för denna regel.")
    with st.expander("Trendfilter för KI (valfritt)"):
        pf_trend = st.checkbox("Använd trendfilter för KI-återköp", False, key="pf_trend")
        st.caption("Trendfilter: efter KI-köpbesked väntar återköpet tills föregående handelsdags Sverigepris i SEK är över SMA 200. En ny KI-säljsignal avbryter väntande köp. Sverige används som gemensam trendreferens för hela KI-strategin.")
    with st.expander("Portfölj"):
        w_global = st.slider("Vikt Global (%)", 0, 100, int(config.DEFAULT_PORTFOLIO_WEIGHTS["global"] * 100), 1, help='Anger vikt global (%). Påverkar endast KI-modellen – Portföljbacktest.', key="pf_w_global")
        w_sweden = st.slider("Vikt Sverige (%)", 0, 100, int(config.DEFAULT_PORTFOLIO_WEIGHTS["sweden"] * 100), 1, help='Anger vikt sverige (%). Påverkar endast KI-modellen – Portföljbacktest.', key="pf_w_sweden")
        w_em = st.slider("Vikt Emerging Markets (%)", 0, 100, int(config.DEFAULT_PORTFOLIO_WEIGHTS["em"] * 100), 1, help='Anger vikt emerging markets (%). Påverkar endast KI-modellen – Portföljbacktest.', key="pf_w_em")
        rebalance_freq = st.selectbox("Rebalansering", list(config.REBALANCE_OPTIONS.keys()), index=list(config.REBALANCE_OPTIONS.keys()).index(config.DEFAULT_REBALANCE), format_func=lambda k: config.REBALANCE_OPTIONS[k], help=config.EXPLANATIONS["rebalance"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_rebalance_freq")
        portfolio_initial_capital = st.number_input("Startkapital, KI-portfölj (kr)", 1000.0, 100_000_000.0, 100_000.0, 1000.0, help='Anger startkapital, ki-portfölj (kr). Påverkar endast KI-modellen – Portföljbacktest.', key="pf_portfolio_initial_capital")
        pf_cost_bps = st.number_input("Courtage/transaktionskostnad (bps)", 0.0, 500.0, config.DEFAULT_COST_BPS, 1.0, help=config.EXPLANATIONS["cost"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_cost_bps")
        pf_slippage_bps = st.number_input("Slippage (bps)", 0.0, 500.0, config.DEFAULT_SLIPPAGE_BPS, 1.0, help=config.EXPLANATIONS["slippage"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_slippage_bps")
    with st.expander("Avriskning"):
        ki_scope = st.selectbox("KI-signalen påverkar", list(config.KI_SIGNAL_SCOPE_OPTIONS.keys()), index=0, format_func=lambda k: config.KI_SIGNAL_SCOPE_OPTIONS[k], help=config.EXPLANATIONS["ki_scope"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_ki_scope")
        derisk_pct = st.select_slider("Minska aktieexponeringen med", options=config.DERISK_LEVELS, value=config.DEFAULT_DERISK_LEVEL, help=config.EXPLANATIONS["derisk_pct"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_derisk_pct")
    with st.expander("Defensiv placering"):
        interest_mode = st.selectbox("Räntekonto", list(config.INTEREST_MODES.keys()), index=0, format_func=lambda k: config.INTEREST_MODES[k], help=config.EXPLANATIONS["risk_free"] + ' Påverkar endast KI-modellen – Portföljbacktest.', key="pf_interest_mode")
        annual_interest_rate = st.slider("Årlig ränta (%)", 0.0, 8.0, 2.5, 0.1, help="Förräntar KI-räntekontot och används i KI:s Sharpe/Sortino. Påverkar endast KI-portföljbacktest.", key="pf_annual_interest_rate") / 100.0
        st.caption("Fast ränta eller nollränta. Historisk riskfri ränteserie ingår inte i datakällorna.")
    weight_sum = w_global + w_sweden + w_em
    base_weights = {k: v for k, v in {"global": w_global/100, "sweden": w_sweden/100, "em": w_em/100}.items() if v > 0}
    risk_free_annual = annual_interest_rate if interest_mode == "fixed" else 0.0
    with pf_model_box:
        st.caption(f"KI styr köp och sälj · Trendfilter för återköp: {'Sverige SMA 200' if pf_trend else 'av'} · RSI, MACD och VIX påverkar inte KI.")
        st.markdown("**Modell som testas just nu**")
        st.write(f"KI sälj: >{pf_ki_sell_threshold} i {pf_ki_duration_months} månader · Köpgräns: <{pf_ki_buy_threshold} · Aktiveringsnivå/golv: <{pf_ki_effective_floor} · Återköp: {config.KI_BUYBACK_RULES[pf_ki_buyback_rule]}")
        st.write(f"Avriskning: {derisk_pct} % av {config.KI_SIGNAL_SCOPE_OPTIONS[ki_scope]} · Defensiv ränta: {risk_free_annual:.1%} · Portfölj: {w_global}/{w_sweden}/{w_em} · Rebalansering: {config.REBALANCE_OPTIONS[rebalance_freq]}")
        st.write(f"Startkapital: {portfolio_initial_capital:,.0f} kr · Courtage: {pf_cost_bps/100:.2f} % · Slippage: {pf_slippage_bps/100:.2f} % · Handel: Close efter publiceringsfördröjning")

scope_key_map = {"all": {"global", "sweden", "em"}, "sweden_only": {"sweden"}, "sweden_em": {"sweden", "em"}}
# ============================================================
# DATAHÄMTNING (FLIK 1-3: teknisk analys)
# ============================================================


raw_price = fetch_price_series(ticker)
raw_vix = fetch_vix()

technical_available = raw_price is not None and not raw_price.empty
if not technical_available:
    with tab1:
        st.error(f"Kunde inte hämta marknadsdata för {ticker}. Kontrollera börssymbolen.")
    with tab3:
        st.info("Tekniskt backtest behöver prisdata. KI-flikarna kan fortfarande användas.")
else:
    df = raw_price.copy()
    if raw_vix is not None:
        df = df.join(raw_vix, how="left")
        df["VIX"] = df["VIX"].ffill()
    else:
        df["VIX"] = np.nan
        st.warning("⚠️ VIX-data kunde inte hämtas just nu. VIX-panik-signalen kommer inte att kunna triggas.")

    df = indicators.calculate_technical_indicators(df, sma_trend_period, config.DEFAULT_RSI_PERIOD)

    sig_params = signals_mod.SignalParams(
        buy_rsi_threshold=buy_rsi_threshold,
        sell_rsi_filter=sell_macd_rsi_filter,
        vix_panic_threshold=vix_panic_threshold,
        cooldown_bars=cooldown_bars,
        use_rsi_buy=use_rsi, use_vix_buy=use_vix,
        use_macd_sell=use_macd, use_rsi_sell_filter=use_sell_rsi,
        use_trend_filter=use_trend,
    )
    # Warm up indicators on full history; cooldown and orders start inside the selected window.
    df = research.select_period(df, period_start, period_end)
    if len(df) < 2:
        with tab3:
            st.warning("Otillräcklig teknisk prishistorik under vald period.")
        technical_available = False
    df = signals_mod.generate_signals(df, sig_params)

    if technical_available:
        latest = df.iloc[-1]
        latest_price = float(latest["Close"])
        latest_vix = float(latest["VIX"]) if not np.isnan(latest["VIX"]) else None
        latest_rsi = float(latest["RSI"]) if not np.isnan(latest["RSI"]) else None
        latest_sma = float(latest["SMA"]) if not np.isnan(latest["SMA"]) else None
        trend_is_positive = (latest_sma is not None) and (latest_price > latest_sma)

        signal_rows = df[df["Signal"] != 0]
        last_signal_row = signal_rows.iloc[-1] if not signal_rows.empty else None


        def _collect_markers(sub: pd.DataFrame) -> dict:
            out = {"buy_neg": ([], []), "buy_pos": ([], []), "sell": ([], []), "vix_buy_neg": ([], []), "vix_buy_pos": ([], [])}
            for date, row in sub.iterrows():
                sma = row["SMA"]
                pos_trend = (not np.isnan(sma)) and row["Close"] > sma
                if row["Signal"] == 1 and row["Signal_Type"] == "VIX Panik KÖP":
                    key = "vix_buy_pos" if pos_trend else "vix_buy_neg"
                elif row["Signal"] == 1:
                    key = "buy_pos" if pos_trend else "buy_neg"
                elif row["Signal"] == -1:
                    key = "sell"
                else:
                    continue
                d, p = out[key]
                d.append(date)
                p.append(row["Close"])
            return out


        markers = _collect_markers(signal_rows)

        # ------------------------------------------------------------
        # FLIK 1: TEKNISK TRENDANALYS
        # ------------------------------------------------------------
        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                trend_label = "📗 POSITIV" if trend_is_positive else "📕 NEGATIV"
                days_in_trend = int(abs(df["Streak"].iloc[-1]))
                st.metric("Nuvarande trend", trend_label, delta=f"{days_in_trend} dagar i trend", help=config.EXPLANATIONS["trend"])
            with c2:
                st.metric("RSI (14)", f"{latest_rsi:.1f}" if latest_rsi is not None else "N/A (warm-up)", delta=f"Köp < {buy_rsi_threshold}", delta_color="off", help=config.EXPLANATIONS["rsi"])
            with c3:
                if last_signal_row is not None:
                    date_str = pd.Timestamp(last_signal_row.name).strftime("%Y-%m-%d")
                    emoji = "🟢" if "KÖP" in str(last_signal_row["Signal_Type"]) else "🔴"
                    st.metric("Senaste signal", f"{emoji} {last_signal_row['Signal_Type']}", delta=date_str, delta_color="off")
                else:
                    st.metric("Senaste signal", "Ingen signal")
            with c4:
                st.metric(f"Pris ({ticker})", f"${latest_price:.2f}")

            info_expander("sma", "rsi", "macd", "trend", "cooldown")
            st.markdown("---")

            st.subheader("🌡️ VIX-panikmätare")
            if latest_vix is not None:
                vc1, vc2 = st.columns([2, 3])
                with vc1:
                    vix_status = "Över paniktröskeln" if latest_vix > vix_panic_threshold else "✅ Normalt marknadsläge"
                    st.metric("VIX just nu", f"{latest_vix:.2f}", delta=f"{latest_vix - vix_panic_threshold:+.2f} vs tröskel", delta_color="inverse", help=config.EXPLANATIONS["vix"])
                    st.markdown(f"**Status:** {vix_status}")
                with vc2:
                    vix_pct = min(latest_vix / (vix_panic_threshold * 1.5), 1.0)
                    bar_color = "🟥" if latest_vix > vix_panic_threshold else ("🟨" if latest_vix > vix_panic_threshold * 0.75 else "🟩")
                    filled = int(vix_pct * 20)
                    st.markdown(f"**VIX-nivå:** `{bar_color * filled}{'⬜' * (20 - filled)}`")
            else:
                st.info("VIX-data är inte tillgänglig för tillfället.")

            st.markdown("---")
            fig = charts.build_trend_heatmap_chart(df, ticker, sma_trend_period, color_intensity_cap, markers)
            if not show_sma:
                for trace in fig.data:
                    if trace.name.startswith('SMA') or trace.name in ('Positiv Trend', 'Negativ Trend'):
                        trace.visible = False
            for label, cols, visible in [('RSI', ['RSI'], show_rsi), ('MACD', ['MACD', 'MACD_Signal'], show_macd), ('VIX', ['VIX'], show_vix)]:
                if visible:
                    with st.expander(f"Diagram: {label}"):
                        st.line_chart(df[cols])
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Data via Yahoo Finance · Auto-adjusted för utdelningar/split · Cache: 1 timme")

# ------------------------------------------------------------
# FLIK 2: MAKRO & KONJUNKTURMODELL
# ------------------------------------------------------------
with tab2:
    st.subheader("📊 Konjunkturbarometermodell (Konjunkturinstitutet)")
    st.markdown(
        "Konjunkturmodellen använder KI:s Barometerindikator för att identifiera extrema delar av "
        "konjunkturcykeln. Idén är **konträr**: vid mycket stark konjunktur/överhettning minskas "
        "aktieexponeringen, vid mycket svag konjunktur ökas den igen. Detta är en **långsiktig** modell "
        "och skiljer sig fundamentalt från de kortsiktiga RSI/MACD/VIX-signalerna i den tekniska modellen. "
        "Modellen är historisk och **garanterar inte** framtida resultat. Läs mer om ursprungsidén: "
        "https://cornucopia.se/2015/02/konjunkturmodellen-haller-fortfarande/"
    )
    info_expander("ki_barometer", "ki_sell", "ki_buy", "ki_months")

    df_ki = fetch_ki_barometer()
    if df_ki is None or df_ki.empty:
        st.warning("⚠️ Kunde inte hämta data från Konjunkturinstitutets API just nu. Detta kan bero på ett tillfälligt driftstopp hos statistik.konj.se. Försök ladda om sidan senare.")
    else:
        secondary_df = fetch_price_series(config.SWEDEN_ORIGINAL_TICKER)

        ki_params_sidebar = ki_model.KiParams(
            sell_threshold=ki_sell_threshold,
            buy_threshold=ki_buy_threshold,
            duration_months=ki_duration_months,
            floor_threshold=ki_buy_threshold,
            buyback_rule=ki_buyback_rule,
        )
        ki_signals_monthly = ki_model.generate_ki_signals(df_ki["Barometer"], ki_params_sidebar)

        ki_daily = ki_signals_monthly.reindex(pd.date_range(ki_signals_monthly.index.min(), df_ki.index.max(), freq="D"))
        ki_daily["Barometer"] = ki_daily["Barometer"].ffill()
        if secondary_df is not None and not secondary_df.empty:
            df_combo = secondary_df[["Close"]].join(ki_daily["Barometer"], how="left").ffill().dropna()
        else:
            df_combo = pd.DataFrame({"Close": 100., "Barometer": ki_daily["Barometer"]}, index=ki_daily.index)
            st.caption("Sverigepris saknas; prisjämförelsen visas som en konstant referens.")

        k1, k2, k3 = st.columns(3)
        with k1:
            latest_ki = float(df_ki["Barometer"].iloc[-1])
            status = "🔴 ÖVERHETTNING" if latest_ki > ki_sell_threshold else ("🟢 LÅGKONJUNKTUR" if latest_ki < ki_buy_threshold else "⚪ NEUTRAL")
            st.metric("Barometerindikator", f"{latest_ki:.1f}", delta=status, delta_color="off")
        with k2:
            st.metric("Senaste KI-månad", pd.Timestamp(df_ki.index[-1]).strftime("%Y-%m"))
        with k3:
            sig_hist = ki_signals_monthly[ki_signals_monthly["Signal"] != 0]
            if not sig_hist.empty:
                last = sig_hist.iloc[-1]
                emoji = "🟢" if last["Signal"] == 1 else "🔴"
                st.metric("Senaste KI-signal", f"{emoji} {last['Signal_Type']}", delta=pd.Timestamp(sig_hist.index[-1]).strftime("%Y-%m"), delta_color="off")
            else:
                st.metric("Senaste KI-signal", "Ingen signal")

        st.markdown("---")
        buy_dates = ki_signals_monthly[ki_signals_monthly["Signal"] == 1].index
        sell_dates = ki_signals_monthly[ki_signals_monthly["Signal"] == -1].index
        df_combo = research.select_period(df_combo, period_start, period_end)
        if not df_combo.empty:
            buy_dates = buy_dates[(buy_dates >= df_combo.index.min()) & (buy_dates <= df_combo.index.max())]
            sell_dates = sell_dates[(sell_dates >= df_combo.index.min()) & (sell_dates <= df_combo.index.max())]
        fig_ki = charts.build_ki_chart(df_combo, config.SWEDEN_ORIGINAL_TICKER, ki_sell_threshold, ki_buy_threshold, buy_dates, sell_dates)
        st.plotly_chart(fig_ki, use_container_width=True)
        st.caption(
            f"KI-data datumstämplas vid månadsslut och antas tillgänglig först {config.KI_PUBLICATION_LAG_DAYS} "
            "dagar senare (schablon). Historiska värden kan vara reviderade; testet återskapar inte säkert dåtidens information. Markörerna här visar signalmånader, inte handelsdagar."
        )

# ------------------------------------------------------------
# FLIK 3: TEKNISK BACKTEST
# ------------------------------------------------------------
if technical_available:
    with tab3:
        st.subheader("📊 Kvantitativ backtest: Signalmodell vs. Buy & Hold")
        st.markdown(
            "Signaler exekveras **tidigast nästa handelsdag** efter att de uppstått (ingen retroaktiv handel). "
            f"Execution-metod: **{execution_method_label}**. Courtage: **{cost_bps:.0f} bps**, slippage: **{slippage_bps:.0f} bps**."
        )

        exec_params = backtest.ExecutionParams(
            initial_capital=initial_capital, cost_bps=cost_bps, slippage_bps=slippage_bps, execution_method=execution_method, require_sma=False
        )
        bt = backtest.run_technical_backtest(df, exec_params)

        if bt is None:
            st.warning("Otillräcklig historisk data för att genomföra backtestet med vald SMA-period.")
        else:
            st.caption(f"Faktisk teknisk testperiod: {bt['equity'].index.min().date()} till {bt['equity'].index.max().date()} · USD")
            st.caption(f"Längsta tid under tidigare topp: {research.longest_underwater_days(bt['equity'])} kalenderdagar · Avslutade affärer: {sum(t['status'] == 'closed' for t in bt['trades'])}")
            strat_report = metrics.build_risk_report(bt["equity"], bt["position"], bt["trades"], risk_free_annual=tech_risk_free)
            bnh_position = pd.Series(1, index=bt["bnh_equity"].index)
            bnh_report = metrics.build_risk_report(bt["bnh_equity"], bnh_position, [], risk_free_annual=tech_risk_free)

            st.markdown("#### Avkastning")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Totalavkastning (Strategi)", fmt_pct(strat_report.total_return_pct), delta=f"{strat_report.total_return_pct - bnh_report.total_return_pct:+.1f} procentenheter mot köp och behåll", help=config.EXPLANATIONS["total_return"])
            m1.caption(f"Slutvärde: **${strat_report.final_value:,.0f}**")
            m2.metric("Totalavkastning (Buy & Hold)", fmt_pct(bnh_report.total_return_pct), delta="Referens", delta_color="off")
            m2.caption(f"Slutvärde: **${bnh_report.final_value:,.0f}**")
            m3.metric("CAGR (Strategi)", fmt_ratio(strat_report.cagr_pct) + " %/år", delta=fmt_pct(strat_report.cagr_pct - bnh_report.cagr_pct, 2), help=config.EXPLANATIONS["cagr"])
            m4.metric("CAGR (Buy & Hold)", fmt_ratio(bnh_report.cagr_pct) + " %/år", delta="Referens", delta_color="off")

            st.markdown("#### Risk")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Max Drawdown (Strategi)", fmt_pct(strat_report.max_drawdown_pct), help=config.EXPLANATIONS["mdd"])
            r2.metric("Max Drawdown (Buy & Hold)", fmt_pct(bnh_report.max_drawdown_pct))
            r3.metric("Sharpe Ratio", fmt_ratio(strat_report.sharpe), help=config.EXPLANATIONS["sharpe"])
            r4.metric("Sortino Ratio", fmt_ratio(strat_report.sortino), help=config.EXPLANATIONS["sortino"])

            st.markdown("#### Affärer & exponering")
            ts = strat_report.trade_stats
            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Avslutade affärer", ts.n_closed)
            a2.metric("Öppna affärer", ts.n_open)
            a3.metric("Win Rate", fmt_ratio(ts.win_rate_pct, 1) + " %" if ts.win_rate_pct is not None else "N/A", help=config.EXPLANATIONS["win_rate"])
            a4.metric("Profit Factor", metrics.format_profit_factor(ts.profit_factor), help=config.EXPLANATIONS["profit_factor"])
            st.caption(f"Marknadsexponering: **{strat_report.exposure_pct:.1f} %** · Calmar Ratio: **{fmt_ratio(strat_report.calmar)}**")

            info_expander("cagr", "total_return", "mdd", "sharpe", "sortino", "calmar", "win_rate", "profit_factor", "exposure", "slippage", "cost")

            st.markdown("---")
            strat_dd = metrics.compute_drawdown(bt["equity"].to_numpy())
            bnh_dd = metrics.compute_drawdown(bt["bnh_equity"].to_numpy())
            fig_bt = charts.build_equity_drawdown_chart(bt["equity"], bt["bnh_equity"], strat_dd, bnh_dd, "Aktiv Signalmodell")
            charts.add_transactions(fig_bt, bt["equity"], charts.technical_events(bt["trades"]), bt["position"])
            st.caption("Grön bakgrund: investerad. Grå: kassa. Markörer och streckade linjer visar genomförda affärer. Hovra för signal- och executionsdatum.")
            st.plotly_chart(fig_bt, use_container_width=True)

            if bt["trades"]:
                with st.expander("📋 Detaljerad affärslogg (avslutade och ev. öppen affär visas separat)"):
                    st.dataframe(charts.trade_log(bt["trades"]), use_container_width=True, hide_index=True)
                    st.caption("Avkastning visar kursförändring; Resultat i USD inkluderar courtage. Öppna affärer visar orealiserad avkastning och saknar säljdatum.")

# ------------------------------------------------------------
# FLIK 4: KI-PORTFÖLJBACKTEST
# ------------------------------------------------------------
with tab4:
    st.subheader("🏦 KI-portföljbacktest: Konjunkturmodellen som allokeringsstrategi")
    st.markdown(
        "Detta är en **helt separat backtestmotor** från den tekniska modellen ovan. Den testar hur "
        "Konjunkturmodellen fungerar som strategi för att allokera om en bred, global portfölj - "
        "**inte** som en signal för en enskild aktie."
    )
    info_expander("currency", "rebalance", "ki_scope", "derisk_pct", "risk_free")

    if weight_sum != 100:
        st.error("Portföljvikterna ovan summerar inte till 100 %. Justera dem för att köra backtesten.")
    else:
        proxy_symbols = {k: v["ticker"] for k, v in config.PORTFOLIO_PROXIES.items() if k in base_weights}
        st.caption("Proxys som används: " + " · ".join(f"**{k}** = {v['label']}" for k, v in config.PORTFOLIO_PROXIES.items() if k in base_weights))

        raw_prices = {k: fetch_price_series(sym) for k, sym in proxy_symbols.items()}
        fx = fetch_fx_rate()

        missing = [k for k, v in raw_prices.items() if v is None or v.empty]
        if missing:
            st.error(f"❌ Kunde inte hämta data för: {', '.join(missing)}. KI-portföljbacktesten kan inte köras just nu.")
        elif fx is None or fx.empty:
            st.error("❌ Kunde inte hämta USD/SEK-växelkurs. KI-portföljbacktesten kan inte köras just nu.")
        elif df_ki is None or df_ki.empty:
            st.error("❌ KI-barometerdata saknas (se KI-modellen – Konjunktur). KI-portföljbacktesten kan inte köras just nu.")
        else:
            prices_sek = {k: portfolio.to_common_currency(v["Close"], fx) for k, v in raw_prices.items()}
            full_prices = portfolio.align_prices(prices_sek)
            prices_df = research.select_period(full_prices, period_start, period_end)
            if len(prices_df) < 2:
                st.error("Otillräcklig gemensam historik efter valutakonvertering; minst två datum krävs.")
                st.stop()
            st.warning("KI-resultatet kan bygga på få konjunkturcykler. Perioden begränsas endast av tillgångar med positiv vikt samt valutadata. Se faktisk period nedan.")
            with st.expander("Data och antaganden"):
                st.write(f"KI: senast hämtade historiska serie, som kan vara reviderad. Antagen tillgänglighet: månadsslut + {config.KI_PUBLICATION_LAG_DAYS} kalenderdagar; handel tidigast följande handelsdag. Detta är inte verifierade historiska publiceringsdatum och undanröjer inte effekten av reviderade värden.")
                st.markdown("[KI: data uppdateras vid publicering](https://www.konj.se/statistik-och-data/) · [KI: indikatorer revideras varje månad](https://www.konj.se/publikationer/konjunkturbarometern/2026-09-29-kraftigt-forbattrat-stamningslage-hos-hushallen/)")
                st.caption("Startallokering följer senast kända KI-/trendbeslut före perioden. Saknas tidigare beslut startar KI-portföljen fullt investerad. Teknisk strategi startar i kassa. Kassa i KI får vald schablonränta; historisk kortränta används inte.")
            st.caption(f"Faktisk backteststart och slut: {prices_df.index.min().date()} till {prices_df.index.max().date()} · Basvaluta: {config.DEFAULT_BASE_CURRENCY}")

            st.caption(f"Kostnad per omsatt aktievärde: courtage {pf_cost_bps:g} + slippage {pf_slippage_bps:g} bps, även initialköp och Buy & Hold-rebalansering. Riskfri ränta: {risk_free_annual:.1%}.")

            ki_params_sidebar = ki_model.KiParams(
                sell_threshold=pf_ki_sell_threshold, buy_threshold=pf_ki_buy_threshold,
                duration_months=pf_ki_duration_months, floor_threshold=pf_ki_floor_threshold, buyback_rule=pf_ki_buyback_rule,
            )
            ki_signals_monthly = ki_model.generate_ki_signals(df_ki["Barometer"], ki_params_sidebar)
            sweden_raw = raw_prices.get('sweden')
            if sweden_raw is None:
                sweden_raw = fetch_price_series(config.SWEDEN_ORIGINAL_TICKER)
            sweden_reference = None if sweden_raw is None or sweden_raw.empty else portfolio.to_common_currency(sweden_raw['Close'], fx).dropna()
            if pf_trend and (sweden_reference is None or sweden_reference.empty):
                st.error("Trendfiltret kräver Sverigepris och valutadata. Stäng av filtret eller försök igen.")
                st.stop()

            def execution_for(monthly, use_filter=None):
                orders = ki_model.map_signals_to_trading_days(monthly, full_prices.index)
                if (pf_trend if use_filter is None else use_filter):
                    orders = research.trend_orders(orders, sweden_reference, full_prices.index)
                return research.orders_for_period(orders, prices_df.index)

            ki_exec_signals = execution_for(ki_signals_monthly)

            pf_params = portfolio.PortfolioParams(
                base_weights=base_weights, rebalance_freq=rebalance_freq, scope_keys=scope_key_map[ki_scope],
                derisk_pct=float(derisk_pct), interest_mode=interest_mode, annual_interest_rate=annual_interest_rate,
                cost_bps=pf_cost_bps, slippage_bps=pf_slippage_bps,
                initial_capital=portfolio_initial_capital, apply_ki=True,
            )
            result = portfolio.run_ki_vs_bnh(prices_df, ki_exec_signals, pf_params)
            ki_res, bnh_res = result["ki"], result["bnh"]

            ki_pos = pd.Series((1.0 - ki_res["weights"]["cash"]).to_numpy(), index=ki_res["equity"].index)
            bnh_pos = pd.Series((1.0 - bnh_res["weights"]["cash"]).to_numpy(), index=bnh_res["equity"].index)
            ki_report = metrics.build_risk_report(ki_res["equity"], (ki_pos > 0).astype(int), [], risk_free_annual=risk_free_annual)
            bnh_report = metrics.build_risk_report(bnh_res["equity"], (bnh_pos > 0).astype(int), [], risk_free_annual=risk_free_annual)
            ki_exposure = float(ki_pos.mean() * 100.0)
            bnh_exposure = float(bnh_pos.mean() * 100.0)

            st.markdown(f"#### Huvudjämförelse: {w_global}% Global / {w_sweden}% Sverige / {w_em}% Emerging Markets")
            value1, value2 = st.columns(2)
            value1.metric("Slutvärde KI-strategi", f"{ki_report.final_value:,.0f} kr")
            value2.metric("Slutvärde köp och behåll", f"{bnh_report.final_value:,.0f} kr")
            st.caption(f"Avslutade sälj–återköpscykler: {research.completed_cycles(ki_res['events'])} · Längsta tid under tidigare topp: KI {research.longest_underwater_days(ki_res['equity'])} dagar / köp och behåll {research.longest_underwater_days(bnh_res['equity'])} dagar (kalenderdagar, även pågående nedgång). Startallokering räknas inte som en affärscykel.")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Totalavkastning (KI-strategi)", fmt_pct(ki_report.total_return_pct), delta=f"{ki_report.total_return_pct - bnh_report.total_return_pct:+.1f} procentenheter mot köp och behåll")
            m1.caption(f"Slutvärde: **{ki_report.final_value:,.0f} kr**")
            m2.metric("Totalavkastning (Buy & Hold)", fmt_pct(bnh_report.total_return_pct), delta="Referens", delta_color="off")
            m2.caption(f"Slutvärde: **{bnh_report.final_value:,.0f} kr**")
            m3.metric("CAGR (KI-strategi)", fmt_ratio(ki_report.cagr_pct) + " %/år")
            m4.metric("CAGR (Buy & Hold)", fmt_ratio(bnh_report.cagr_pct) + " %/år")

            r1, r2 = st.columns(2)
            r1.metric("Max Drawdown (KI)", fmt_pct(ki_report.max_drawdown_pct))
            r2.metric("Max Drawdown (B&H)", fmt_pct(bnh_report.max_drawdown_pct))
            with st.expander("Fördjupning – riskjusterade mått"):
                r3, r4 = st.columns(2)
                r3.metric("Sharpe (KI) / (B&H)", f"{fmt_ratio(ki_report.sharpe)} / {fmt_ratio(bnh_report.sharpe)}")
                r4.metric("Calmar (KI) / (B&H)", f"{fmt_ratio(ki_report.calmar)} / {fmt_ratio(bnh_report.calmar)}")
            st.caption(f"Tid i aktier — KI: **{ki_exposure:.1f} %**, B&H: **{bnh_exposure:.1f} %** · Tid defensivt/räntekonto — KI: **{100 - ki_exposure:.1f} %**, B&H: **{100 - bnh_exposure:.1f} %**")

            st.markdown("---")
            strat_dd = metrics.compute_drawdown(ki_res["equity"].to_numpy(), portfolio_initial_capital)
            bnh_dd = metrics.compute_drawdown(bnh_res["equity"].to_numpy(), portfolio_initial_capital)
            fig_pf = charts.build_equity_drawdown_chart(ki_res["equity"], bnh_res["equity"], strat_dd, bnh_dd, "KI-portfölj")
            charts.add_transactions(fig_pf, ki_res["equity"], charts.portfolio_events(ki_res["events"]), ki_res["risk_multiplier"])
            st.plotly_chart(fig_pf, use_container_width=True)
            st.caption("Grön bakgrund: fullt investerad. Grå: avriskat läge. Markörerna visar faktiska omallokeringar; hovra för datum, aktieandelar och belopp. Avriskningsprocenten gäller vald portföljdel.")

            with st.expander("Affärslogg – varför köpte eller sålde modellen?"):
                if ki_res['events']:
                    st.dataframe(research.ki_trade_log(ki_res['events']), use_container_width=True, hide_index=True)
                else:
                    st.caption("Inga omallokeringar efter startdagen under perioden.")
                st.caption(f"Startläge: {ki_res['weights']['cash'].iloc[0]:.1%} räntekonto. Signalmånad och antaget publiceringsdatum visas separat från handelsdagen.")

            fig_ind = charts.build_ki_indicator_chart(research.select_period(ki_signals_monthly, prices_df.index.min(), prices_df.index.max()), pf_ki_sell_threshold, pf_ki_buy_threshold, pf_ki_effective_floor)
            st.plotly_chart(fig_ind, use_container_width=True)

            with st.expander("Fördjupning – portföljsammansättning"):
                label_map = {k: config.PORTFOLIO_PROXIES[k]["label"].split(" (")[0] for k in base_weights} | {"cash": "Räntekonto"}
                fig_alloc = charts.build_allocation_chart(ki_res["weights"], label_map)
                st.plotly_chart(fig_alloc, use_container_width=True)

            with st.expander("Fördjupning – resultat per portföljdel"):
                rows = []
                for key in list(base_weights.keys()) + ["cash"]:
                    ki_series = ki_res["components"][key]
                    bnh_series = bnh_res["components"][key]
                    rows.append(
                        {
                            "Del": label_map.get(key, key),
                            "Buy & Hold totalavk.": fmt_pct(metrics.total_return(bnh_series)),
                            "KI-styrd totalavk.": fmt_pct(metrics.total_return(ki_series)),
                        }
                    )
                rows.append(
                    {"Del": "Total portfölj", "Buy & Hold totalavk.": fmt_pct(bnh_report.total_return_pct), "KI-styrd totalavk.": fmt_pct(ki_report.total_return_pct)}
                )
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                st.caption(
                    "OBS: Eftersom kapital flyttas mellan delarna vid rebalansering/KI-signaler är dessa "
                    "kurvor inte renodlade 'köp och behåll enbart den tillgången'-kurvor, utan visar respektive "
                    "sleeves faktiska bidrag inom den simulerade portföljen."
                )

            with st.expander("Fördjupning – avriskningsgrad × återköpsregel"):
                st.caption("Historisk jämförelse - optimera INTE parametrarna mot denna tabell och förvänta dig samma resultat framåt.")
                sweep_rows = []
                for rule_key, rule_label in config.KI_BUYBACK_RULES.items():
                    sig_monthly_rule = ki_model.generate_ki_signals(
                        df_ki["Barometer"],
                        ki_model.KiParams(pf_ki_sell_threshold, pf_ki_buy_threshold, pf_ki_duration_months, pf_ki_floor_threshold, rule_key),
                    )
                    exec_rule = execution_for(sig_monthly_rule)
                    for lvl in config.DERISK_LEVELS:
                        if lvl == 0:
                            continue
                        p = portfolio.PortfolioParams(
                            base_weights=base_weights, rebalance_freq=rebalance_freq, scope_keys=scope_key_map[ki_scope],
                            derisk_pct=float(lvl), interest_mode=interest_mode, annual_interest_rate=annual_interest_rate,
                            cost_bps=pf_cost_bps, slippage_bps=pf_slippage_bps,
                            initial_capital=portfolio_initial_capital, apply_ki=True,
                        )
                        res = portfolio.simulate_portfolio(prices_df, exec_rule, p)
                        sweep_rows.append(
                            {
                                "Avriskning": f"{lvl} %",
                                "Återköpsregel": rule_label,
                                "CAGR": fmt_ratio(metrics.cagr(res["equity"])) + " %",
                                "Max DD": fmt_ratio(metrics.max_drawdown(res["equity"])) + " %",
                                "Sharpe": fmt_ratio(metrics.sharpe_ratio(res["equity"], risk_free_annual=risk_free_annual)),
                                "Sortino": fmt_ratio(metrics.sortino_ratio(res["equity"], risk_free_annual=risk_free_annual)),
                                "Calmar": fmt_ratio(metrics.calmar_ratio(res["equity"])),
                                "Slutvärde": f"{res['equity'].iloc[-1]:,.0f} kr",
                            }
                        )
                sweep_df = pd.DataFrame(sweep_rows)
                st.dataframe(sweep_df, use_container_width=True, hide_index=True)
                st.caption("Tabellen markerar avsiktligt INTE en enskild 'bästa' rad - jämför gärna både CAGR och de riskjusterade måtten (Sharpe/Sortino/Calmar).")

            with st.expander("Fördjupning – KI med och utan trendfilter"):
                st.caption("Samma period, kostnader och KI-inställningar. Endast trendvillkoret ändras. Filtret väntar på föregående dags Sverigepris i SEK över SMA 200; det kan ge senare återköp.")
                if sweden_reference is None or sweden_reference.empty:
                    st.info("Sverigedata saknas för trendjämförelsen.")
                else:
                    variants = []
                    for use_filter in (False, True):
                        variant = portfolio.simulate_portfolio(prices_df, execution_for(ki_signals_monthly, use_filter), pf_params)
                        variants.append({"Strategi": "KI + trendfilter" if use_filter else "Enbart KI",
                                         "Slutvärde (kr)": variant['equity'].iloc[-1],
                                         "Årsavkastning (%)": metrics.cagr(variant['equity']),
                                         "Största nedgång (%)": metrics.max_drawdown(variant['equity']),
                                         "Avslutade cykler": research.completed_cycles(variant['events'])})
                    st.dataframe(pd.DataFrame(variants), use_container_width=True, hide_index=True)

            st.markdown("---")
            if w_sweden != 100:
                with st.expander("Fördjupning – Sverige under samma period"):
                    st.caption("Samma handelsdagar, KI-regel, trendfilter och kostnader som huvudjämförelsen. Här tillämpas avriskningen på Sverige.")
                    sweden_only_prices = None
                    if sweden_reference is not None:
                        sweden_only_prices = sweden_reference.reindex(sweden_reference.index.union(prices_df.index)).sort_index().ffill().reindex(prices_df.index).to_frame('sweden')
                    if sweden_only_prices is None or sweden_only_prices.isna().any().any():
                        st.info("Sverigedata täcker inte hela den valda perioden. Ingen jämförelse med annan period visas.")
                    else:
                        st.caption(f"Sverigejämförelsens faktiska period: {prices_df.index.min().date()} till {prices_df.index.max().date()}.")
                        sweden_params = portfolio.PortfolioParams(
                            base_weights={'sweden': 1.0}, rebalance_freq=rebalance_freq, scope_keys={'sweden'},
                            derisk_pct=float(derisk_pct), interest_mode=interest_mode, annual_interest_rate=annual_interest_rate,
                            cost_bps=pf_cost_bps, slippage_bps=pf_slippage_bps, initial_capital=portfolio_initial_capital)
                        sweden_result = portfolio.run_ki_vs_bnh(sweden_only_prices, ki_exec_signals, sweden_params)
                        s1, s2, s3, s4 = st.columns(4)
                        s1.metric("CAGR KI-strategi Sverige", fmt_ratio(metrics.cagr(sweden_result['ki']['equity'])) + " %/år")
                        s2.metric("CAGR Sverige Buy & Hold", fmt_ratio(metrics.cagr(sweden_result['bnh']['equity'])) + " %/år")
                        s3.metric("Max DD KI-strategi", fmt_ratio(metrics.max_drawdown(sweden_result['ki']['equity'])) + " %")
                        s4.metric("Max DD Buy & Hold", fmt_ratio(metrics.max_drawdown(sweden_result['bnh']['equity'])) + " %")

# ------------------------------------------------------------
# FLIK 5: OM MODELLERNA
# ------------------------------------------------------------
with st.expander("ℹ️ Om modellerna"):
    st.subheader("ℹ️ Om modellerna i appen")
    st.markdown(
        """
Appen innehåller tre principiellt olika angreppssätt, som **inte** ska blandas ihop:

**1. Teknisk RSI/VIX/MACD-modell (flik 1 & 2)**
Kortsiktig, tillgångsspecifik modell som reagerar på pris, momentum och volatilitet för en enskild
ticker. Signaler genereras dagligen och exekveras tidigast nästa handelsdag.

**2. KI/Konjunkturmodellen (flik 3 & 4)**
Långsiktig, konträr makromodell baserad på Konjunkturinstitutets Barometerindikator (månadsdata).
Används här som en portföljallokeringsstrategi mellan en bred aktieportfölj och ett räntekonto -
inte som en signal för enskilda aktier.

**3. Buy & Hold**
Passiv referensportfölj med samma målvikter och samma rebalanseringsschema som KI-strategin, men
utan några aktiva allokeringsbeslut. Detta är benchmarken som avgör om KI-modellen historiskt
tillfört något värde utöver att bara äga portföljen rakt av.

Samtliga backtester bygger på historisk data och **garanterar inte** framtida resultat. Se README.md
för fullständig dokumentation av antaganden, datakällor och begränsningar.
        """
    )
