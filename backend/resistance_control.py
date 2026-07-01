"""CONTROL test: crude rolling-max resistance breakout.

Resistance R(t) = highest HIGH over the prior 50 days = high.rolling(50).max().shift(1)
(the .shift(1) makes it point-in-time: R(t) uses only bars strictly before t).
Breakout signal at t = close(t) > R(t)  AND  close(t-1) <= R(t-1)  -> the *bar* it
breaks through (fresh cross, not "every day it stays above"). We report both the
fresh-cross version and the simpler "close > R" state, since the task says "True on
the bar a genuine breakout happens" -> fresh cross is the honest reading.

Everything point-in-time. Forward returns from CLOSE. Honest edge via
recovery_test._perdate_diff_t (non-overlapping per-date diff t-test).
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import recovery_test as rt

LOOKBACK = 50
HORIZONS = (5, 21, 63)


def main():
    b = pd.read_pickle(".resistance_cache.pkl")
    high, close = b["high"], b["close"]

    # Point-in-time resistance: highest high over prior LOOKBACK bars (excludes today).
    R = high.rolling(LOOKBACK).max().shift(1)

    above = close > R
    # Fresh cross = the bar it breaks above (yesterday at/below, today above).
    # NOTE: shift(1, fill_value=False) keeps bool dtype; .shift(1).fillna(False)
    # silently produced object dtype in pandas 2.x and broke the ~ negation,
    # making this mask identical to `above`.
    fresh = above & ~above.shift(1, fill_value=False)
    # Maturity guard: need enough history so R is defined and the name has data.
    enough = close.notna().rolling(LOOKBACK + 5).sum() >= (LOOKBACK + 5)

    masks = {
        "fresh_cross": fresh & R.notna() & enough,   # the honest "breakout bar"
        "above_state": above & R.notna() & enough,   # every day price is above R (for ref)
    }

    out = {"lookback": LOOKBACK, "horizons": list(HORIZONS), "variants": {}}
    for name, mask in masks.items():
        rec = {}
        for H in HORIZONS:
            fwd = close.shift(-H) / close - 1
            vals = fwd.where(mask).stack().dropna()
            pdt = rt._perdate_diff_t(fwd, mask, H)
            rec[f"{H}d"] = {
                "n": int(len(vals)),
                "mean_pct": round(float(vals.mean()) * 100, 2) if len(vals) else None,
                "win_pct": round(float((vals > 0).mean()) * 100, 1) if len(vals) else None,
                "perdate": pdt,
            }
        out["variants"][name] = rec
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
