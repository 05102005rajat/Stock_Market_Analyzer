"""Volume analytics and volume-based trading signals (pandas/numpy only).

Detects volume spikes, dry-ups, and volume-confirmed breakouts/breakdowns,
plus an On-Balance-Volume trend. Volume is unreliable or absent for many FX
pairs and some indices, so an all-zero/NaN series is handled gracefully.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _has_volume(volume: pd.Series) -> bool:
    """True only if the series carries real, non-zero volume."""
    v = volume.fillna(0.0)
    return bool(v.sum() != 0) and bool(np.isfinite(v).any())


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Cumulative sign(close.diff()) * volume."""
    direction = np.sign(close.diff().fillna(0.0))
    return (direction * volume.fillna(0.0)).cumsum()


def _obv_trend(obv: pd.Series, window: int = 20) -> str:
    """Sign of the OBV regression slope over the last `window` bars."""
    tail = obv.tail(window).to_numpy(dtype=float)
    if tail.size < 2:
        return "flat"
    x = np.arange(tail.size)
    slope = float(np.polyfit(x, tail, 1)[0])
    # Normalize by the OBV scale so the "flat" threshold is dimensionless.
    scale = float(np.mean(np.abs(tail))) or 1.0
    norm = slope / scale
    if norm > 0.01:
        return "rising"
    if norm < -0.01:
        return "falling"
    return "flat"


def analyze(df: pd.DataFrame, lookback: int = 40, max_signals: int = 10) -> dict:
    """Volume analytics + recent volume-based signals."""
    volume = df["volume"]
    close = df["close"]

    if not _has_volume(volume):
        return {"available": False, "latest_ratio": None, "obv_trend": "flat", "signals": []}

    volume = volume.fillna(0.0)
    n = len(df)

    # Trailing averages (min_periods so early bars don't crash; they stay NaN).
    avg50 = volume.rolling(window=50, min_periods=20).mean()
    avg5 = volume.rolling(window=5, min_periods=3).mean()
    high20 = close.rolling(window=20, min_periods=20).max()
    low20 = close.rolling(window=20, min_periods=20).min()
    up = close.diff() > 0

    latest_ratio = None
    if avg50.notna().iloc[-1] and avg50.iloc[-1] > 0:
        latest_ratio = round(float(volume.iloc[-1] / avg50.iloc[-1]), 3)

    obv = _obv(close, volume)
    obv_trend = _obv_trend(obv)

    signals: list[dict] = []

    def make(i: int, name: str, bias: str, strength: float, description: str) -> dict:
        return {
            "category": "volume",
            "name": name,
            "bias": bias,
            "time": int(df.index[i].timestamp()),
            "date": df.index[i].strftime("%Y-%m-%d"),
            "strength": round(float(min(max(strength, 0.0), 1.0)), 3),
            "description": description,
        }

    start = max(n - lookback, 0)
    dryups: list[dict] = []  # collected separately so we can cap them

    for i in range(start, n):
        a50 = avg50.iloc[i]
        if pd.isna(a50) or a50 <= 0:
            continue  # trailing average undefined → skip
        vol = float(volume.iloc[i])
        ratio = vol / a50

        # --- Volume Spike: >= 2x the 50-day average ---
        if ratio >= 2.0:
            closed_up = bool(up.iloc[i])
            bias = "bullish" if closed_up else "bearish"
            strength = (ratio - 2.0) / 2.0 + 0.5  # 2x→0.5, 4x→1.0
            direction = "up" if closed_up else "down"
            signals.append(make(
                i, "Volume Spike", bias, strength,
                f"Volume was {ratio:.1f}x its 50-day average as price closed {direction}, "
                "signalling unusually strong participation.",
            ))

        # --- Breakout / Breakdown on Volume: new 20-day close extreme on >=1.5x ---
        if ratio >= 1.5 and not pd.isna(high20.iloc[i]):
            if float(close.iloc[i]) >= float(high20.iloc[i]):
                strength = min((ratio - 1.5) / 2.5 + 0.5, 1.0)
                signals.append(make(
                    i, "Breakout on Volume", "bullish", strength,
                    f"Price made a new 20-day high on {ratio:.1f}x average volume, "
                    "confirming the breakout with conviction.",
                ))
            elif float(close.iloc[i]) <= float(low20.iloc[i]):
                strength = min((ratio - 1.5) / 2.5 + 0.5, 1.0)
                signals.append(make(
                    i, "Breakdown on Volume", "bearish", strength,
                    f"Price made a new 20-day low on {ratio:.1f}x average volume, "
                    "confirming the breakdown with conviction.",
                ))

        # --- Volume Dry-Up: 5-day avg <= 0.5x the 50-day avg ---
        a5 = avg5.iloc[i]
        if not pd.isna(a5) and a5 <= 0.5 * a50:
            contraction = a5 / a50  # smaller → stronger dry-up
            strength = 1.0 - contraction  # at 0.5x → 0.5
            dryups.append(make(
                i, "Volume Dry-Up", "neutral", strength,
                f"Recent volume contracted to {contraction:.0%} of the 50-day average, "
                "a quiet base that often precedes a move.",
            ))

    # Cap dry-ups to the two most recent so they don't spam the feed.
    dryups.sort(key=lambda s: s["time"], reverse=True)
    signals.extend(dryups[:2])

    signals.sort(key=lambda s: s["time"], reverse=True)
    return {
        "available": True,
        "latest_ratio": latest_ratio,
        "obv_trend": obv_trend,
        "signals": signals[:max_signals],
    }
