"""Cross-sectional hypotheses — honest tests on the cached 80-name universe.

Four retail intuitions, tested point-in-time (results from the 2016-2026 cache):

1. SECTOR EVENT CONTAGION: ">=80% of a sector down >=1% in a day means more
   downside is coming."  -> NOT SUPPORTED. n=442 events: sector vs market
   +0.03% (5d) / -0.21% (21d) afterward. Crash days price the news same-day.
   Survivors (green on the event day) next-5d: +0.51%, 53% win — identical to
   the unconditional base rate (+0.49%, 51%). No delayed contagion.

2. SUPPLY-CHAIN LEAD-LAG: "chip designers up -> equipment makers up NEXT."
   -> NOT TRADABLE here. Contemporaneous 21d corr = 0.71 (same-month move);
   predictive hi-lo spread is NEGATIVE (-3.1%/21d, t=-1.2). Cohen & Frazzini
   (2008 JF) works for OVERLOOKED links, not the most-watched megacaps.

3. PEER CATCH-UP: "sector booming -> the laggard will catch up."
   -> NOT SUPPORTED. 906 sector-months: laggards minus leaders next 21d =
   -0.24% (t=-0.59). Mild momentum; laggards keep lagging. (Lead-lag in the
   literature is big->SMALL stocks; this universe is all big.)

4. RUN-UP INTO EVENTS REVERSES: "stocks pop into earnings then fade."
   -> SUPPORTED (t=-2.39, the only |t|>2 of the batch). Top-30% 10d run-ups
   into volume-spike events: next 21d -0.07% (51% win) vs +2.82% (58%) for
   weak run-ups. Matches the earnings-announcement-premium reversal
   (Frazzini & Lamont). Volume-proxy caveat: misses mega-cap earnings
   (nothing 3.5x's AAPL volume) — rebuild with real earnings dates.

Run:  ./venv/bin/python crosssection_test.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from services.sector import SECTORS

CACHE = ".resistance_cache.pkl"


def main():
    b = pd.read_pickle(CACHE)
    close, vol = b["close"], b["volume"]
    ret = close.pct_change()

    # ---- 1. sector event days ----
    print("TEST 1: sector event days (>=80% of members down >=1%)")
    rows = []
    for sec, tks in SECTORS.items():
        tks = [t for t in tks if t in ret.columns]
        if len(tks) < 5:
            continue
        r = ret[tks]
        event = ((r < -0.01).mean(axis=1) >= 0.8) & (r.notna().mean(axis=1) > 0.7)
        days, last = [], None
        for d in event[event].index:
            if last is None or (d - last).days > 30:
                days.append(d)
                last = d
        for H in (5, 21):
            fs, fm = [], []
            for d in days:
                i = close.index.get_loc(d)
                if i + H >= len(close):
                    continue
                fs.append(close[tks].iloc[i + H].div(close[tks].iloc[i]).mean() - 1)
                fm.append(close.iloc[i + H].div(close.iloc[i]).mean() - 1)
            if len(fs) >= 8:
                diff = np.array(fs) - np.array(fm)
                rows.append((sec, H, len(fs), 100 * np.mean(fs), 100 * diff.mean(),
                             stats.ttest_1samp(diff, 0).statistic))
    print(pd.DataFrame(rows, columns=["sector", "H", "n", "fwd%", "vs_mkt%", "t"]).to_string(index=False))

    # ---- 3. laggard catch-up ----
    print("\nTEST 3: within-sector laggards vs leaders, next 21d")
    r21, f21 = close.pct_change(21), close.pct_change(21).shift(-21)
    diffs = []
    for sec, tks in SECTORS.items():
        tks = [t for t in tks if t in r21.columns]
        if len(tks) < 5:
            continue
        g = r21[tks].sub(r21[tks].mean(axis=1), axis=0)
        f = f21[tks].sub(f21[tks].mean(axis=1), axis=0)
        for d in g.index[252::21]:
            row = g.loc[d].dropna()
            if len(row) < 5:
                continue
            v = f.loc[d, row.nsmallest(2).index].mean() - f.loc[d, row.nlargest(2).index].mean()
            if not np.isnan(v):
                diffs.append(v)
    arr = np.array(diffs)
    print(f"  {100*arr.mean():+.2f}%  t={stats.ttest_1samp(arr,0).statistic:.2f}  n={len(arr)}")

    # ---- 4. run-up into volume events ----
    print("\nTEST 4: run-up into volume-spike events -> next 21d")
    ev = (vol > 3.5 * vol.rolling(50).mean().shift(1))
    recs = []
    for tk in close.columns:
        c = close[tk].values
        idx, last = np.where(ev[tk].values)[0], -99
        for i in idx:
            if i - last > 40 and i > 11 and i + 22 < len(c) and not np.isnan(c[i - 11]) and not np.isnan(c[i + 21]):
                recs.append({"runup": c[i - 1] / c[i - 11] - 1, "post": c[i + 21] / c[i] - 1})
                last = i
    e = pd.DataFrame(recs)
    hi = e[e.runup >= e.runup.quantile(0.7)]
    lo = e[e.runup <= e.runup.quantile(0.3)]
    print(f"  big run-up: post-21d {100*hi.post.mean():+.2f}% | weak run-up: {100*lo.post.mean():+.2f}% "
          f"| t={stats.ttest_ind(hi.post, lo.post).statistic:.2f}  n={len(e)}")


if __name__ == "__main__":
    main()
