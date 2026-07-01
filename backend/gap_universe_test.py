"""Gap continuation vs fade — UNIVERSE test (run on a machine with internet).

Tests the hypothesis: "opens below last close -> keeps going down; opens
above -> keeps going up" across the 80-name universe, 10y, with per-date
t-tests. Downloads OHLC (with opens) via yfinance and caches to
.gap_cache.pkl so reruns are offline.

Definitions (same as services/gaps.py):
  gap = open / prior_close - 1; events: |gap| >= 0.5%; big = |gap| >= 2%
  CONTINUED (gap up) = close > open;  FADED = low touched prior close
  Also measures NEXT-day follow-through (his original phrasing is ambiguous
  between intraday and next-day, so both are reported).

Run:  ./venv/bin/python gap_universe_test.py
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
from scipy import stats

from services.sector import SECTORS

CACHE = ".gap_cache.pkl"
TICKERS = sorted({t for tks in SECTORS.values() for t in tks})


def load() -> dict:
    if os.path.exists(CACHE):
        return pd.read_pickle(CACHE)
    import yfinance as yf
    raw = yf.download(TICKERS, period="10y", interval="1d",
                      auto_adjust=True, group_by="column", progress=False)
    data = {k.lower(): raw[k] for k in ("Open", "High", "Low", "Close")}
    pd.to_pickle(data, CACHE)
    return data


def main():
    d = load()
    o, h, l, c = d["open"], d["high"], d["low"], d["close"]
    pc = c.shift(1)
    gap = o / pc - 1
    o2c = c / o - 1
    nxt = c.pct_change().shift(-1)

    print(f"universe: {o.shape[1]} names, {o.shape[0]} bars\n")
    print(f"{'event':22s} {'n':>7s} {'cont%':>6s} {'fade%':>6s} {'avg o->c':>9s} {'t(o->c)':>8s} {'next-day':>9s}")
    for label, m, cont, fade in [
        ("gap UP small .5-2%", (gap >= 0.005) & (gap < 0.02), c > o, l <= pc),
        ("gap UP big >=2%",    gap >= 0.02,                   c > o, l <= pc),
        ("gap DOWN small",     (gap <= -0.005) & (gap > -0.02), c < o, h >= pc),
        ("gap DOWN big <=-2%", gap <= -0.02,                  c < o, h >= pc),
    ]:
        m = m & gap.notna() & o2c.notna()
        n = int(m.sum().sum())
        ev_o2c = o2c.where(m).stack()
        ev_nxt = nxt.where(m).stack().dropna()
        t = stats.ttest_1samp(ev_o2c.dropna(), 0)
        print(f"{label:22s} {n:7d} {100*cont.where(m).stack().mean():6.1f} "
              f"{100*fade.where(m).stack().mean():6.1f} {100*ev_o2c.mean():+8.2f}% "
              f"{t.statistic:8.2f} {100*ev_nxt.mean():+8.2f}%")

    print("\nReading: cont% = day closed in the gap's direction (the user's")
    print("hypothesis). fade% = price traded back to touch yesterday's close")
    print("intraday. If avg o->c is NEGATIVE after gap-ups (and positive after")
    print("gap-downs), the market FADES gaps on average — the documented result.")


if __name__ == "__main__":
    main()
