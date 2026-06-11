"""SHORT-HOLD answer (1 to 5 days = your actual 1-week flip). Does buying the
resistance break beat the alternatives over 1 week? Point-in-time, cached.

Compares over 1/2/3/5-day holds:
  random day      : the no-skill bar
  fresh breakout  : new 21-day high out of a 1-month base
  volume breakout : new 50-day high on volume > 1.5x average (the 'confirmed' break)
  dip-buy         : oversold RSI2<15 inside an uptrend (the tested edge)
vs_other = per-date difference vs every other stock that day (the honest edge test).
"""
from __future__ import annotations
import os
import numpy as np
import pandas as pd
import recovery_test as rt

CACHE = os.path.join(os.path.dirname(__file__), ".volbreak_cache.pkl")
HOR = (1, 2, 3, 5)


def rsi2(c):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def main():
    b = pd.read_pickle(CACHE)
    px, vol = b["close"], b["volume"]
    enough = px.notna().rolling(400).sum() >= 400
    sma200 = px.rolling(200).mean()
    vr = vol / vol.rolling(50).mean()

    new21 = px > px.rolling(21).max().shift(1)
    drought = new21.shift(1).rolling(21).sum() == 0
    fresh = new21 & drought & enough
    volbreak = (px > px.rolling(50).max().shift(1)) & (vr > 1.5) & enough
    dip = (px.apply(rsi2) < 15) & (px > sma200) & enough

    sigs = [("fresh breakout", fresh), ("volume breakout", volbreak), ("dip-buy (oversold)", dip)]

    print("ONE-WEEK answer — 80 names, 10y, point-in-time\n")
    print(f"{'trigger':22}{'hold':>5}{'avg':>9}{'win%':>7}{'n':>8}   vs random-day")
    for H in HOR:
        bfwd = (px.shift(-H) / px - 1).stack().dropna()
        print(f"{'(random day)':22}{H:>4}d{bfwd.mean()*100:>+8.2f}%{(bfwd>0).mean()*100:>6.0f}%{len(bfwd):>8}   —")
        for label, m in sigs:
            fwd = px.shift(-H) / px - 1
            vals = fwd.where(m).stack().dropna()
            d = rt._perdate_diff_t(fwd, m, H)
            print(f"{label:22}{H:>4}d{vals.mean()*100:>+8.2f}%{(vals>0).mean()*100:>6.0f}%{len(vals):>8}   {d['diff_pct']:+}% (t={d['t']}, n={d['n_dates']}d)")
        print()


if __name__ == "__main__":
    main()
