"""Trend classification, support/resistance, and classic chart-pattern detection.

These are heuristic detectors built on local extrema (scipy.signal.argrelextrema)
and linear regression of the closing series. They are meant as analytical aids,
not trading advice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.signal import argrelextrema


def _extrema(values: np.ndarray, order: int):
    """Indices of local maxima and minima with a comparison window of `order`.

    Uses strict comparisons so a flat point is never counted as both a max and
    a min, and drops extrema within `order` of either boundary (those are
    one-sided artifacts, not real swings).
    """
    n = len(values)
    if n < order * 2 + 1:
        return np.array([], dtype=int), np.array([], dtype=int)
    maxima = argrelextrema(values, np.greater, order=order)[0]
    minima = argrelextrema(values, np.less, order=order)[0]
    interior = lambda idx: idx[(idx >= order) & (idx < n - order)]
    maxima = _thin(interior(maxima), order)
    minima = _thin(interior(minima), order)
    return maxima, minima


def _thin(idx: np.ndarray, gap: int) -> np.ndarray:
    if idx.size == 0:
        return idx
    kept = [idx[0]]
    for i in idx[1:]:
        if i - kept[-1] >= gap:
            kept.append(i)
    return np.array(kept, dtype=int)


def trend(df: pd.DataFrame) -> dict:
    """Linear-regression slope over the close series → up / down / sideways."""
    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    if n == 0:
        return {"direction": "sideways", "slope_pct_per_bar": 0.0, "r2": 0.0,
                "start": None, "end": None}
    if n < 2:
        ts = int(df.index[-1].timestamp())
        val = round(float(close[-1]), 4) if n else None
        point = {"time": ts, "value": val}
        return {
            "direction": "sideways",
            "slope_pct_per_bar": 0.0,
            "r2": 0.0,
            "start": point,
            "end": point,
        }
    x = np.arange(n)
    slope, intercept = np.polyfit(x, close, 1)
    fitted = slope * x + intercept
    # Normalize slope by average price to a per-bar percentage.
    avg = float(np.mean(close))
    pct_per_bar = (slope / avg) * 100 if avg else 0.0
    # R² of the fit as a confidence proxy.
    ss_res = float(np.sum((close - fitted) ** 2))
    ss_tot = float(np.sum((close - avg) ** 2)) or 1e-9
    r2 = 1 - ss_res / ss_tot

    if pct_per_bar > 0.05:
        direction = "uptrend"
    elif pct_per_bar < -0.05:
        direction = "downtrend"
    else:
        direction = "sideways"

    return {
        "direction": direction,
        "slope_pct_per_bar": round(pct_per_bar, 4),
        "r2": round(r2, 3),
        "start": {"time": int(df.index[0].timestamp()), "value": round(float(fitted[0]), 4)},
        "end": {"time": int(df.index[-1].timestamp()), "value": round(float(fitted[-1]), 4)},
    }


def support_resistance(df: pd.DataFrame, order: int = 5, max_levels: int = 4) -> dict:
    """Cluster swing highs/lows into price levels, then classify each level as
    support or resistance by its position relative to the *current* price.

    A prior swing high below today's price now acts as support, and a prior
    swing low above today's price acts as resistance — so we partition by price
    rather than by whether the swing was a high or a low.
    """
    close = df["close"].to_numpy(dtype=float)
    if close.size == 0:
        return {"resistance": [], "support": []}
    current = float(close[-1])
    maxima, minima = _extrema(close, order)
    swing_idx = np.concatenate([maxima, minima]).astype(int)
    span = float(np.max(close) - np.min(close)) or 1.0
    tol = span * 0.02  # merge levels within 2% of the price range

    # Cluster all swing prices into levels, tracking touch count (strength).
    prices = sorted(float(close[i]) for i in swing_idx)
    clusters: list[list[float]] = []
    for p in prices:
        if clusters and abs(p - np.mean(clusters[-1])) <= tol:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    levels = [(round(float(np.mean(c)), 4), len(c)) for c in clusters]

    # Resistance = levels above price (nearest first); support = below.
    resistance = sorted((lvl for lvl in levels if lvl[0] > current), key=lambda l: l[0])
    support = sorted((lvl for lvl in levels if lvl[0] < current), key=lambda l: -l[0])
    return {
        "resistance": [lvl for lvl, _ in resistance[:max_levels]],
        "support": [lvl for lvl, _ in support[:max_levels]],
    }


def _markers(df, indices, label, position, color):
    return [
        {
            "time": int(df.index[i].timestamp()),
            "date": df.index[i].strftime("%Y-%m-%d"),
            "price": round(float(df["close"].iloc[i]), 4),
            "label": label,
            "position": position,
            "color": color,
        }
        for i in indices
    ]


def detect_patterns(df: pd.DataFrame, order: int = 5) -> list[dict]:
    """Detect double top/bottom and head-and-shoulders from swing extrema."""
    close = df["close"].to_numpy(dtype=float)
    if close.size == 0:
        return []
    maxima, minima = _extrema(close, order)
    span = float(np.max(close) - np.min(close)) or 1.0
    tol = span * 0.03
    found: list[dict] = []

    # --- Double Top: two comparable peaks separated by a trough ---
    for a, b in zip(maxima, maxima[1:]):
        if abs(close[a] - close[b]) <= tol:
            between = [m for m in minima if a < m < b]
            if between:
                trough = min(between, key=lambda m: close[m])
                if close[trough] < min(close[a], close[b]) - tol:
                    found.append(
                        _pattern("Double Top", "bearish", df, [a, trough, b],
                                 "A reversal pattern: two peaks at a similar level "
                                 "suggest buyers are losing momentum.")
                    )

    # --- Double Bottom: two comparable troughs separated by a peak ---
    for a, b in zip(minima, minima[1:]):
        if abs(close[a] - close[b]) <= tol:
            between = [m for m in maxima if a < m < b]
            if between:
                peak = max(between, key=lambda m: close[m])
                if close[peak] > max(close[a], close[b]) + tol:
                    found.append(
                        _pattern("Double Bottom", "bullish", df, [a, peak, b],
                                 "A reversal pattern: two troughs at a similar level "
                                 "suggest sellers are exhausting.")
                    )

    # --- Head and Shoulders: peak-head-peak with a higher middle peak ---
    for l, h, r in zip(maxima, maxima[1:], maxima[2:]):
        if close[h] > close[l] and close[h] > close[r] and abs(close[l] - close[r]) <= tol * 1.5:
            found.append(
                _pattern("Head & Shoulders", "bearish", df, [l, h, r],
                         "A topping pattern: a high central peak (head) flanked by "
                         "two lower peaks (shoulders) signals a potential reversal down.")
            )

    # --- Inverse Head and Shoulders ---
    for l, h, r in zip(minima, minima[1:], minima[2:]):
        if close[h] < close[l] and close[h] < close[r] and abs(close[l] - close[r]) <= tol * 1.5:
            found.append(
                _pattern("Inverse Head & Shoulders", "bullish", df, [l, h, r],
                         "A bottoming pattern: a low central trough flanked by two "
                         "higher troughs signals a potential reversal up.")
            )

    # Keep the most recent, non-overlapping reversal detections.
    found.sort(key=lambda p: p["points"][-1]["time"], reverse=True)
    reversals = _dedupe(found)[:5]

    # Triangles span a wide window, so detect them separately and append.
    triangles = _detect_triangles(df, maxima, minima)
    combined = reversals + triangles
    combined.sort(key=lambda p: p["points"][-1]["time"], reverse=True)
    return combined[:6]


def _detect_triangles(df: pd.DataFrame, maxima: np.ndarray, minima: np.ndarray) -> list[dict]:
    """Ascending / descending / symmetrical triangles from recent swing trend lines.

    Fits a line through the recent swing highs and another through the recent
    swing lows; the relative slopes classify the triangle.
    """
    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    cutoff = int(n * 0.55)  # only the recent portion forms the triangle
    rh = [i for i in maxima if i >= cutoff]
    rl = [i for i in minima if i >= cutoff]
    if len(rh) < 3 or len(rl) < 3:
        return []

    avg = float(np.mean(close[cutoff:])) or 1.0
    slope_h = float(np.polyfit(rh, close[rh], 1)[0]) / avg * 100  # %/bar
    slope_l = float(np.polyfit(rl, close[rl], 1)[0]) / avg * 100
    flat = 0.03  # |slope| below this is "flat"

    if abs(slope_h) < flat and slope_l > flat:
        name, bias, desc = (
            "Ascending Triangle", "bullish",
            "A flat resistance with rising support — buyers stepping up; "
            "often resolves upward.",
        )
    elif slope_h < -flat and abs(slope_l) < flat:
        name, bias, desc = (
            "Descending Triangle", "bearish",
            "A flat support with falling resistance — sellers pressing down; "
            "often resolves downward.",
        )
    elif slope_h < -flat and slope_l > flat:
        name, bias, desc = (
            "Symmetrical Triangle", "neutral",
            "Converging highs and lows — a coil that breaks in the direction "
            "of the eventual breakout.",
        )
    else:
        return []

    idx = sorted(set(rh + rl))
    return [_pattern(name, bias, df, [idx[0], idx[-1]], desc)]


def _pattern(name, bias, df, indices, description) -> dict:
    return {
        "name": name,
        "bias": bias,
        "description": description,
        "points": [
            {
                "time": int(df.index[i].timestamp()),
                "date": df.index[i].strftime("%Y-%m-%d"),
                "price": round(float(df["close"].iloc[i]), 4),
            }
            for i in indices
        ],
    }


def _dedupe(patterns: list[dict]) -> list[dict]:
    """Drop patterns whose index span overlaps a stronger earlier-listed one."""
    kept: list[dict] = []
    used: list[tuple[int, int]] = []
    for p in patterns:
        lo = p["points"][0]["time"]
        hi = p["points"][-1]["time"]
        if any(not (hi < a or lo > b) for a, b in used):
            continue
        used.append((lo, hi))
        kept.append(p)
    return kept


def analyze(df: pd.DataFrame, order: int = 5) -> dict:
    return {
        "trend": trend(df),
        "levels": support_resistance(df, order=order),
        "patterns": detect_patterns(df, order=order),
    }
