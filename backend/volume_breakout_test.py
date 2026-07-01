"""The STRONGEST honest version of "buy the resistance break": confirmed by a
VOLUME surge, and from a tight base (the real Minervini/VCP setup). If even this
fails, the breakout-buy idea is genuinely dead. Point-in-time, cached, per-date t.

Variants (all = new high today, point-in-time):
  V0_plain50      : new 50-day high (control — no volume)
  V1_vol50_1.5x   : new 50-day high on volume > 1.5x its 50-day average
  V2_vol50_2x     : new 50-day high on volume > 2x average (big conviction)
  V3_vol_uptrend  : V1 AND above the 200-day (trend filter)
  V4_52whigh_vol  : new 252-day (52-week) high on volume > 1.5x (blue-sky breakout)
  V5_vcp          : breakout from a TIGHT base (prior 20d range < 10%) on volume>1.5x
Bar to clear: beat buy-hold AND other-stocks-same-date with t>2.

Run: ./venv/bin/python volume_breakout_test.py 2>/dev/null
"""
from __future__ import annotations
import json, os, sys
import numpy as np
import pandas as pd
from services import data
import recovery_test as rt

CACHE = os.path.join(os.path.dirname(__file__), ".volbreak_cache.pkl")
HOR = (5, 21, 63)


def load():
    if os.path.exists(CACHE):
        b = pd.read_pickle(CACHE)
        return b["close"], b["volume"]
    cl, vol = {}, {}
    for t in rt.UNIVERSE:
        try:
            d = data.fetch_ohlcv(t, "10y", "1d")
            cl[t], vol[t] = d["close"], d["volume"]
        except Exception as e:
            print(f"skip {t}: {e}", file=sys.stderr)
    close = pd.DataFrame(cl).sort_index()
    volume = pd.DataFrame(vol).reindex(close.index)
    pd.to_pickle({"close": close, "volume": volume}, CACHE)
    return close, volume


def evaluate(mask, px, label):
    out = {"signal": label}
    for H in HOR:
        fwd = px.shift(-H) / px - 1
        vals = fwd.where(mask).stack().dropna()
        if len(vals) < 20:
            out[f"{H}d"] = {"n": int(len(vals)), "note": "underpowered"}
            continue
        out[f"{H}d"] = {"n": int(len(vals)),
                        "mean_pct": round(float(vals.mean()) * 100, 2),
                        "win_pct": round(float((vals > 0).mean()) * 100, 1),
                        "vs_other": rt._perdate_diff_t(fwd, mask, H)}
    return out


def main():
    px, vol = load()
    enough = px.notna().rolling(400).sum() >= 400
    sma200 = px.rolling(200).mean()
    volavg = vol.rolling(50).mean()
    vr = vol / volavg                                   # volume ratio vs 50-day avg

    new50 = px > px.rolling(50).max().shift(1)
    new252 = px > px.rolling(252).max().shift(1)
    rng20 = (px.rolling(20).max() - px.rolling(20).min()) / px      # base tightness
    tight = rng20.shift(1) < 0.10                       # prior 20d range under 10% = tight base

    masks = {
        "V0_plain50":     new50 & enough,
        "V1_vol50_1.5x":  new50 & (vr > 1.5) & enough,
        "V2_vol50_2x":    new50 & (vr > 2.0) & enough,
        "V3_vol_uptrend": new50 & (vr > 1.5) & (px > sma200) & enough,
        "V4_52whigh_vol": new252 & (vr > 1.5) & enough,
        "V5_vcp":         new50 & (vr > 1.5) & tight & enough,
    }

    base = {}
    for H in HOR:
        v = (px.shift(-H) / px - 1).stack().dropna()
        base[f"{H}d"] = {"mean_pct": round(float(v.mean()) * 100, 2),
                         "win_pct": round(float((v > 0).mean()) * 100, 1)}

    out = {"universe_n": int(px.shape[1]), "buy_hold_baseline": base,
           "results": [evaluate(m, px, k) for k, m in masks.items()]}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
