"""Does TREND-CONTINUATION (momentum) work? — the honest version of "trends are
generally successful." This buys STRENGTH (stocks already in a confirmed uptrend),
the opposite of buying a crash-recovery. Same cached universe + per-date diff test.

Signals (all point-in-time, >=1.5y history):
  M1_tsmom_above200 : above 200-day AND 12-1 month momentum positive (classic time-series momentum)
  M3_golden_cross   : 50-day above 200-day (confirmed uptrend), hold
  M5_stage2_uptrend : price>50d>200d AND 50d rising (Minervini "Stage 2")
  M2 spread         : cross-sectional — top third by 6-mo return vs bottom third (the real momentum anomaly)

Run: ./venv/bin/python momentum_test.py 2>/dev/null
"""
from __future__ import annotations
import json
import numpy as np
import pandas as pd
import recovery_test as rt

HOR = (21, 63, 126)


def main():
    px = rt.load_closes()
    sma50, sma200 = px.rolling(50).mean(), px.rolling(200).mean()
    enough = px.notna().rolling(400).sum() >= 400
    mom12_1 = px.shift(21) / px.shift(252) - 1      # 12-1 month momentum (skip last month)
    mom6 = px / px.shift(126) - 1
    above200 = px > sma200

    masks = {
        "M1_tsmom_above200": above200 & (mom12_1 > 0) & enough,
        "M3_golden_cross":   (sma50 > sma200) & enough,
        "M5_stage2_uptrend": (px > sma50) & (sma50 > sma200) & (sma50 > sma50.shift(20)) & enough,
    }

    out = {"universe_n": int(px.shape[1]), "baseline": {}, "signals": {}}
    for H in HOR:
        v = (px.shift(-H) / px - 1).stack().dropna()
        out["baseline"][f"{H//21}mo"] = {"mean_pct": round(float(v.mean()) * 100, 2),
                                         "win_pct": round(float((v > 0).mean()) * 100, 1)}

    for name, m in masks.items():
        out["signals"][name] = {}
        for H in HOR:
            fwd = px.shift(-H) / px - 1
            vals = fwd.where(m).stack().dropna()
            out["signals"][name][f"{H//21}mo"] = {
                "n": int(len(vals)),
                "mean_pct": round(float(vals.mean()) * 100, 2),
                "win_pct": round(float((vals > 0).mean()) * 100, 1),
                "vs_other": rt._perdate_diff_t(fwd, m, H),
            }

    # M2 — cross-sectional momentum spread: top vs bottom tercile by 6mo return
    spread = {}
    for H in HOR:
        fwd = px.shift(-H) / px - 1
        dates = px.index[list(range(260, len(px) - H, H))]
        diffs = []
        for dt in dates:
            r = mom6.loc[dt].dropna()
            if len(r) < 9:
                continue
            top = r[r >= r.quantile(2 / 3)].index
            bot = r[r <= r.quantile(1 / 3)].index
            ft, fb = fwd.loc[dt, top].dropna(), fwd.loc[dt, bot].dropna()
            if len(ft) and len(fb):
                diffs.append(ft.mean() - fb.mean())
        diffs = np.array(diffs)
        t = diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs))) if len(diffs) > 2 else float("nan")
        spread[f"{H//21}mo"] = {"top_minus_bottom_pct": round(float(diffs.mean()) * 100, 2),
                                "t": round(float(t), 2), "n_dates": int(len(diffs))}
    out["M2_xsec_momentum_spread"] = spread
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
