"""Dip-Buy verdict — the one signal that survived honest testing.

Short-term mean reversion: buying an OVERSOLD dip while the stock is still in a
longer-term uptrend (above its 200-day average) and selling into the bounce beat
random same-exit entries by ~+7 win-rate points and ~3x per-trade profit
(z=3.7 over 850 trades, 20 large-caps). It is a REAL, modest, regime-dependent
edge (works in uptrends; a downtrend dip is a falling knife).

For a given stock we replay this rule over its own history to get ITS win-rate
and typical bounce, and report whether it's in a buyable dip right now.
NOTE: only the BUY side has tested edge — 'overbought' does NOT predict drops,
so there is no symmetric sell-prediction here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ENTRY_RSI = 15
TARGET = 0.06
STOP = -0.08
MAXDAYS = 12


def _rsi2(c: pd.Series) -> np.ndarray:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).to_numpy()


def _trades(c, sma5, entries):
    out, in_t, ep, ei = [], False, 0.0, 0
    eset = set(int(x) for x in entries)
    n = len(c)
    for i in range(210, n):
        if not in_t:
            if (i - 1) in eset:
                in_t, ep, ei = True, c[i], i
        else:
            ret = c[i] / ep - 1
            if c[i] > sma5[i] or ret >= TARGET or ret <= STOP or (i - ei) >= MAXDAYS:
                out.append(ret); in_t = False
    return np.array(out)


def verdict(df: pd.DataFrame) -> dict:
    """Replay the dip-buy rule on this stock's history + report today's state."""
    c = df["close"].to_numpy(dtype=float)
    n = len(c)
    if n < 260:
        return {"available": False, "reason": "Need ~1y+ of history."}
    rsi2 = _rsi2(df["close"])
    sma200 = df["close"].rolling(200).mean().to_numpy()
    sma5 = df["close"].rolling(5).mean().to_numpy()

    cond = (rsi2 < ENTRY_RSI) & (c > sma200)
    entries = np.where(cond[210:n])[0] + 210
    trades = _trades(c, sma5, entries)
    if len(trades) < 15:
        return {"available": False, "reason": "Too few historical dips to judge this stock."}

    win = float(np.mean(trades > 0))
    wins = trades[trades > 0]
    typ_bounce = float(np.median(wins)) if len(wins) else 0.02
    avg = float(np.mean(trades))

    price = round(float(c[-1]), 2)
    active = bool(rsi2[-1] < ENTRY_RSI and c[-1] > sma200[-1])
    in_uptrend = bool(c[-1] > sma200[-1])

    out = {
        "available": True,
        "active": active,
        "in_uptrend": in_uptrend,
        "rsi2": round(float(rsi2[-1]), 0),
        "history": {
            "win_rate": round(win, 2),
            "avg_per_trade_pct": round(avg * 100, 2),
            "typical_bounce_pct": round(typ_bounce * 100, 2),
            "n_trades": int(len(trades)),
        },
        "price": price,
        "disclaimer": "A real but MODEST, uptrend-only edge (short-term reversal). Bounces are odds, "
                      "not guarantees; in a downtrend a dip is a falling knife. Buy side only — "
                      "'overbought' does not predict drops.",
    }
    if active:
        out["plan"] = {
            "buy_near": price,
            "target": round(price * (1 + typ_bounce), 2),
            "target_pct": round(typ_bounce * 100, 2),
            "stop": round(price * (1 + STOP), 2),
            "stop_pct": round(STOP * 100, 2),
        }
    return out
