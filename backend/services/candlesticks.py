"""Classic candlestick pattern detection.

Heuristic single-, two-, and three-bar candlestick detectors built on simple
per-bar geometry (body, range, shadows) with numpy/pandas only. These are
analytical aids, not trading advice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _metrics(df: pd.DataFrame) -> dict:
    """Per-bar geometry arrays used by every detector below."""
    o = df["open"].to_numpy(dtype=float)
    h = df["high"].to_numpy(dtype=float)
    l = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    body = c - o
    body_abs = np.abs(body)
    rng = np.maximum(h - l, 1e-9)  # guard against zero-range bars
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    return {
        "o": o, "h": h, "l": l, "c": c,
        "body": body, "body_abs": body_abs, "rng": rng,
        "upper": upper, "lower": lower,
    }


def _trend_dir(c: np.ndarray, i: int) -> int:
    """Prior-trend context for bar i: -1 downtrend, +1 uptrend, 0 unknown.

    Compares close[i-1] to close[i-5] so the pattern bar itself is excluded.
    """
    if i - 5 < 0:
        return 0
    diff = c[i - 1] - c[i - 5]
    if diff < 0:
        return -1
    if diff > 0:
        return 1
    return 0


def _clamp(x: float) -> float:
    """Clamp a raw strength score into [0.3, 1.0]."""
    return float(min(1.0, max(0.3, x)))


def detect(df: pd.DataFrame, lookback: int = 40, max_signals: int = 12) -> list[dict]:
    """Scan the last `lookback` bars for candlestick patterns and return
    unified signal dicts, most-recent first, capped at max_signals."""
    n = len(df)
    if n == 0:
        return []
    m = _metrics(df)
    o, h, l, c = m["o"], m["h"], m["l"], m["c"]
    body, body_abs, rng = m["body"], m["body_abs"], m["rng"]
    upper, lower = m["upper"], m["lower"]

    # Window of bars to *report* on; multi-bar/trend logic may peek earlier.
    start = max(0, n - lookback)
    signals: list[dict] = []

    def emit(i: int, name: str, bias: str, strength: float, description: str) -> None:
        signals.append({
            "category": "candlestick",
            "name": name,
            "bias": bias,
            "time": int(df.index[i].timestamp()),
            "date": df.index[i].strftime("%Y-%m-%d"),
            "strength": round(_clamp(strength), 2),
            "description": description,
        })

    for i in range(start, n):
        bull = body[i] > 0
        bear = body[i] < 0
        trend = _trend_dir(c, i)

        # ---------------- SINGLE-BAR ----------------
        # Doji: negligible real body relative to range.
        if body_abs[i] <= 0.1 * rng[i]:
            strength = 1.0 - body_abs[i] / (0.1 * rng[i])
            emit(i, "Doji", "neutral", 0.4 + 0.6 * strength,
                 "Open and close are nearly equal, signalling indecision between buyers and sellers.")

        # Marubozu: both shadows tiny → conviction candle.
        if upper[i] < 0.05 * rng[i] and lower[i] < 0.05 * rng[i] and body_abs[i] > 0.6 * rng[i]:
            tiny = 1.0 - (upper[i] + lower[i]) / (0.1 * rng[i])
            if bull:
                emit(i, "Bullish Marubozu", "bullish", 0.6 + 0.4 * tiny,
                     "A full-bodied up candle with virtually no shadows, showing strong buying pressure.")
            elif bear:
                emit(i, "Bearish Marubozu", "bearish", 0.6 + 0.4 * tiny,
                     "A full-bodied down candle with virtually no shadows, showing strong selling pressure.")

        # Hammer / Hanging Man: long lower shadow, small body in the upper part.
        small_body = body_abs[i] <= 0.4 * rng[i]
        if (lower[i] >= 2 * body_abs[i] and upper[i] <= 0.3 * body_abs[i] + 0.05 * rng[i]
                and small_body and body_abs[i] > 0):
            ratio = lower[i] / (body_abs[i] + 1e-9)
            score = 0.4 + 0.15 * (ratio - 2)
            if trend < 0:
                emit(i, "Hammer", "bullish", score,
                     "A long lower wick after a decline shows buyers rejecting lower prices, hinting at a bullish reversal.")
            elif trend > 0:
                emit(i, "Hanging Man", "bearish", score,
                     "A long lower wick after an advance warns that selling pressure is emerging near the top.")

        # Inverted Hammer / Shooting Star: long upper shadow, small body low in range.
        if (upper[i] >= 2 * body_abs[i] and lower[i] <= 0.3 * body_abs[i] + 0.05 * rng[i]
                and small_body and body_abs[i] > 0):
            ratio = upper[i] / (body_abs[i] + 1e-9)
            score = 0.4 + 0.15 * (ratio - 2)
            if trend < 0:
                emit(i, "Inverted Hammer", "bullish", score,
                     "A long upper wick after a decline shows buyers testing higher prices, hinting at a bullish reversal.")
            elif trend > 0:
                emit(i, "Shooting Star", "bearish", score,
                     "A long upper wick after an advance shows buyers rejected at the highs, hinting at a bearish reversal.")

        # ---------------- TWO-BAR ----------------
        if i >= 1:
            po, pc = o[i - 1], c[i - 1]
            pbody = pc - po
            pbody_abs = abs(pbody)
            pmid = (po + pc) / 2.0

            # Bullish Engulfing: up body fully engulfs prior down body.
            if (pbody < 0 and bull and o[i] <= pc and c[i] >= po and body_abs[i] > pbody_abs):
                over = (body_abs[i] - pbody_abs) / (pbody_abs + 1e-9)
                emit(i, "Bullish Engulfing", "bullish", 0.5 + 0.5 * min(over, 1.0),
                     "A large up candle completely engulfs the prior down candle, signalling a bullish reversal.")
            # Bearish Engulfing.
            if (pbody > 0 and bear and o[i] >= pc and c[i] <= po and body_abs[i] > pbody_abs):
                over = (body_abs[i] - pbody_abs) / (pbody_abs + 1e-9)
                emit(i, "Bearish Engulfing", "bearish", 0.5 + 0.5 * min(over, 1.0),
                     "A large down candle completely engulfs the prior up candle, signalling a bearish reversal.")

            # Bullish Harami: small up body inside prior large down body.
            if (pbody < 0 and bull and pbody_abs > 0 and body_abs[i] < pbody_abs
                    and o[i] >= pc and c[i] <= po):
                inside = 1.0 - body_abs[i] / (pbody_abs + 1e-9)
                emit(i, "Bullish Harami", "bullish", 0.4 + 0.5 * inside,
                     "A small up candle contained within the prior large down candle hints that selling is stalling.")
            # Bearish Harami.
            if (pbody > 0 and bear and pbody_abs > 0 and body_abs[i] < pbody_abs
                    and o[i] <= pc and c[i] >= po):
                inside = 1.0 - body_abs[i] / (pbody_abs + 1e-9)
                emit(i, "Bearish Harami", "bearish", 0.4 + 0.5 * inside,
                     "A small down candle contained within the prior large up candle hints that buying is stalling.")

            # Piercing Line: prior bearish, current opens at/below prior close,
            # closes above prior midpoint but below prior open.
            if (pbody < 0 and bull and o[i] <= pc and pmid < c[i] < po):
                depth = (c[i] - pmid) / (pbody_abs / 2.0 + 1e-9)
                emit(i, "Piercing Line", "bullish", 0.5 + 0.4 * min(depth, 1.0),
                     "An up candle opens below and closes back above the midpoint of the prior down candle, a bullish reversal sign.")
            # Dark Cloud Cover (mirror).
            if (pbody > 0 and bear and o[i] >= pc and po < c[i] < pmid):
                depth = (pmid - c[i]) / (pbody_abs / 2.0 + 1e-9)
                emit(i, "Dark Cloud Cover", "bearish", 0.5 + 0.4 * min(depth, 1.0),
                     "A down candle opens above and closes back below the midpoint of the prior up candle, a bearish reversal sign.")

        # ---------------- THREE-BAR ----------------
        if i >= 2:
            o1, c1 = o[i - 2], c[i - 2]
            o2, c2 = o[i - 1], c[i - 1]
            b1, b2, b3 = c1 - o1, c2 - o2, body[i]
            a1, a2, a3 = abs(b1), abs(b2), body_abs[i]
            mid1 = (o1 + c1) / 2.0

            # Morning Star: big down, small star, big up closing past first midpoint.
            if (b1 < 0 and a2 < a1 * 0.5 and bull and a3 > a1 * 0.5 and c[i] > mid1):
                push = (c[i] - mid1) / (a1 / 2.0 + 1e-9)
                emit(i, "Morning Star", "bullish", 0.55 + 0.4 * min(push, 1.0),
                     "A small-bodied star between a large down and a large up candle marks a bullish three-bar reversal.")
            # Evening Star.
            if (b1 > 0 and a2 < a1 * 0.5 and bear and a3 > a1 * 0.5 and c[i] < mid1):
                push = (mid1 - c[i]) / (a1 / 2.0 + 1e-9)
                emit(i, "Evening Star", "bearish", 0.55 + 0.4 * min(push, 1.0),
                     "A small-bodied star between a large up and a large down candle marks a bearish three-bar reversal.")

            # Three White Soldiers: three rising up candles, each opening inside the prior body.
            if (b1 > 0 and b2 > 0 and b3 > 0 and c2 > c1 and c[i] > c2
                    and o1 < o2 < c1 and o2 < o[i] < c2):
                emit(i, "Three White Soldiers", "bullish", 0.7,
                     "Three consecutive strong up candles closing progressively higher signal sustained buying.")
            # Three Black Crows.
            if (b1 < 0 and b2 < 0 and b3 < 0 and c2 < c1 and c[i] < c2
                    and c1 < o2 < o1 and c2 < o[i] < o2):
                emit(i, "Three Black Crows", "bearish", 0.7,
                     "Three consecutive strong down candles closing progressively lower signal sustained selling.")

    # Most-recent first, then cap.
    signals.sort(key=lambda s: s["time"], reverse=True)
    return signals[:max_signals]
