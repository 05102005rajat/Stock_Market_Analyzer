"""Mark Minervini's 'Trend Template' — an 8-point stage-analysis screen.

Given a long daily history, evaluate the eight Trend Template criteria (price
vs 50/150/200-day SMAs, MA stacking and slope, distance from the 52-week
high/low, and a momentum proxy), score the result 0–8, and classify the
Weinstein-style stage. SMAs are simple moving averages of the close.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_MIN_ROWS = 252      # ~1 trading year — needed for SMA200 + 52-week range
_SLOPE_LOOKBACK = 22  # ~1 month of trading days for the SMA200 trend check


def _sma(close: np.ndarray, window: int) -> float:
    """Latest simple moving average over `window` bars."""
    return float(np.mean(close[-window:]))


def trend_template(df: pd.DataFrame, rs_excess: float | None = None) -> dict:
    """Evaluate Minervini's 8-point Trend Template on daily data.

    `rs_excess` is the stock's excess return vs the market (from
    services.relative); when provided it powers criterion 8 as real relative
    strength instead of the absolute-momentum proxy.
    """
    close = df["close"].to_numpy(dtype=float)
    n = len(close)
    if n < _MIN_ROWS:
        return {
            "available": False,
            "reason": f"Need at least {_MIN_ROWS} daily bars, got {n}.",
            "passes": False,
            "score": 0,
            "stage": "Unknown — insufficient history",
            "summary": "Not enough price history to evaluate the Trend Template.",
            "criteria": [],
        }

    price = float(close[-1])
    sma50 = _sma(close, 50)
    sma150 = _sma(close, 150)
    sma200 = _sma(close, 200)
    # SMA200 ~1 month ago, to judge whether the long-term average is rising.
    sma200_prior = float(np.mean(close[-(200 + _SLOPE_LOOKBACK):-_SLOPE_LOOKBACK]))

    low_52w = float(np.min(close[-_MIN_ROWS:]))
    high_52w = float(np.max(close[-_MIN_ROWS:]))
    year_return = price / float(close[-_MIN_ROWS]) - 1.0

    criteria: list[dict] = []

    def add(name: str, passed: bool, detail: str) -> None:
        criteria.append({"name": name, "passed": bool(passed), "detail": detail})

    # 1. Price above both the 150- and 200-day MA.
    c1 = price > sma150 and price > sma200
    add("Price above 150-day and 200-day MA", c1,
        f"Close {price:.2f} vs SMA150 {sma150:.2f}, SMA200 {sma200:.2f}")

    # 2. 150-day MA above the 200-day MA.
    c2 = sma150 > sma200
    add("150-day MA above 200-day MA", c2,
        f"SMA150 {sma150:.2f} vs SMA200 {sma200:.2f}")

    # 3. 200-day MA trending up over the last ~month.
    c3 = sma200 > sma200_prior
    add("200-day MA trending up", c3,
        f"SMA200 {sma200:.2f} vs {_SLOPE_LOOKBACK}d ago {sma200_prior:.2f}")

    # 4. 50-day MA above both the 150- and 200-day MA.
    c4 = sma50 > sma150 and sma50 > sma200
    add("50-day MA above 150-day and 200-day MA", c4,
        f"SMA50 {sma50:.2f} vs SMA150 {sma150:.2f}, SMA200 {sma200:.2f}")

    # 5. Price above the 50-day MA.
    c5 = price > sma50
    add("Price above 50-day MA", c5,
        f"Close {price:.2f} vs SMA50 {sma50:.2f}")

    # 6. Price at least 30% above the 52-week low.
    pct_above_low = (price / low_52w - 1.0) * 100 if low_52w else 0.0
    c6 = price >= 1.30 * low_52w
    add("Price at least 30% above 52-week low", c6,
        f"Close {price:.2f} is {pct_above_low:.2f}% above 52w low {low_52w:.2f}")

    # 7. Price within 25% of the 52-week high.
    pct_below_high = (1.0 - price / high_52w) * 100 if high_52w else 0.0
    c7 = price >= 0.75 * high_52w
    add("Price within 25% of 52-week high", c7,
        f"Close {price:.2f} is {pct_below_high:.2f}% below 52w high {high_52w:.2f}")

    # 8. Relative strength — real excess vs SPY when available, else momentum proxy.
    if rs_excess is not None:
        c8 = rs_excess > 0
        add("Relative strength vs SPY", c8,
            f"{rs_excess:+.2f}% excess return vs SPY (positive = outperforming; "
            f"true template wants RS-rank >= 70, approximated here by market-relative return)")
    else:
        c8 = year_return > 0
        add("Relative strength (momentum proxy)", c8,
            f"1-year return {year_return * 100:.2f}% (proxy; no benchmark provided)")

    score = int(sum(c["passed"] for c in criteria))
    passes = score == 8

    stage = _classify_stage(score, price, sma50, sma150, sma200, c1, c2, c4, c5)
    summary = _summary(passes, score, stage)

    return {
        "available": True,
        "passes": bool(passes),
        "score": score,
        "stage": stage,
        "summary": summary,
        "criteria": criteria,
    }


def _classify_stage(score, price, sma50, sma150, sma200, c1, c2, c4, c5) -> str:
    """Deterministic Weinstein-style stage from the criteria results."""
    if score >= 7 and c1 and c2 and c4 and c5:
        return "Stage 2 — Advancing (uptrend)"
    below_200 = price < sma200
    if score <= 2 and below_200:
        return "Stage 4 — Declining (downtrend)"
    if below_200 and sma50 > sma150:
        return "Stage 1 — Basing"
    return "Stage 3 — Topping / Transitional"


def _summary(passes: bool, score: int, stage: str) -> str:
    if passes:
        return "Passes all 8 Trend Template criteria — a textbook Stage 2 uptrend."
    return f"Meets {score} of 8 Trend Template criteria — {stage}."
