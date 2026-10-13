"""Shared, testable helpers for periods, pending trend orders and diagnostics."""
from __future__ import annotations

import pandas as pd
import numpy as np


def select_period(frame, start=None, end=None):
    if start is not None and end is not None and pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError("Startdatum måste vara före eller samma dag som slutdatum.")
    return frame.loc[start:end].copy()


def trend_orders(orders, reference, calendar, window=200):
    """Hold KI buys until the PREVIOUS close exceeds its SMA. A sell cancels a pending buy.

    Run on full history before slicing the test window to preserve the starting state.
    """
    calendar = pd.DatetimeIndex(calendar)
    if orders.empty:
        return orders.copy()
    reference = reference.sort_index()
    ok = (reference > reference.rolling(window, min_periods=window).mean())
    # Reindex first, shift second: never use today's close for today's execution.
    ok = ok.reindex(calendar).fillna(False).shift(1, fill_value=False)
    incoming = {pd.Timestamp(d): row.to_dict() for d, row in orders.iterrows()}
    pending = None
    rows = []
    for d in calendar:
        order = incoming.get(d)
        if order is not None:
            if order['Signal'] == -1:
                pending = None
                rows.append(dict(order, Exec_Date=d))
            else:
                pending = order
        if pending is not None and bool(ok.loc[d]):
            rows.append(dict(pending, Exec_Date=d, Reason=str(pending.get('Reason', 'KI återköp')) +
                             f'; föregående stängning över SMA {window}'))
            pending = None
    if not rows:
        return orders.iloc[:0].copy()
    return pd.DataFrame(rows).set_index('Exec_Date')


def orders_for_period(orders, calendar):
    """Seed only the last known position before the start; do not replay old trades."""
    if len(calendar) == 0 or orders.empty:
        return orders.iloc[:0].copy()
    start, end = calendar[0], calendar[-1]
    current = orders.loc[(orders.index >= start) & (orders.index <= end)].copy()
    prior = orders.loc[orders.index < start]
    if not prior.empty and start not in current.index:
        seed = prior.iloc[[-1]].copy()
        seed.index = pd.DatetimeIndex([start], name=orders.index.name)
        seed['Reason'] = 'Startläge från senast kända KI-/trendbeslut. ' + seed.get('Reason', pd.Series('', index=seed.index)).fillna('')
        current = pd.concat([seed, current])
    return current


def longest_underwater_days(equity):
    if equity.empty:
        return 0
    peak = float(equity.attrs.get('initial_capital', equity.iloc[0]))
    peak_date = equity.index[0]
    longest = 0
    underwater = False
    for d, value in equity.items():
        if value < peak or underwater:
            longest = max(longest, (d - peak_date).days)
        underwater = value < peak
        if value >= peak:
            peak, peak_date = value, d
    return longest


def completed_cycles(events):
    pending = False
    count = 0
    for event in events:
        if event['signal'] == -1:
            pending = True
        elif event['signal'] == 1 and pending:
            count += 1
            pending = False
    return count


def ki_trade_log(events):
    return pd.DataFrame([{
        'Handelsdatum': e['date'], 'Signalmånad': e['signal_date'],
        'Antaget tillgängligt': e['available_date'],
        'Åtgärd': 'Sälj' if e['signal'] == -1 else 'Återköp',
        'KI': e['ki'], 'Förklaring': e.get('reason', ''),
        'Aktieandel före (%)': e['before'] * 100,
        'Aktieandel efter (%)': e['after'] * 100,
        'Till/från räntekonto (kr)': e['cash_change'],
    } for e in events])
