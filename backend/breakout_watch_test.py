"""Do the SPECIFIC breakout patterns the user means have any forward edge?
Reuses the cached universe + honest per-date diff test from recovery_test.

  GEN_break  : any new 21-day high (generic breakout — already known to fail)
  B1_fresh   : new 21-day high that ENDS a ~1-month drought (breakout from a base)
  B2_retest  : broke out in last 10d, has pulled back to within 2% of the broken
               level and is holding above it (buy-the-retest idea)
Bar to clear: beat buy-hold AND other-stocks-same-date with t>2.

Run: ./venv/bin/python breakout_watch_test.py 2>/dev/null
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import recovery_test as rt

HOR = (21, 63)


def evaluate(mask, px, label):
    out = {"signal": label}
    for H in HOR:
        fwd = px.shift(-H) / px - 1
        vals = fwd.where(mask).stack().dropna()
        if len(vals) < 20:
            out[f"{H//21}mo"] = {"n": int(len(vals)), "note": "underpowered"}
            continue
        out[f"{H//21}mo"] = {
            "n": int(len(vals)),
            "mean_pct": round(float(vals.mean()) * 100, 2),
            "win_pct": round(float((vals > 0).mean()) * 100, 1),
            "vs_other": rt._perdate_diff_t(fwd, mask, H),
        }
    return out


def main():
    px = rt.load_closes()
    enough = px.notna().rolling(400).sum() >= 400
    roll21 = px.rolling(21).max()
    new21 = px > roll21.shift(1)                          # new 21-day high today

    gen = new21 & enough
    drought = (new21.shift(1).rolling(21).sum() == 0)     # no new high in prior month
    fresh = new21 & drought & enough

    recent_break = new21.rolling(10).max().astype(bool)   # broke out in last 10 days
    old_R = roll21.shift(11)                              # the level broken (pre-break high)
    retest = recent_break & ((px / old_R - 1).abs() < 0.02) & (px > old_R) & enough

    base = {}
    for H in HOR:
        v = (px.shift(-H) / px - 1).stack().dropna()
        base[f"{H//21}mo"] = {"mean_pct": round(float(v.mean()) * 100, 2),
                              "win_pct": round(float((v > 0).mean()) * 100, 1)}

    out = {"buy_hold_baseline": base,
           "results": [evaluate(gen, px, "GEN_break"),
                       evaluate(fresh, px, "B1_fresh_from_base"),
                       evaluate(retest, px, "B2_retest")]}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
