"""Strategy Lab — backtest famous rule-based strategies on ONE stock vs just
buying and holding it. Point-in-time (signals act on the PRIOR day's data, no
peeking). We report total return, the worst drawdown (peak-to-trough drop),
Sharpe (return per unit of risk), and % of time invested.

Honest by design: most strategies match buy-and-hold on return but cut the
drawdown; some lose to whipsaws. It's ONE stock and in-sample, so treat it as a
teaching tool, not proof.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services import data


def _rsi(c, p=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / p, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _walk(entry: np.ndarray, exit_: np.ndarray) -> np.ndarray:
    """In/out series: enter on prior-day entry signal, exit on prior-day exit."""
    n = len(entry)
    out = np.zeros(n)
    pos = 0
    for t in range(1, n):
        if pos == 0 and entry[t - 1]:
            pos = 1
        elif pos == 1 and exit_[t - 1]:
            pos = 0
        out[t] = pos
    return out


def _stats(r: np.ndarray, inmkt: np.ndarray) -> dict:
    sr = np.nan_to_num(r * inmkt)
    eq = np.cumprod(1 + sr)
    dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
    sharpe = (np.mean(sr) / (np.std(sr, ddof=1) + 1e-12)) * np.sqrt(252)
    return {
        "total_return": round(float((eq[-1] - 1) * 100), 1),
        "max_drawdown": round(float(dd), 1),
        "sharpe": round(float(sharpe), 2),
        "exposure": round(float(np.mean(inmkt) * 100), 0),
    }


def backtest_ticker(ticker: str, period: str = "1y") -> dict:
    if period not in ("1y", "2y", "5y"):
        period = "1y"
    # Fetch 5y so the 200-day average is already 'warm' at the start of the window,
    # then score only the chosen window (1y / 2y / 5y).
    df = data.fetch_ohlcv(ticker, period="5y", interval="1d")
    c = df["close"]
    if len(c) < 260:
        return {"available": False, "reason": "Need ~1y+ of history."}
    r = c.pct_change().to_numpy()
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    sma5 = c.rolling(5).mean()
    rsi2 = _rsi(c, 2)
    hi50 = c.rolling(50).max().shift(1)
    lo50 = c.rolling(50).min().shift(1)
    cn = c.to_numpy()

    inmkt = {
        "Buy & Hold": np.ones(len(c)),
        "200-Day Trend Filter": np.nan_to_num((c > sma200).shift(1).to_numpy().astype(float)),
        "Golden Cross (50/200)": np.nan_to_num((sma50 > sma200).shift(1).to_numpy().astype(float)),
        "Breakout (50-day high/low)": _walk((cn > hi50.to_numpy()), (cn < lo50.to_numpy())),
        "RSI-2 Dip Buy (uptrends)": _walk(
            ((rsi2 < 10) & (c > sma200)).to_numpy(), (c > sma5).to_numpy()),
    }

    # Score only the selected window (signals stay warm from the full history).
    keep = {"1y": 252, "2y": 504, "5y": len(c)}[period]
    start = max(0, len(c) - keep)
    r = r[start:]
    inmkt = {k: v[start:] for k, v in inmkt.items()}
    win_years = round(len(r) / 252, 1)

    bh = _stats(r, inmkt["Buy & Hold"])
    rows = []
    for name, im in inmkt.items():
        s = _stats(r, im)
        if name == "Buy & Hold":
            verdict = "the benchmark"
        else:
            better_dd = s["max_drawdown"] > bh["max_drawdown"] + 2     # noticeably shallower
            better_ret = s["total_return"] > bh["total_return"]
            better_sharpe = s["sharpe"] > bh["sharpe"] + 0.05
            if better_ret and better_dd:
                verdict = "beats on BOTH return & risk"
            elif better_sharpe and better_dd:
                verdict = "less drawdown, better risk-adjusted"
            elif better_dd and not better_ret:
                verdict = "lower return but much safer"
            elif better_ret:
                verdict = "higher return (but more risk)"
            else:
                verdict = "loses to buy & hold (whipsaws)"
        rows.append({"name": name, **s, "verdict": verdict})

    return {
        "available": True,
        "ticker": ticker.upper(),
        "years": win_years,
        "period": period,
        "strategies": rows,
        "note": f"One stock, last {win_years}y. The lesson is usually: trend filters CUT DRAWDOWNS "
                "more than they raise returns. Not a recommendation — past results don't predict the future.",
    }
