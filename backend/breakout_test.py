"""Do breakouts to new highs actually lead to big gains? Point-in-time, honest.

A 'breakout' = price closes above its highest level of the prior N days (a new
N-day high). We test N = 20 / 50 / 252 (252 ≈ a 52-week high) and measure the
forward 1-/3-/6-month return vs just holding, sampled NON-OVERLAPPING so the
significance is honest. We also check the 'goes up exponentially' hope: after a
52-week-high breakout, how often was it a big winner vs a dud 6 months later?

Run:  ./venv/bin/python -u breakout_test.py
"""
import numpy as np
import pandas as pd

from services import data

# Diverse basket incl. high-momentum names where breakouts 'should' work best.
BASKET = ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "AMD", "AVGO",
          "TSLA", "NFLX", "CVX", "XOM", "WMT", "COST", "JPM", "PG", "JNJ", "UNH"]


def main():
    px = pd.DataFrame({t: data.fetch_ohlcv(t, "5y", "1d")["close"] for t in BASKET}).dropna(how="all")
    print(f"Breakout test — {px.shape[1]} names, 5y, point-in-time\n", flush=True)

    for N in (20, 50, 252):
        prior_high = px.rolling(N).max().shift(1)
        breakout = px > prior_high                      # new N-day high today
        line = []
        for H in (21, 63, 126):
            fwd = px.shift(-H) / px - 1
            sub = px.index[list(range(260, len(px) - H, H))]   # non-overlapping in time
            fwd_sub = fwd.loc[sub]
            bsub = breakout.loc[sub]
            sel = fwd_sub.where(bsub).stack().dropna()
            if len(sel) < 20:
                line.append(f"{H}d: n<20")
                continue
            # per-date breakout vs non-breakout mean, t-tested across dates
            diffs = []
            for dt in sub:
                sd = fwd_sub.loc[dt].where(bsub.loc[dt]).dropna()
                rd = fwd_sub.loc[dt].where(~bsub.loc[dt]).dropna()
                if len(sd) and len(rd):
                    diffs.append(sd.mean() - rd.mean())
            diffs = np.array(diffs)
            t = diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs))) if len(diffs) > 2 else float("nan")
            line.append(f"{H//21}mo: {sel.mean()*100:+.1f}% (vs rest {diffs.mean()*100:+.1f}%, t={t:+.1f}, n={len(sel)})")
        print(f"  New {N}-day high  ->  " + "  |  ".join(line), flush=True)

    # ---- The 'exponential' hope: 6 months after a 52-week-high breakout ----
    print("\n  After a 52-week-high (252-day) breakout, 6 months later:")
    bk = px > px.rolling(252).max().shift(1)
    fwd6 = px.shift(-126) / px - 1
    sub = px.index[list(range(260, len(px) - 126, 126))]
    out = fwd6.loc[sub].where(bk.loc[sub]).stack().dropna()
    if len(out):
        print(f"    samples: {len(out)}  |  median {out.median()*100:+.1f}%  mean {out.mean()*100:+.1f}%")
        print(f"    big winner (>+20%): {(out > 0.20).mean()*100:.0f}%   |   "
              f"flat/loss (<0%): {(out < 0).mean()*100:.0f}%   |   "
              f"worst {out.min()*100:.0f}%  best {out.max()*100:+.0f}%")
    print("\n  Read: an 'edge' is real only if forward return beats buy-hold with t>2, "
          "AND most breakouts (not just a lucky few) actually go up.")


if __name__ == "__main__":
    main()
