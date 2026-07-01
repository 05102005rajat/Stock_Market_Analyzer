"""Does buying the RECOVERY work? — honest, point-in-time backtest.

User's hypothesis: when a stock falls below its 200-day AND rapidly crashes, then
starts RECOVERING / turning back up, is that a good time to buy?

We pre-specify FIVE definitions of "crashed then recovering" (no cherry-picking;
all are reported), and for each measure forward 1/3/6-month returns vs honest
benchmarks:
  - vs every OTHER stock on the same date  (controls for market-wide moves)
  - vs "still weak" crashed stocks (below BOTH 200d and 50d) — the falling knives
  - vs just buy-and-hold this stock at a random time
Significance uses NON-OVERLAPPING dates + a per-date difference t-test, the only
honest way (overlapping H-day windows inflate t by ~sqrt(H)).

CAVEAT baked in: survivorship bias. yfinance only has stocks that exist today, so
"buy the recovery" is flattered. We deliberately include names that crashed and
did NOT fully recover (WBA, INTC, T, PYPL, ROKU, CVNA, VZ, PFE...) to push back.

CLI:  ./venv/bin/python recovery_test.py <SIGNAL|ALL>     (prints JSON)
      SIGNAL in {R1_reclaim50, R2_recovering_state, R3_reclaim200, R4_bounce_low,
                 R5_slope50_up, STILL_WEAK}
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

from services import data

# Sector-diverse universe. Deliberately includes big-drawdown names that did NOT
# cleanly recover, to fight survivorship bias (the central trap of this test).
UNIVERSE = [
    # mega/large tech (mostly recovered)
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AVGO", "TSLA", "NFLX", "AMD",
    "QCOM", "TXN", "MU", "AMAT", "LRCX", "ADBE", "CRM", "ORCL", "CSCO", "IBM",
    # crashed HARD, recovery mixed-to-poor (anti-survivorship ballast)
    "PYPL", "INTC", "BA", "DIS", "NKE", "PFE", "MRNA", "ROKU", "PLTR", "COIN",
    "CVNA", "T", "VZ", "WBA", "SHOP", "SNOW", "NET", "CRWD", "DDOG", "ABNB",
    "UBER", "RBLX", "ETSY", "DOCU", "ZM", "TGT", "SBUX", "NKE",
    # finance
    "JPM", "BAC", "GS", "MS", "WFC", "C",
    # health / staples
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "BMY", "WMT", "COST", "PG", "KO", "PEP", "MCD",
    # energy / utilities / industrials  (incl. the user's holdings)
    "XOM", "CVX", "NEE", "DUK", "SO", "CEG", "VST", "CAT", "DE", "GE", "HON", "UNP",
    # the user's other singles
    "PDD", "AZO", "HD", "LOW",
]
UNIVERSE = sorted(set(UNIVERSE))

CACHE = os.path.join(os.path.dirname(__file__), ".recovery_cache.pkl")
DD = 0.20            # "rapidly fell" = drew down >=20% from its 1y high recently
RECENT = 63         # ...within the last ~3 months
HORIZONS = (21, 63, 126)   # 1 / 3 / 6 months forward


def load_closes(period: str = "10y") -> pd.DataFrame:
    """Wide DataFrame of adjusted closes (date x ticker), cached to disk so the
    workflow agents read locally instead of re-hitting Yahoo."""
    if os.path.exists(CACHE):
        return pd.read_pickle(CACHE)
    cols = {}
    for t in UNIVERSE:
        try:
            cols[t] = data.fetch_ohlcv(t, period, "1d")["close"]
        except Exception as e:
            print(f"skip {t}: {e}", file=sys.stderr)
    px = pd.DataFrame(cols).sort_index()
    px.to_pickle(CACHE)
    return px


def features(px: pd.DataFrame) -> dict:
    """Point-in-time feature frames (everything uses data <= t only)."""
    sma50 = px.rolling(50).mean()
    sma200 = px.rolling(200).mean()
    hi252 = px.rolling(252).max()
    dd = px / hi252 - 1                         # current drawdown from 1y high
    crashed = dd.rolling(RECENT).min() <= -DD   # fell >=DD within last ~3 months
    below200 = px < sma200
    above50 = px > sma50
    enough = px.notna().rolling(400).sum() >= 400   # >=1.5y history (maturity guard)
    return dict(px=px, sma50=sma50, sma200=sma200, dd=dd, crashed=crashed,
                below200=below200, above50=above50, enough=enough)


def signal(key: str, f: dict) -> pd.DataFrame:
    """Boolean mask (date x ticker) for each pre-specified definition."""
    px, below200, above50, crashed, enough = (
        f["px"], f["below200"], f["above50"], f["crashed"], f["enough"])
    sma50, sma200 = f["sma50"], f["sma200"]
    base = crashed & enough
    if key == "R1_reclaim50":          # day it crosses back above the 50-day, still below 200
        cross = above50 & ~above50.shift(1, fill_value=False)
        return below200 & cross & base
    if key == "R2_recovering_state":   # the app's "recovering" label: below 200 but above 50
        return below200 & above50 & base
    if key == "R3_reclaim200":         # reclaims the 200-day from below ("fully healed")
        return (px > sma200) & (px.shift(1) <= sma200.shift(1)) & base
    if key == "R4_bounce_low":         # up >=10% off its 2-month low, still below 200
        off_low = px / px.rolling(60).min() - 1
        return below200 & (off_low >= 0.10) & base
    if key == "R5_slope50_up":         # the 50-day average itself turning up, still below 200
        return below200 & (sma50 > sma50.shift(20)) & base
    if key == "STILL_WEAK":            # falling knife: crashed, below BOTH lines
        return below200 & ~above50 & base
    raise ValueError(key)


def _perdate_diff_t(fwd: pd.DataFrame, mask: pd.DataFrame, H: int):
    """Non-overlapping per-date difference test: on each sampled date compare mean
    forward return of SELECTED vs NON-selected stocks; t across dates. Honest."""
    dates = fwd.index[list(range(260, len(fwd) - H, H))]   # stride H = non-overlapping
    diffs = []
    for dt in dates:
        sel = fwd.loc[dt].where(mask.loc[dt]).dropna()
        rest = fwd.loc[dt].where(~mask.loc[dt]).dropna()
        if len(sel) and len(rest):
            diffs.append(sel.mean() - rest.mean())
    diffs = np.array(diffs)
    if len(diffs) > 2:
        t = diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs)))
    else:
        t = float("nan")
    return dict(diff_pct=round(float(diffs.mean()) * 100, 2) if len(diffs) else None,
                t=round(float(t), 2), n_dates=int(len(diffs)))


def evaluate(key: str, f: dict, weak_mask: pd.DataFrame) -> dict:
    px = f["px"]
    mask = signal(key, f)
    out = {"signal": key, "horizons": {}}
    for H in HORIZONS:
        fwd = px.shift(-H) / px - 1
        vals = fwd.where(mask).stack().dropna()                 # pooled descriptive
        if len(vals) < 20:
            out["horizons"][f"{H//21}mo"] = {"n": int(len(vals)), "note": "underpowered (<20)"}
            continue
        rec = {
            "n": int(len(vals)),
            "mean_pct": round(float(vals.mean()) * 100, 2),
            "median_pct": round(float(vals.median()) * 100, 2),
            "win_pct": round(float((vals > 0).mean()) * 100, 1),
            "big_win_pct": round(float((vals > 0.20).mean()) * 100, 1),   # >+20%
            "dud_pct": round(float((vals < 0).mean()) * 100, 1),
            "worst_pct": round(float(vals.min()) * 100, 1),
            "p25_pct": round(float(vals.quantile(0.25)) * 100, 1),         # downside
            "vs_other_stocks_same_date": _perdate_diff_t(fwd, mask, H),
        }
        out["horizons"][f"{H//21}mo"] = rec
    # recovering-vs-stillweak: does the recovery filter beat the falling knives?
    if key != "STILL_WEAK":
        H = 63
        fwd = px.shift(-H) / px - 1
        a = fwd.where(mask).stack().dropna()
        b = fwd.where(weak_mask).stack().dropna()
        # per-date: mean(recovering) - mean(still_weak) on shared dates
        dates = fwd.index[list(range(260, len(fwd) - H, H))]
        diffs = []
        for dt in dates:
            ra = fwd.loc[dt].where(mask.loc[dt]).dropna()
            rb = fwd.loc[dt].where(weak_mask.loc[dt]).dropna()
            if len(ra) and len(rb):
                diffs.append(ra.mean() - rb.mean())
        diffs = np.array(diffs)
        t = diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs))) if len(diffs) > 2 else float("nan")
        out["recovering_minus_stillweak_3mo"] = {
            "recovering_mean_pct": round(float(a.mean()) * 100, 2) if len(a) else None,
            "stillweak_mean_pct": round(float(b.mean()) * 100, 2) if len(b) else None,
            "diff_pct": round(float(diffs.mean()) * 100, 2) if len(diffs) else None,
            "t": round(float(t), 2), "n_dates": int(len(diffs)),
        }
    return out


def baseline(px: pd.DataFrame) -> dict:
    """Unconditional buy-hold-at-random-day forward returns, for reference."""
    out = {}
    for H in HORIZONS:
        fwd = (px.shift(-H) / px - 1).stack().dropna()
        out[f"{H//21}mo"] = {
            "mean_pct": round(float(fwd.mean()) * 100, 2),
            "median_pct": round(float(fwd.median()) * 100, 2),
            "win_pct": round(float((fwd > 0).mean()) * 100, 1),
        }
    return out


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "ALL"
    px = load_closes()
    f = features(px)
    weak = signal("STILL_WEAK", f)
    keys = ["R1_reclaim50", "R2_recovering_state", "R3_reclaim200",
            "R4_bounce_low", "R5_slope50_up", "STILL_WEAK"]
    if arg == "ALL":
        res = {"universe_n": px.shape[1], "rows": int(px.shape[0]),
               "span": [str(px.index[0].date()), str(px.index[-1].date())],
               "buy_hold_baseline": baseline(px),
               "results": [evaluate(k, f, weak) for k in keys]}
    else:
        res = {"universe_n": px.shape[1], "buy_hold_baseline": baseline(px),
               "results": [evaluate(arg, f, weak)]}
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
