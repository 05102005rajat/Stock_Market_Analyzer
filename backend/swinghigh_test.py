"""Swing-high PIVOT resistance breakout — honest, point-in-time backtest.

Resistance = the most recent *confirmed* swing-high pivot above current price.
A swing-high pivot at bar i is a 'high' that is the local maximum over a +/-W bar
window (W=5). It is only CONFIRMED once W bars have passed after it (so the
right-hand window is fully observed). Point-in-time: at date t we only know about
pivots whose bar index <= t-W.

Breakout (the signal) on bar t:
  - close[t] > R[t]           (closes above the most recent confirmed pivot above price)
  - close[t-1] <= R[t-1]      (was at/below it on the prior bar -> a genuine cross)
  - R is the nearest confirmed pivot-high that sits ABOVE the prior close.

Optional "notable" variant: require that pivot to be higher than the prior pivot
(an ascending/significant swing high), to avoid breaking trivial micro-pivots.

Forward returns and the honest per-date diff t-test come from recovery_test.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

import recovery_test as rt

W = 5  # pivot half-window (local max over +/-5 bars); also confirmation lag


def _confirmed_pivot_high(high: pd.Series) -> pd.Series:
    """For each bar, the pivot HIGH value once it becomes confirmed.

    A bar j is a swing-high pivot if high[j] == max(high[j-W .. j+W]) (strict vs
    neighbours, ties broken by >= which is fine). It becomes known at bar j+W.
    Return a series indexed like `high`: at index t, the pivot-high VALUE of any
    pivot that got CONFIRMED exactly at bar t (NaN otherwise). Point-in-time safe.
    """
    h = high.values
    n = len(h)
    out = np.full(n, np.nan)
    for j in range(W, n - W):
        wj = h[j - W:j + W + 1]
        if np.isnan(h[j]) or np.isnan(wj).any():
            continue
        if h[j] == wj.max() and (wj < h[j]).sum() >= 2 * W:  # strict local max
            conf = j + W                                     # confirmed here
            if conf < n:
                out[conf] = h[j]
    return pd.Series(out, index=high.index)


def build_masks(b: dict):
    """Return (mask_basic, mask_notable) boolean DataFrames (date x ticker)."""
    high, close = b["high"], b["close"]
    cols = close.columns
    basic = pd.DataFrame(False, index=close.index, columns=cols)
    notable = pd.DataFrame(False, index=close.index, columns=cols)

    enough = close.notna().rolling(260).sum() >= 260  # >=1y history maturity guard

    for tk in cols:
        h = high[tk]
        c = close[tk]
        piv_conf = _confirmed_pivot_high(h)   # value confirmed AT each bar, else NaN

        # Walk bars, maintaining the set of confirmed pivots so far.
        piv_levels = []     # all confirmed pivot-high values, in confirmation order
        last_R = np.nan     # nearest confirmed pivot ABOVE prior close
        prev_pivot_val = np.nan
        cvals = c.values
        idx = c.index
        for i in range(len(idx)):
            # 1) signal test uses R as known at bar i-1 (only past pivots)
            pclose = cvals[i - 1] if i > 0 else np.nan
            ccur = cvals[i]
            # nearest confirmed pivot strictly ABOVE the prior close:
            R = np.nan
            R_notable = np.nan
            if not np.isnan(pclose) and piv_levels:
                above = [(p, k) for k, p in enumerate(piv_levels) if p > pclose]
                if above:
                    # nearest above = smallest pivot that still exceeds prior close
                    p, k = min(above, key=lambda x: x[0])
                    R = p
                    # notable: that pivot higher than the pivot before it (ascending)
                    if k > 0 and piv_levels[k] > piv_levels[k - 1]:
                        R_notable = p

            if (not np.isnan(R) and not np.isnan(ccur) and not np.isnan(pclose)
                    and ccur > R and pclose <= R):
                basic.iat[i, basic.columns.get_loc(tk)] = True
            if (not np.isnan(R_notable) and not np.isnan(ccur) and not np.isnan(pclose)
                    and ccur > R_notable and pclose <= R_notable):
                notable.iat[i, notable.columns.get_loc(tk)] = True

            # 2) AFTER acting on bar i, add any pivot confirmed at bar i (it became
            #    known at bar i, so it may only inform bars > i). This keeps PIT.
            pv = piv_conf.iat[i]
            if not np.isnan(pv):
                piv_levels.append(pv)

    basic = basic & enough.fillna(False)
    notable = notable & enough.fillna(False)
    return basic, notable


def evaluate(b: dict, mask: pd.DataFrame, name: str):
    close = b["close"]
    out = {"signal": name, "horizons": {}}
    for H in (5, 21, 63):
        fwd = close.shift(-H) / close - 1
        vals = fwd.where(mask).stack().dropna()
        diff = rt._perdate_diff_t(fwd, mask, H)
        out["horizons"][f"{H}d"] = {
            "n": int(len(vals)),
            "mean_pct": round(float(vals.mean()) * 100, 2) if len(vals) else None,
            "win_pct": round(float((vals > 0).mean()) * 100, 1) if len(vals) else None,
            "vs_other": diff,
        }
    return out


def main():
    b = pd.read_pickle(".resistance_cache.pkl")
    basic, notable = build_masks(b)
    print("basic total signals:", int(basic.values.sum()))
    print("notable total signals:", int(notable.values.sum()))
    res = {
        "basic": evaluate(b, basic, "swinghigh_basic"),
        "notable": evaluate(b, notable, "swinghigh_notable"),
    }
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
