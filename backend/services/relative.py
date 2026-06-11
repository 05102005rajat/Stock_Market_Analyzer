"""Relative strength vs a benchmark (default SPY).

True relative strength compares a stock's return to the market's. Minervini's
real Trend Template wants an RS *rank* vs the whole universe; we don't have the
universe, but excess return vs SPY is a faithful, honest version of the idea —
far better than the absolute-momentum proxy it replaces.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LOOKBACK = 126  # ~6 months of trading days


def relative_strength(stock_df: pd.DataFrame, bench_df: pd.DataFrame, lookback: int = LOOKBACK) -> dict | None:
    """Excess return of the stock over the benchmark across `lookback` bars.

    Returns None when there isn't enough aligned history.
    """
    bench = bench_df["close"].reindex(stock_df.index, method="ffill")
    s = stock_df["close"].to_numpy(dtype=float)
    b = bench.to_numpy(dtype=float)
    if (len(s) < lookback + 1
            or np.isnan(b[-(lookback + 1):]).any() or b[-lookback] == 0
            or np.isnan(s[-(lookback + 1):]).any() or s[-lookback] == 0):
        return None  # guard BOTH series — a 0/NaN close would emit Infinity/NaN into JSON

    stock_ret = s[-1] / s[-lookback] - 1.0
    bench_ret = b[-1] / b[-lookback] - 1.0
    excess = stock_ret - bench_ret
    return {
        "excess_pct": round(float(excess) * 100, 2),
        "stock_ret_pct": round(float(stock_ret) * 100, 2),
        "bench_ret_pct": round(float(bench_ret) * 100, 2),
        "outperforming": bool(excess > 0),
        # Map to [-1, 1]: ±20% of excess return saturates the score.
        "value": float(max(-1.0, min(1.0, excess / 0.20))),
        "lookback": int(lookback),
    }
