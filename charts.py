# ============================================================
# charts.py
# ------------------------------------------------------------
# Bygger Plotly-figurer. Inga Streamlit-anrop här - varje
# funktion returnerar en go.Figure som app.py sedan renderar
# med st.plotly_chart().
# ============================================================

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

COMMON_LAYOUT = dict(
    hovermode="x unified",
    margin=dict(l=10, r=10, t=60, b=10),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
GRID = dict(showgrid=True, gridcolor="rgba(128,128,128,0.2)")


def build_trend_heatmap_chart(df: pd.DataFrame, ticker: str, sma_period: int, color_cap: int, signal_markers: dict) -> go.Figure:
    fig = go.Figure()

    pos_mask = df["Streak"] > 0
    fig.add_trace(
        go.Bar(
            x=df.index[pos_mask],
            y=(df["Close"] - df["SMA"])[pos_mask],
            base=df["SMA"][pos_mask],
            marker=dict(color=df["Streak"][pos_mask], colorscale=[[0, "#e6ffe6"], [1, "#004d00"]], cmin=0, cmax=color_cap, line_width=0),
            name="Positiv Trend",
            hoverinfo="skip",
        )
    )
    neg_mask = df["Streak"] < 0
    fig.add_trace(
        go.Bar(
            x=df.index[neg_mask],
            y=(df["Close"] - df["SMA"])[neg_mask],
            base=df["SMA"][neg_mask],
            marker=dict(color=df["Streak"][neg_mask].abs(), colorscale=[[0, "#ffe6e6"], [1, "#800000"]], cmin=0, cmax=color_cap, line_width=0),
            name="Negativ Trend",
            hoverinfo="skip",
        )
    )
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA"], mode="lines", name=f"SMA {sma_period}", line=dict(color="#3498db", width=1.2)))
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", name=f"Pris ({ticker})", line=dict(color="#f1c40f", width=1.8)))

    marker_style = {
        "buy_neg": dict(symbol="triangle-up", color="rgba(46, 204, 113, 0.8)", size=10, line=dict(color="black", width=1)),
        "buy_pos": dict(symbol="triangle-up", color="#00d2d3", size=12, line=dict(color="white", width=1)),
        "sell": dict(symbol="triangle-down", color="rgba(231, 76, 60, 0.85)", size=10, line=dict(color="black", width=1)),
        "vix_buy_neg": dict(symbol="diamond", color="#1dd1a1", size=14, line=dict(color="black", width=1.5)),
        "vix_buy_pos": dict(symbol="diamond", color="#ff9ff3", size=14, line=dict(color="white", width=1.5)),
    }
    names = {
        "buy_neg": "Köp (Negativ Trend)",
        "buy_pos": "Köp (Positiv Trend)",
        "sell": "MACD Vändning (Sälj)",
        "vix_buy_neg": "VIX Panik (Negativ Trend)",
        "vix_buy_pos": "VIX Panik (Positiv Trend)",
    }
    for key, style in marker_style.items():
        dates_, prices_ = signal_markers.get(key, ([], []))
        fig.add_trace(go.Scatter(x=dates_, y=prices_, mode="markers", name=names[key], marker=style))

    fig.update_layout(yaxis_title="Pris", bargap=0, **COMMON_LAYOUT)
    fig.update_xaxes(rangeslider=dict(visible=False), type="date", **GRID)
    fig.update_yaxes(**GRID)
    return fig


def build_ki_chart(df_combo: pd.DataFrame, ticker: str, sell_threshold: float, buy_threshold: float, buy_dates, sell_dates) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if df_combo.empty:
        return fig

    normalized = (df_combo["Close"] / df_combo["Close"].iloc[0]) * 100.0
    fig.add_trace(go.Scatter(x=df_combo.index, y=normalized, mode="lines", name=f"{ticker} (Bas 100)", line=dict(color="#f1c40f", width=1.8)), secondary_y=False)

    fig.add_trace(
        go.Scatter(x=df_combo.index, y=df_combo["Barometer"], mode="lines", name="Barometerindikator (KI)", line=dict(color="rgba(180,180,180,0.7)", width=2)),
        secondary_y=True,
    )
    fig.add_hline(y=sell_threshold, line_dash="dash", line_color="rgba(231,76,60,0.8)", annotation_text=f"Sälj ({sell_threshold})", annotation_position="top left", secondary_y=True)
    fig.add_hline(y=buy_threshold, line_dash="dash", line_color="rgba(46,204,113,0.8)", annotation_text=f"Köp ({buy_threshold})", annotation_position="bottom left", secondary_y=True)

    if len(buy_dates) > 0:
        buy_y = [normalized.iloc[min(normalized.index.searchsorted(d), len(normalized) - 1)] for d in buy_dates]
        fig.add_trace(go.Scatter(x=buy_dates, y=buy_y, mode="markers", name="KÖP (KI-signal)", marker=dict(symbol="triangle-up", color="#2ecc71", size=14, line=dict(color="black", width=1.5))), secondary_y=False)
    if len(sell_dates) > 0:
        sell_y = [normalized.iloc[min(normalized.index.searchsorted(d), len(normalized) - 1)] for d in sell_dates]
        fig.add_trace(go.Scatter(x=sell_dates, y=sell_y, mode="markers", name="SÄLJ (KI-signal)", marker=dict(symbol="triangle-down", color="#e74c3c", size=14, line=dict(color="black", width=1.5))), secondary_y=False)

    fig.update_layout(**COMMON_LAYOUT)
    fig.update_yaxes(title_text="Normaliserat Pris (Start = 100)", secondary_y=False, **GRID)
    fig.update_yaxes(title_text="Barometerindikator", secondary_y=True, showgrid=False)
    fig.update_xaxes(**GRID)
    return fig


def build_equity_drawdown_chart(strategy_equity: pd.Series, bnh_equity: pd.Series, strategy_dd, bnh_dd, strategy_name: str = "Strategi") -> go.Figure:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.65, 0.35], subplot_titles=["Portföljens kapitalutveckling", "Historisk Drawdown (%)"])

    fig.add_trace(go.Scatter(x=strategy_equity.index, y=strategy_equity.values, mode="lines", name=strategy_name, line=dict(color="#00d2d3", width=2.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=bnh_equity.index, y=bnh_equity.values, mode="lines", name="Köp & Behåll (Buy & Hold)", line=dict(color="rgba(149,165,166,0.8)", width=1.5, dash="dash")), row=1, col=1)

    fig.add_trace(go.Scatter(x=strategy_equity.index, y=strategy_dd, mode="lines", name=f"Drawdown: {strategy_name}", line=dict(color="#e74c3c", width=1.5), fill="tozeroy", fillcolor="rgba(231,76,60,0.15)"), row=2, col=1)
    fig.add_trace(go.Scatter(x=bnh_equity.index, y=bnh_dd, mode="lines", name="Drawdown: Buy & Hold", line=dict(color="rgba(127,140,141,0.6)", width=1.2, dash="dot"), fill="tozeroy", fillcolor="rgba(127,140,141,0.08)"), row=2, col=1)

    fig.update_layout(xaxis2=dict(type="date"), **COMMON_LAYOUT)
    fig.update_yaxes(title_text="Portföljvärde", row=1, col=1, **GRID)
    fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1, **GRID)
    fig.update_xaxes(**GRID)
    return fig


def build_allocation_chart(weights_df: pd.DataFrame, label_map: dict) -> go.Figure:
    fig = go.Figure()
    for col in weights_df.columns:
        fig.add_trace(go.Scatter(x=weights_df.index, y=weights_df[col] * 100.0, mode="lines", stackgroup="one", name=label_map.get(col, col)))
    fig.update_layout(yaxis_title="Andel av portföljen (%)", **COMMON_LAYOUT)
    fig.update_xaxes(**GRID)
    fig.update_yaxes(range=[0, 100], **GRID)
    return fig


def build_ki_indicator_chart(ki_signals: pd.DataFrame, sell_threshold: float, buy_threshold: float, floor_threshold: float) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ki_signals.index, y=ki_signals["Barometer"], mode="lines", name="Barometerindikator", line=dict(color="#3498db", width=2)))
    fig.add_hline(y=sell_threshold, line_dash="dash", line_color="rgba(231,76,60,0.8)", annotation_text=f"Säljgräns ({sell_threshold})")
    fig.add_hline(y=buy_threshold, line_dash="dash", line_color="rgba(46,204,113,0.8)", annotation_text=f"Köpgräns ({buy_threshold})")
    fig.add_hline(y=floor_threshold, line_dash="dot", line_color="rgba(149,165,166,0.6)", annotation_text=f"Golv för återköp ({floor_threshold})")

    sells = ki_signals[ki_signals["Signal"] == -1]
    buys = ki_signals[ki_signals["Signal"] == 1]
    fig.add_trace(go.Scatter(x=sells.index, y=sells["Barometer"], mode="markers", name="▼ KI AVRISKNING", marker=dict(symbol="triangle-down", color="#e74c3c", size=13, line=dict(color="black", width=1))))
    fig.add_trace(go.Scatter(x=buys.index, y=buys["Barometer"], mode="markers", name="▲ KI ÅTERKÖP", marker=dict(symbol="triangle-up", color="#2ecc71", size=13, line=dict(color="black", width=1))))

    fig.update_layout(yaxis_title="Barometerindikator", **COMMON_LAYOUT)
    fig.update_xaxes(**GRID)
    fig.update_yaxes(**GRID)
    return fig


def technical_events(trades):
    events = []
    for trade in trades:
        for side, prefix in ((1, "entry"), (-1, "exit")):
            if side == -1 and trade["status"] != "closed":
                continue
            values = trade.get(prefix + "_indicators", {})
            events.append({"date": trade[prefix + "_date"], "signal": side,
                           "label": "▲ KÖP" if side == 1 else "▼ SÄLJ",
                           "hover": f"Signaltyp: {trade.get('signal_type') if side == 1 else trade.get('exit_signal_type')}<br>"
                           f"Signaldatum: {trade.get(prefix + '_signal_date')}<br>"
                           f"Executionsdatum: {trade[prefix + '_date']}<br>"
                           f"Executionspris: {trade[prefix + '_price']:.2f}<br>" +
                           "<br>".join(f"{k}: {v:.2f}" for k, v in values.items())})
    return events


def portfolio_events(events):
    return [{**e, "label": f"▼ AVRISKNING {e['derisk_pct']:g} %" if e['signal'] == -1 else "▲ ÅTERKÖP",
             "hover": f"{e.get('reason', 'KI-signal')}<br>KI-värde: {e['ki']:.2f}<br>Signaldatum (KI-månad): {e['signal_date']}<br>"
             f"Tillgänglig för handel: {e['available_date']}<br>Handelsdatum: {e['date']}<br>"
             f"Aktieandel före: {e['before']:.1%}<br>Aktieandel efter: {e['after']:.1%}<br>"
             f"Belopp {'till' if e['cash_change'] >= 0 else 'från'} räntekonto: {abs(e['cash_change']):,.2f} kr"}
            for e in events]


def add_transactions(fig, equity, events, invested):
    """Annotera faktiska exekveringar på kapitalserien, aldrig obekräftade signaler."""
    if len(equity) == 0:
        return fig
    state = invested.reindex(equity.index).fillna(0).to_numpy() > .999
    starts = [0] + [i for i in range(1, len(state)) if state[i] != state[i-1]]
    for start, end in zip(starts, starts[1:] + [len(state)-1]):
        fig.add_vrect(x0=equity.index[start], x1=equity.index[end],
                      fillcolor="rgba(46,204,113,0.055)" if state[start] else "rgba(140,140,140,0.045)",
                      line_width=0, layer="below", row=1, col=1)
    for side in (1, -1):
        group = [e for e in events if e['signal'] == side and e['date'] in equity.index]
        if not group:
            continue
        color = "#20bf6b" if side == 1 else "#eb3b5a"
        fig.add_trace(go.Scatter(x=[e['date'] for e in group], y=[equity.loc[e['date']] for e in group],
                                 mode="markers+text", text=[e['label'] for e in group],
                                 textposition="top center" if side == 1 else "bottom center",
                                 textfont=dict(size=13, color=color),
                                 marker=dict(size=19, symbol="triangle-up" if side == 1 else "triangle-down",
                                             color=color, line=dict(color="white", width=1)),
                                 customdata=[e['hover'] for e in group], hovertemplate="%{customdata}<extra></extra>",
                                 name="Köp / återköp" if side == 1 else "Sälj / avriskning", cliponaxis=False), row=1, col=1)
        for e in group:
            fig.add_vline(x=e['date'], line_width=1, line_dash="dash", line_color=color, row=1, col=1)
    fig.update_layout(hovermode="closest", height=650,
                      legend=dict(orientation="h", yanchor="top", y=-0.15, x=0),
                      margin=dict(l=10, r=10, t=55, b=110))
    return fig


def trade_log(trades):
    rows = []
    for t in trades:
        closed = t['status'] == 'closed'
        rows.append({"Signaldatum köp": t.get('entry_signal_date'), "Köpdatum": t['entry_date'],
                     "Köpsignal": t['signal_type'], "Köpkurs": t['entry_price'],
                     "Signaldatum sälj": t.get('exit_signal_date') if closed else None,
                     "Säljdatum": t['exit_date'] if closed else None,
                     "Säljsignal": t.get('exit_signal_type') if closed else None,
                     "Säljkurs": t['exit_price'] if closed else None,
                     "Avkastning": f"{t['return_pct']:+.2f} %", "Hålltid": f"{t['days']} dagar",
                     "Status": "Stängd" if closed else "Öppen (orealiserad)", "Resultat i USD": t['pnl']})
    return pd.DataFrame(rows)
