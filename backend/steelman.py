"""Steelman the recovery-buy idea: find the most GENEROUS-but-honest variant.

Reuses recovery_test's cached closes + the SAME honest non-overlapping per-date
difference t-test. Adds extra point-in-time features:
  - weekly/long-term 200d trend (price above a 40-week SMA = ~200 trading days
    smoothed weekly), so we keep names in a long-term uptrend even if below daily 200d
  - 200d slope flattening / rising
  - large-drawdown (>40%) only
  - RSI2 oversold (the user's previously-validated dip edge), layered on recovery
All masks point-in-time (data <= t). All forward returns use px.shift(-H).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import recovery_test as rt

H3, H6 = 63, 126
HORIZONS = (63, 126)


def rsi(px: pd.DataFrame, n: int) -> pd.DataFrame:
    d = px.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def build():
    px = rt.load_closes()
    f = rt.features(px)
    f["rsi2"] = rsi(px, 2)
    # weekly long-term trend: 40-week SMA on weekly closes, reindexed daily (ffill, shifted to avoid lookahead)
    wk = px.resample("W-FRI").last()
    wk_sma40 = wk.rolling(40).mean()
    # use only info available strictly before/at t: reindex onto daily, ffill
    f["above_wk200"] = (wk > wk_sma40).reindex(px.index, method="ffill").shift(1).fillna(False) & (px > wk_sma40.reindex(px.index, method="ffill").shift(1))
    # simpler robust daily proxy: price above its own 200d is the daily trend; "long-term up"
    # = the 200d itself is above where it was ~1y ago (secular uptrend) even if price dipped below
    f["sma200_up_yoy"] = f["sma200"] > f["sma200"].shift(252)
    # 200d slope flattening/rising: sma200 today >= sma200 ~1 month ago
    f["sma200_slope_up"] = f["sma200"] > f["sma200"].shift(21)
    f["sma200_slope_flat_up"] = f["sma200"] >= f["sma200"].shift(21) * 0.995  # within -0.5%/mo
    # large drawdown only
    f["big_dd"] = f["dd"].rolling(rt.RECENT).min() <= -0.40
    return px, f


def perdate_diff_t(fwd, mask, H):
    return rt._perdate_diff_t(fwd, mask, H)


def descr(px, mask, H):
    fwd = px.shift(-H) / px - 1
    vals = fwd.where(mask).stack().dropna()
    if len(vals) < 20:
        return {"n": int(len(vals)), "note": "underpowered"}
    pdt = perdate_diff_t(fwd, mask, H)
    return {
        "n": int(len(vals)),
        "mean_pct": round(float(vals.mean()) * 100, 2),
        "median_pct": round(float(vals.median()) * 100, 2),
        "win_pct": round(float((vals > 0).mean()) * 100, 1),
        "p25_pct": round(float(vals.quantile(0.25)) * 100, 1),
        "vs_other_t": pdt["t"],
        "vs_other_diff_pct": pdt["diff_pct"],
        "n_dates": pdt["n_dates"],
    }


def regime_split(px, mask, H, cut="2021-06-01"):
    """Split forward-return pooled stack by entry date into two regimes; report mean & vs-other t each."""
    fwd = px.shift(-H) / px - 1
    out = {}
    cutd = pd.Timestamp(cut)
    for name, idx in [("pre", px.index[px.index < cutd]), ("post", px.index[px.index >= cutd])]:
        m = mask.loc[idx]
        f2 = fwd.loc[idx]
        vals = f2.where(m).stack().dropna()
        if len(vals) < 20:
            out[name] = {"n": int(len(vals)), "note": "underpowered"}
            continue
        pdt = rt._perdate_diff_t(f2, m, H)
        out[name] = {"n": int(len(vals)), "mean_pct": round(float(vals.mean())*100,2),
                     "vs_other_t": pdt["t"], "n_dates": pdt["n_dates"]}
    return out


def main():
    px, f = build()
    below200, above50, crashed, enough = f["below200"], f["above50"], f["crashed"], f["enough"]
    sma50, sma200 = f["sma50"], f["sma200"]
    base = crashed & enough

    variants = {}

    # V1: R2 recovering BUT long-term secular uptrend intact (200d rising YoY)
    variants["V1_recover_LTuptrend"] = below200 & above50 & base & f["sma200_up_yoy"]

    # V2: large DD (>40%) that reclaims the 50d (cross) while still below 200
    cross50 = above50 & ~above50.shift(1, fill_value=False)
    variants["V2_bigDD_reclaim50"] = f["big_dd"] & enough & below200 & cross50

    # V3: recovering (above 50d) AND oversold RSI2<15 (layer dip edge on recovery)
    variants["V3_recover_RSI2_oversold"] = below200 & above50 & base & (f["rsi2"] < 15)

    # V4: reclaim 200d but require 200d slope flattening/rising (not catching on the way down)
    reclaim200 = (px > sma200) & (px.shift(1) <= sma200.shift(1))
    variants["V4_reclaim200_slopeup"] = reclaim200 & base & f["sma200_slope_up"]
    variants["V4b_reclaim200_slopeflat"] = reclaim200 & base & f["sma200_slope_flat_up"]

    # V5: recovering state + 200d slope flattening/rising (stay above 50, 200d not collapsing)
    variants["V5_recover_slopeflat"] = below200 & above50 & base & f["sma200_slope_flat_up"]

    # V6: bigDD recovering state (above 50, below 200) — pure deep mean reversion that turned
    variants["V6_bigDD_recover"] = f["big_dd"] & enough & below200 & above50

    # V7: weekly long-term trend up AND recovering above daily 50d (below daily 200d allowed)
    variants["V7_wk200up_recover"] = f["above_wk200"] & above50 & base

    res = {}
    for name, m in variants.items():
        res[name] = {"3mo": descr(px, m, H3), "6mo": descr(px, m, H6)}
    import json
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
