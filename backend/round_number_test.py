"""Round-number / psychological resistance breakout — honest, point-in-time.

Resistance = the nearest round level above price, where the round STEP scales to
price ($1 <$20, $5 $20-100, $10 $100-500, $50 >$500). A round level R is
"resistance" if the stock has been STUCK just under it: close < R AND within ~4%
below R, on >=10 of the last LOOKBACK bars. Breakout = today's close crosses
above R after yesterday's close was below R.

Everything point-in-time: the round level and the "stuck under" test use only bars
with index <= t (yesterday's stuck-state + today's close crossing). Forward returns
use rt._perdate_diff_t (non-overlapping per-date diff t).
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

import recovery_test as rt

B = pd.read_pickle('.resistance_cache.pkl')
close = B['close']
HORIZONS = (5, 21, 63)

LOOKBACK = 20      # window to check "stuck just under" (past bars)
MIN_STUCK = 10     # >= this many of the last LOOKBACK bars sit just below the level
NEAR = 0.04        # "within ~4% below" the round level


def round_step(price: pd.DataFrame) -> pd.DataFrame:
    """Step scaled to price level (vectorized). Point-in-time: uses price at t."""
    step = pd.DataFrame(np.nan, index=price.index, columns=price.columns)
    step = step.mask(price < 20, 1.0)
    step = step.mask((price >= 20) & (price < 100), 5.0)
    step = step.mask((price >= 100) & (price < 500), 10.0)
    step = step.mask(price >= 500, 50.0)
    return step


def nearest_round_above(price: pd.DataFrame, step: pd.DataFrame) -> pd.DataFrame:
    """Smallest round multiple of step strictly above price."""
    # floor(price/step)*step is the round level at/below price; add step to go above.
    base = np.floor(price / step) * step
    level = base + step
    # if price sits exactly on a round number, base+step is still the next one up.
    return level


def build_mask() -> pd.DataFrame:
    px = close
    step_y = round_step(px.shift(1))                       # step from yesterday's price
    R = nearest_round_above(px.shift(1), step_y)            # the round level above, as of yesterday

    # "just under R" on a given past bar: close below R and within NEAR% below it.
    # Use the SAME R (level defined as of yesterday) consistently across the window so
    # we are asking "has price been camped just under THIS level". For each bar k in the
    # window we test that bar's close against R (point-in-time: R known by yesterday,
    # window bars are all <= yesterday).
    dist = (R - px) / R                                     # >0 means below R
    just_under = (px < R) & (dist <= NEAR) & (dist > 0)     # below and within 4%
    # count over the past LOOKBACK bars, all strictly before today (shifted)
    stuck_count = just_under.shift(1).rolling(LOOKBACK).sum()
    stuck = stuck_count >= MIN_STUCK

    below_yest = px.shift(1) < R                            # was below the level yesterday
    cross_up = px > R                                       # closes above it today

    enough = px.notna().rolling(LOOKBACK + 5).sum() >= (LOOKBACK + 5)
    mask = stuck & below_yest & cross_up & enough
    return mask.fillna(False)


def main():
    mask = build_mask()
    n_signals = int(mask.values.sum())
    rows = []
    for H in HORIZONS:
        fwd = close.shift(-H) / close - 1
        d = rt._perdate_diff_t(fwd, mask, H)
        vals = fwd.where(mask).stack().dropna()
        n = int(len(vals))
        rows.append({
            "H": H,
            "diff_pct": d["diff_pct"], "t": d["t"], "n_dates": d["n_dates"],
            "mean_pct": round(float(vals.mean()) * 100, 2) if n else None,
            "win_pct": round(float((vals > 0).mean()) * 100, 1) if n else None,
            "n": n,
        })
    print(json.dumps({"n_signals": n_signals, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
