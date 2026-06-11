"""Multi-timeframe trend analysis — the 'read it like an expert' view.

Given a long daily history, classify the trend over several horizons
(1 week … 1 year), report the % change over each, judge how aligned the
timeframes are, and summarize the long-term regime via the 50/200-day SMAs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# (label, approximate trading-day length)
HORIZONS = [("1W", 5), ("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252)]

# Slope threshold in % per bar separating trend from chop (matches patterns.py).
_FLAT = 0.05


def _direction(close: np.ndarray) -> tuple[str, float]:
    """Regression-slope direction over a window → up / down / sideways."""
    n = len(close)
    x = np.arange(n)
    slope = float(np.polyfit(x, close, 1)[0])
    avg = float(np.mean(close)) or 1e-9
    pct_per_bar = slope / avg * 100
    if pct_per_bar > _FLAT:
        return "uptrend", pct_per_bar
    if pct_per_bar < -_FLAT:
        return "downtrend", pct_per_bar
    return "sideways", pct_per_bar


def multi_timeframe(df: pd.DataFrame) -> dict:
    """Per-horizon trend + change, an alignment verdict, and SMA regime."""
    close = df["close"].astype(float)
    n = len(close)

    horizons = []
    for label, bars in HORIZONS:
        if n < bars + 1:
            continue
        window = close.iloc[-(bars + 1):].to_numpy()
        change_pct = (window[-1] / window[0] - 1) * 100
        direction, slope = _direction(window)
        horizons.append(
            {
                "label": label,
                "bars": bars,
                "direction": direction,
                "change_pct": round(float(change_pct), 2),
                "slope_pct_per_bar": round(float(slope), 4),
            }
        )

    dirs = [h["direction"] for h in horizons]
    bull, bear = dirs.count("uptrend"), dirs.count("downtrend")
    total = len(horizons)
    if total and bull == total:
        alignment = "Strong uptrend — every timeframe aligned"
    elif total and bear == total:
        alignment = "Strong downtrend — every timeframe aligned"
    elif bull > bear:
        alignment = "Mostly bullish — timeframes lean up"
    elif bear > bull:
        alignment = "Mostly bearish — timeframes lean down"
    else:
        alignment = "Mixed / choppy — timeframes disagree"

    return {"horizons": horizons, "alignment": alignment, "regime": _regime(close)}


def _regime(close: pd.Series) -> dict:
    """Long-term regime: price vs 50/200-day SMA, and golden/death cross."""
    current = float(close.iloc[-1])
    out: dict = {"price": round(current, 2)}
    for w in (50, 200):
        if len(close) >= w:
            sma = float(close.iloc[-w:].mean())
            out[f"sma{w}"] = round(sma, 2)
            out[f"above_sma{w}"] = bool(current > sma)
        else:
            out[f"sma{w}"] = None
            out[f"above_sma{w}"] = None

    if out.get("sma50") is not None and out.get("sma200") is not None:
        golden = out["sma50"] > out["sma200"]
        out["cross"] = "golden" if golden else "death"
        out["cross_label"] = (
            "Golden cross — 50-day above 200-day (long-term bullish)"
            if golden
            else "Death cross — 50-day below 200-day (long-term bearish)"
        )
    else:
        out["cross"] = None
        out["cross_label"] = "Not enough history for the 50/200-day regime"
    return out
