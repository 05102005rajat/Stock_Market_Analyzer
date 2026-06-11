"""PRIOR-PEAK re-test breakout (reclaim a former major high) — point-in-time.

Resistance = a MAJOR prior peak: the highest HIGH in a window ~6-12 months ago that
price then fell at least ~10% below, and has since climbed back to re-test.
Breakout = CLOSE reclaims above that prior major peak (first cross from below).

Everything POINT-IN-TIME: a signal at date t uses only data with index <= t.
"""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

import recovery_test as rt

b = pd.read_pickle('.resistance_cache.pkl')
high = b['high']
low = b['low']
close = b['close']

# --- parameters (picked once, sensible) ---
LOOK_LO = 126   # ~6 months: peak must be at least this far back
LOOK_HI = 252   # ~12 months: ...and no further than this back
FELL    = 0.10  # price must have fallen >=10% below the peak after it formed
NEAR    = 0.03  # "re-test": prior close was within 3% below the peak (climbed back)
ENOUGH  = 300   # require >=300 bars of history (maturity guard)

n = len(close)

# Resistance level at each date t = the highest HIGH over the window [t-252, t-126].
# This is the major prior peak from 6-12 months ago, known as of t (shifted).
# rolling max of high over a 252-window, but ending LOOK_LO bars ago:
peak = high.shift(LOOK_LO).rolling(LOOK_HI - LOOK_LO).max()   # uses bars t-252..t-126

# Did price fall >=FELL below that peak at some point AFTER the peak window but before t?
# Lowest low since the peak window ended (i.e. over the last LOOK_LO bars, shifted by 1
# so it's strictly prior to today's bar) vs the peak.
low_since = low.shift(1).rolling(LOOK_LO).min()
fell_below = low_since <= peak * (1 - FELL)

# Re-test: yesterday's close was within NEAR below the peak (had climbed back near it),
# and today's close reclaims ABOVE the peak (first cross from below).
prev_close = close.shift(1)
near_below = (prev_close <= peak) & (prev_close >= peak * (1 - NEAR))
cross_up = (close > peak) & (prev_close <= peak)

enough = close.notna().rolling(ENOUGH).sum() >= ENOUGH

mask = (peak.notna() & fell_below & near_below & cross_up & enough).fillna(False)

# evaluation
print("total signal observations n =", int(mask.values.sum()))
print("dates with >=1 signal =", int((mask.sum(axis=1) > 0).sum()))

for H in (5, 21, 63):
    fwd = close.shift(-H) / close - 1
    vals = fwd.where(mask).stack().dropna()
    d = rt._perdate_diff_t(fwd, mask, H)
    if len(vals):
        print(f"H={H:2d}  n={len(vals):4d}  mean_pct={vals.mean()*100:6.2f}  "
              f"win_pct={(vals>0).mean()*100:5.1f}  "
              f"vs_other diff={d['diff_pct']}  t={d['t']}  n_dates={d['n_dates']}")
    else:
        print(f"H={H:2d}  n=0 (no signals)")
