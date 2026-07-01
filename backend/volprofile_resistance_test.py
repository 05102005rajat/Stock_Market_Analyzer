"""Volume-profile (high-volume-node) resistance breakout — honest point-in-time test.

Resistance definition (fixed once, no tuning):
  - Trailing window W = 120 trading days.
  - Build a volume-by-price histogram with NBINS = 30 bins spanning the window's
    [min(low), max(high)] range.
  - Each day's volume is SPREAD across its [low, high] range in proportion to the
    overlap of that bar with each bin (so a wide bar deposits volume into many
    bins, a narrow bar concentrates it). This is more faithful than dumping all
    volume into the close bin.
  - Overhead supply node = the highest-volume bin whose bin-CENTER price is ABOVE
    today's close. Resistance R = that bin center. (nearest meaningful overhead HVN
    by volume, not just nearest by price)
  - Breakout on date t: close_t > R_t AND close_{t-1} <= R_{t-1 grid}  i.e. the
    close crosses up through the overhead high-volume shelf for the first time.

Point-in-time: the profile at grid date g uses ONLY bars with index in
(g-W, g]. We compute the profile + R on a WEEKLY grid (every 5 trading days) for
speed, forward-fill R to daily, then fire the breakout the first daily bar the
close exceeds R. No forward data is ever used.

Run: ./venv/bin/python volprofile_resistance_test.py
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

import recovery_test as rt

W = 120          # trailing window (trading days)
NBINS = 30       # price bins
GRID = 5         # recompute profile every 5 trading days (weekly) for speed
HORIZONS = (5, 21, 63)


def overhead_hvn(highs, lows, vols, close):
    """Given trailing-window arrays (highs, lows, vols) and today's close, return
    the price of the highest-volume bin whose center is above `close`, or nan."""
    lo = np.nanmin(lows)
    hi = np.nanmax(highs)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.nan
    edges = np.linspace(lo, hi, NBINS + 1)
    centers = (edges[:-1] + edges[1:]) / 2
    width = (hi - lo) / NBINS
    profile = np.zeros(NBINS)
    for h, l, v in zip(highs, lows, vols):
        if not (np.isfinite(h) and np.isfinite(l) and np.isfinite(v)) or v <= 0:
            continue
        if h < l:
            h, l = l, h
        span = h - l
        if span <= 0:
            # narrow/zero-range bar: dump all volume in the bin containing its price
            idx = min(int((h - lo) / width), NBINS - 1)
            idx = max(idx, 0)
            profile[idx] += v
            continue
        # overlap of [l,h] with each bin, distribute volume proportionally
        ov = np.clip(np.minimum(edges[1:], h) - np.maximum(edges[:-1], l), 0, None)
        s = ov.sum()
        if s > 0:
            profile += v * ov / s
    # overhead bins: center strictly above today's close
    above = centers > close
    if not above.any():
        return np.nan
    cand_vol = np.where(above, profile, -1.0)
    j = int(np.argmax(cand_vol))
    if cand_vol[j] <= 0:
        return np.nan
    return float(centers[j])


def build_resistance(b):
    high, low, close, vol = b["high"], b["low"], b["close"], b["volume"]
    idx = close.index
    tickers = close.columns
    R = pd.DataFrame(index=idx, columns=tickers, dtype=float)
    grid_positions = range(W, len(idx), GRID)
    H = high.values
    L = low.values
    V = vol.values
    C = close.values
    for gi in grid_positions:
        sl = slice(gi - W, gi)          # bars (g-W, g-1]  -> strictly past+today's window
        for ci, tk in enumerate(tickers):
            c = C[gi, ci]
            if not np.isfinite(c):
                continue
            R.iat[gi, ci] = overhead_hvn(H[sl, ci], L[sl, ci], V[sl, ci], c)
    # forward-fill R from grid dates to daily (point-in-time: R known at grid date,
    # held until next recompute). Limit ffill to GRID so stale values don't persist.
    R = R.ffill(limit=GRID)
    return R


def main():
    b = pd.read_pickle(".resistance_cache.pkl")
    close = b["close"]
    R = build_resistance(b)

    # Breakout: close crosses above the overhead HVN shelf.
    above = close > R
    crossed = above & ~above.shift(1, fill_value=False)
    # require R to have been defined on the prior bar too (genuine cross, not a
    # first-appearance artifact)
    mask = crossed & R.shift(1).notna() & R.notna()

    # also require enough history so the window is full
    enough = close.notna().rolling(W + 5).sum() >= (W + 5)
    mask = mask & enough
    mask = mask.fillna(False)

    rows = []
    n_sig = int(mask.values.sum())
    for H in HORIZONS:
        fwd = close.shift(-H) / close - 1
        d = rt._perdate_diff_t(fwd, mask, H)
        sel = fwd.where(mask)
        flat = sel.values[np.isfinite(sel.values)]
        mean_pct = float(np.mean(flat)) * 100 if flat.size else float("nan")
        win_pct = float(np.mean(flat > 0)) * 100 if flat.size else float("nan")
        rows.append(dict(H=H, mean_pct=round(mean_pct, 2), win_pct=round(win_pct, 1),
                         n=int(flat.size), diff_pct=d["diff_pct"], t=d["t"],
                         n_dates=d["n_dates"]))
    out = dict(n_signals=n_sig, rows=rows,
               R_coverage=float(R.notna().values.mean()))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
