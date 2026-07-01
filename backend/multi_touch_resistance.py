"""Multi-touch horizontal resistance breakout — honest, point-in-time backtest.

Resistance R is a price level the HIGH approached (within TOL) and was REJECTED at
on >=MIN_TOUCH distinct swing-high pivots inside a trailing WINDOW, while the CLOSE
stayed below R. Breakout = today's CLOSE crosses above R for the first time
(yesterday's close <= R, today's close > R).

POINT-IN-TIME: a signal at bar t uses only highs with index position <= t. Pivots
need +/-PIVOT future bars to confirm, so the most recent PIVOT bars of the window
can never be pivots yet (handled naturally by requiring confirmation bars that all
lie at-or-before t). No forward leakage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import recovery_test as rt

CACHE = ".resistance_cache.pkl"

WINDOW = 120      # trailing lookback for the level
PIVOT = 3         # swing high = local max of high over +/-PIVOT bars
TOL = 0.015       # 1.5% : pivot "touches" the level / cluster width
MIN_TOUCH = 3     # >=3 distinct rejections
HORIZONS = (5, 21, 63)


def swing_high_pivots(high: np.ndarray) -> np.ndarray:
    """Boolean array: True where bar i is a local max over [i-PIVOT, i+PIVOT].
    A pivot at i is only *confirmable* once bar i+PIVOT exists (handled by caller)."""
    n = len(high)
    piv = np.zeros(n, dtype=bool)
    for i in range(PIVOT, n - PIVOT):
        window = high[i - PIVOT:i + PIVOT + 1]
        if high[i] == window.max() and np.sum(window == window.max()) == 1:
            piv[i] = True
    return piv


def build_mask(b: dict) -> pd.DataFrame:
    high = b["high"]
    close = b["close"]
    idx = close.index
    cols = close.columns
    mask = pd.DataFrame(False, index=idx, columns=cols)

    H = high.values
    C = close.values
    n = len(idx)

    for j, tk in enumerate(cols):
        h = H[:, j]
        c = C[:, j]
        valid = ~np.isnan(c)
        # iterate over candidate breakout bars t
        for t in range(WINDOW + PIVOT, n):
            if not valid[t] or not valid[t - 1]:
                continue
            ct = c[t]
            cprev = c[t - 1]
            # window of bars strictly before t (point-in-time): [t-WINDOW, t-1]
            lo = t - WINDOW
            hw = h[lo:t]                      # highs in window, all index <= t-1
            cw = c[lo:t]
            if np.isnan(hw).any() or np.isnan(cw).any():
                continue
            # swing-high pivots inside this window, but a pivot at local pos p is only
            # confirmed if p+PIVOT < len(window) i.e. its right shoulder is also <= t-1.
            piv_local = swing_high_pivots(hw)
            # pivot positions (local) -> their high values
            pivs = np.where(piv_local)[0]
            if len(pivs) < MIN_TOUCH:
                continue
            pivot_highs = hw[pivs]
            # cluster pivots within TOL of each other; find a cluster with >=MIN_TOUCH
            # distinct members. Greedy: for each pivot as anchor, count pivots within
            # TOL above/below; take the densest cluster.
            best_R = None
            best_count = 0
            for ph in pivot_highs:
                near = pivot_highs[np.abs(pivot_highs / ph - 1.0) <= TOL]
                if len(near) > best_count:
                    best_count = len(near)
                    best_R = near.max()       # ceiling of the cluster
            if best_count < MIN_TOUCH or best_R is None:
                continue
            R = best_R
            # CLOSE must have stayed below R throughout the window (genuine ceiling)
            if (cw > R).any():
                continue
            # breakout: yesterday's close <= R, today's close > R (first cross)
            if cprev <= R and ct > R:
                mask.iat[t, j] = True
    return mask


def main():
    b = pd.read_pickle(CACHE)
    close = b["close"]
    mask = build_mask(b)

    n_sig = int(mask.values.sum())
    print(f"PARAMS window={WINDOW} pivot=+/-{PIVOT} tol={TOL} min_touch={MIN_TOUCH}")
    print(f"total breakout signal observations n = {n_sig}")
    print(f"distinct signal dates = {int((mask.sum(axis=1) > 0).sum())}")

    rows = []
    for H in HORIZONS:
        fwd = close.shift(-H) / close - 1
        vals = fwd.where(mask).stack().dropna()
        d = rt._perdate_diff_t(fwd, mask, H)
        n = int(len(vals))
        mean_pct = round(float(vals.mean()) * 100, 2) if n else None
        win_pct = round(float((vals > 0).mean()) * 100, 1) if n else None
        rows.append((H, n, mean_pct, win_pct, d["diff_pct"], d["t"], d["n_dates"]))
        print(f"H={H:>3}  n={n:>4}  mean={mean_pct}%  win={win_pct}%  "
              f"vs_other_diff={d['diff_pct']}%  t={d['t']}  n_dates={d['n_dates']}")
    return rows


if __name__ == "__main__":
    main()
