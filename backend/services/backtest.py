"""Historical edge backtest for detected candlestick signals.

For every candlestick occurrence across the full history, measure the forward
return at several horizons, then aggregate by pattern into a hit-rate and
average-return table — compared against the *unconditional* baseline so you can
see which signals actually carried an edge for THIS stock.

Educational only: in-sample historical behavior does not predict the future,
and small samples are noisy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services import candlesticks


def run(df: pd.DataFrame, horizons=(5, 10, 20), min_samples: int = 5) -> dict:
    """Backtest candlestick patterns; return per-pattern hit-rate vs baseline."""
    horizons = tuple(int(h) for h in horizons)
    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    if n < max(horizons) + 30:
        return {
            "available": False,
            "reason": "Not enough history to backtest.",
            "horizons": list(horizons),
            "baseline": {},
            "patterns": [],
        }

    # Unconditional baseline: how often is price simply up after h bars, and by how much.
    baseline = {}
    for h in horizons:
        fwd = close[h:] / close[:-h] - 1.0
        baseline[str(h)] = {
            "up_rate": round(float(np.mean(fwd > 0)), 3),
            "avg_return": round(float(np.mean(fwd)) * 100, 2),
        }

    # Every candlestick occurrence across the full series (no cap, full lookback).
    signals = candlesticks.detect(df, lookback=n, max_signals=10**9)
    time_to_i = {int(ts.timestamp()): i for i, ts in enumerate(df.index)}

    groups: dict[tuple, list[int]] = {}
    for s in signals:
        i = time_to_i.get(s["time"])
        if i is not None:
            groups.setdefault((s["name"], s["bias"]), []).append(i)

    rows = []
    for (name, bias), idxs in groups.items():
        stats = {}
        for h in horizons:
            rets = np.array([close[i + h] / close[i] - 1.0 for i in idxs if i + h < n])
            if rets.size == 0:
                stats[str(h)] = None
                continue
            if bias == "bullish":
                win = float(np.mean(rets > 0))
                base = baseline[str(h)]["up_rate"]
            elif bias == "bearish":
                win = float(np.mean(rets < 0))
                base = 1.0 - baseline[str(h)]["up_rate"]
            else:  # neutral patterns (e.g. Doji) — measure up-rate for reference
                win = float(np.mean(rets > 0))
                base = baseline[str(h)]["up_rate"]
            stats[str(h)] = {
                "samples": int(rets.size),
                "win_rate": round(win, 3),
                "avg_return": round(float(np.mean(rets)) * 100, 2),
                "edge": round(win - base, 3),  # win-rate above the baseline
            }
        rows.append({"name": name, "bias": bias, "count": len(idxs), "stats": stats})

    # Rank by edge at the middle horizon; drop tiny, noisy samples.
    mid = str(horizons[len(horizons) // 2])
    rows = [r for r in rows if r["count"] >= min_samples]

    def edge_of(r):
        st = r["stats"].get(mid)
        return st["edge"] if st else -99

    rows.sort(key=edge_of, reverse=True)
    return {
        "available": True,
        "horizons": list(horizons),
        "baseline": baseline,
        "patterns": rows,
        "note": "Win rate is measured against the unconditional baseline. Small samples are noisy.",
    }
