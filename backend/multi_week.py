"""Roll the train-through-prior-Friday → forecast-the-week test across the last
N weeks and chart the Monday (first-trading-day) direction hit rate, to show
whether ~50% holds out of sample rather than relying on one or two anecdotes.

Run:  ./venv/bin/python -u multi_week.py [N_WEEKS]
Outputs /tmp/monday_hitrate.png and a summary table.
"""
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from services import data, forecast

N_WEEKS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
TICKERS = ["AAPL", "MSFT", "NVDA", "SPY", "KO"]


def week_first_days(idx):
    """Map (isoyear, isoweek) -> position of the first trading day that week."""
    firsts = {}
    for pos, ts in enumerate(idx):
        key = (ts.isocalendar().year, ts.isocalendar().week)
        if key not in firsts:
            firsts[key] = pos
    return firsts


def main():
    print(f"Multi-week out-of-sample test — last {N_WEEKS} weeks\n", flush=True)
    series = {t: data.fetch_ohlcv(t, period="5y", interval="1d") for t in TICKERS}

    # Reference week list from SPY (shared calendar); take the last N_WEEKS that
    # have a prior trading day and at least one forward day.
    ref = series["SPY"]
    firsts = week_first_days(ref.index)
    keys = sorted(firsts.keys())
    target_keys = [k for k in keys if firsts[k] > 0][-N_WEEKS:]

    per_week = []   # (label, monday_hit_fraction, n)
    mon_hits, mon_n = 0, 0
    all_hits, all_n, band_hits, abs_errs = 0, 0, 0, []

    for k in target_keys:
        ref_pos = firsts[k]
        mon_date = ref.index[ref_pos]
        wk_hit, wk_n = 0, 0
        for t in TICKERS:
            idx = series[t].index
            if mon_date not in idx:
                continue
            pos = idx.get_loc(mon_date)
            cutoff = pos - 1
            if cutoff < 260:
                continue
            close = series[t]["close"].to_numpy(float)
            cut_close = close[cutoff]
            # Trading days that actually fall in THIS iso-week (so a holiday-short
            # week doesn't spill into next week's bars).
            wk_days = sum(1 for j in range(pos, len(close))
                          if idx[j].isocalendar().week == k)
            fwd = min(5, wk_days, len(close) - pos)
            if fwd < 1:
                continue
            fc = forecast.forecast(series[t].iloc[: cutoff + 1], horizon=fwd, interval="1d")
            if not fc["available"]:
                continue
            # Monday (first day) direction
            p0 = fc["points"][0]
            a0 = close[pos]
            mon_ok = (np.sign(p0["value"] - cut_close) == np.sign(a0 - cut_close))
            wk_hit += int(mon_ok); wk_n += 1
            mon_hits += int(mon_ok); mon_n += 1
            # full-week stats
            for d in range(fwd):
                p = fc["points"][d]; a = close[pos + d]
                all_ok = (np.sign(p["value"] - cut_close) == np.sign(a - cut_close))
                all_hits += int(all_ok); all_n += 1
                band_hits += int(p["lower"] <= a <= p["upper"])
                abs_errs.append(abs(p["value"] - a) / a)
        if wk_n:
            per_week.append((mon_date.strftime("%m-%d"), wk_hit / wk_n, wk_n))
            print(f"  Week of {mon_date.strftime('%Y-%m-%d')}: Monday dir {wk_hit}/{wk_n} "
                  f"({wk_hit/wk_n*100:.0f}%)", flush=True)

    mon_rate = mon_hits / mon_n if mon_n else 0
    all_rate = all_hits / all_n if all_n else 0
    cover = band_hits / all_n if all_n else 0
    mae = float(np.mean(abs_errs)) if abs_errs else 0
    print("\n" + "=" * 60)
    print(f"Monday direction:   {mon_hits}/{mon_n} ({mon_rate*100:.0f}%)")
    print(f"All-day direction:  {all_hits}/{all_n} ({all_rate*100:.0f}%)")
    print(f"95% band coverage:  {band_hits}/{all_n} ({cover*100:.0f}%)")
    print(f"Mean abs error:     {mae*100:.2f}%")

    # ---- Chart ----
    labels = [w[0] for w in per_week]
    rates = [w[1] * 100 for w in per_week]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    colors = ["#26a69a" if r >= 50 else "#ef5350" for r in rates]
    ax.bar(labels, rates, color=colors, alpha=0.85)
    ax.axhline(50, color="#888", linestyle="--", linewidth=1, label="coin flip (50%)")
    ax.axhline(mon_rate * 100, color="#4f9eff", linestyle="-", linewidth=1.5,
               label=f"overall Monday hit {mon_rate*100:.0f}%")
    ax.set_ylim(0, 100)
    ax.set_ylabel("Monday direction hit rate (%)")
    ax.set_xlabel("week (first trading day)")
    ax.set_title(f"Forecast Monday-direction hit rate — last {len(per_week)} weeks, "
                 f"{len(TICKERS)} tickers (band cover {cover*100:.0f}%)")
    ax.legend()
    fig.tight_layout()
    fig.savefig("/tmp/monday_hitrate.png", dpi=110)
    print("\nchart -> /tmp/monday_hitrate.png")


if __name__ == "__main__":
    main()
