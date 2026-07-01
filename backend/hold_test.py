"""The user's ACTUAL plan: buy the breakout, sell 3-4 days later. Does that beat
the alternatives over the SAME short hold? Honest, point-in-time, cached universe.

Compares, over a 3-day and 5-day hold:
  - baseline   : buying on a random day (the 'no-skill' bar)
  - fresh break: buying the day it breaks a 1-month base (the user's idea)
  - dip-buy    : buying when oversold (RSI2<15) inside an uptrend (the tested edge)
The point: SAME stocks, same short hold — which TRIGGER gives the better entry?
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import recovery_test as rt


def rsi2(c):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=0.5, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def main():
    px = rt.load_closes()
    enough = px.notna().rolling(400).sum() >= 400
    sma200 = px.rolling(200).mean()
    roll21 = px.rolling(21).max()
    new21 = px > roll21.shift(1)
    drought = new21.shift(1).rolling(21).sum() == 0
    fresh = new21 & drought & enough
    RSI2 = px.apply(rsi2)
    dip = (RSI2 < 15) & (px > sma200) & enough

    print(f"Short-hold test — 80 names, 10y, point-in-time\n")
    print(f"{'trigger':22}{'hold':>5}{'avg':>9}{'win%':>7}{'n':>8}   vs random-day entry")
    for H in (3, 5):
        # baseline: unconditional short-hold return
        bfwd = (px.shift(-H) / px - 1).stack().dropna()
        bmean = bfwd.mean()
        print(f"{'(random day)':22}{H:>4}d{bmean*100:>+8.2f}%{(bfwd>0).mean()*100:>6.0f}%{len(bfwd):>8}   —")
        for label, m in [("fresh breakout", fresh), ("dip-buy (oversold)", dip)]:
            fwd = px.shift(-H) / px - 1
            vals = fwd.where(m).stack().dropna()
            d = rt._perdate_diff_t(fwd, m, H)
            tag = f"{d['diff_pct']:+}% (t={d['t']}, n={d['n_dates']}d)"
            print(f"{label:22}{H:>4}d{vals.mean()*100:>+8.2f}%{(vals>0).mean()*100:>6.0f}%{len(vals):>8}   {tag}")
        print()

    # The 'buying the spike' effect: breakouts that are OVERBOUGHT (RSI14>68) next 3-5d
    rsi14 = px.apply(lambda c: 100 - 100 / (1 + c.diff().clip(lower=0).rolling(14).mean()
                                            / (-c.diff().clip(upper=0)).rolling(14).mean().replace(0, np.nan)))
    hot_break = fresh & (rsi14 > 68)
    cool_break = fresh & (rsi14 <= 68)
    print("Breakouts split by overbought (the 'don't chase a spike' check):")
    for H in (3, 5):
        for label, m in [("  overbought break", hot_break), ("  calm break", cool_break)]:
            v = (px.shift(-H) / px - 1).where(m).stack().dropna()
            if len(v) > 20:
                print(f"{label:22}{H:>4}d{v.mean()*100:>+8.2f}%{(v>0).mean()*100:>6.0f}%{len(v):>8}")


if __name__ == "__main__":
    main()
