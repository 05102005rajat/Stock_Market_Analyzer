"""Composite TECHNICAL POSTURE score with a confidence interval.

Aggregates the independent technical reads — trend, multi-timeframe alignment,
50/200 SMA regime, RSI, MACD, Minervini stage, recent candlesticks, volume,
chart patterns, and relative strength — into:

  * a structure score in [-100, +100] (bearish ←→ bullish),
  * a posture label (Strongly Bearish … Strongly Bullish),
  * a confidence level driven by how much the components AGREE, and
  * a score interval (score ± weighted dispersion).

IMPORTANT — this DESCRIBES current technical structure; it does NOT predict
returns. A walk-forward study (15 large-caps, 5y incl. the 2022 bear, 4,680
samples) found NO forward-return edge: 20-day returns after a bullish posture
(+2.1%) were actually *lower* than after a bearish posture (+2.8%), and a fitted
model scored no better than the base rate out-of-sample. So this is a state
summary and a transparency tool, not a buy/sell recommendation.
"""
from __future__ import annotations

import numpy as np

# Honest, hard-won finding from backend/signal_study.py — surfaced in the UI so
# the posture is never mistaken for a forecast.
EVIDENCE = {
    "tested": True,
    "samples": 4680,
    "tickers": 15,
    "span": "5 years incl. the 2022 bear",
    "finding": (
        "Backtested point-in-time across 15 large-caps: this composite did NOT "
        "predict forward returns. 20-day returns after a bullish posture (+2.1%) "
        "were lower than after a bearish one (+2.8%), and a walk-forward model fit "
        "no better than chance. Read it as a description of current technical "
        "structure — not a prediction of where the price goes next."
    ),
}


def _clip(x: float) -> float:
    return float(max(-1.0, min(1.0, x)))


def score(ctx: dict) -> dict:
    """Return the composite signal dict (see module docstring)."""
    trend = ctx.get("trend") or {}
    mtf = ctx.get("multiTimeframe") or {}
    regime = mtf.get("regime") or {}
    latest = ctx.get("latest") or {}
    candles = ctx.get("candlesticks") or []
    vol = ctx.get("volume") or {}
    mino = ctx.get("minervini") or {}
    patterns = ctx.get("patterns") or []
    bt = ctx.get("backtest") or {}

    comps: list[dict] = []

    def add(name, value, weight, detail):
        comps.append({"name": name, "value": round(_clip(value), 3), "weight": float(weight), "detail": detail})

    # --- Trend of the displayed window (scaled by fit quality) ---
    d = trend.get("direction")
    if d:
        base = 1 if d == "uptrend" else -1 if d == "downtrend" else 0
        r2 = float(trend.get("r2", 0) or 0)
        add("Trend", base * (0.5 + 0.5 * min(1.0, max(0.0, r2))), 1.5, d)

    # --- Multi-timeframe alignment (1W…1Y) ---
    horizons = mtf.get("horizons") or []
    if horizons:
        ups = sum(1 for h in horizons if h["direction"] == "uptrend")
        downs = sum(1 for h in horizons if h["direction"] == "downtrend")
        add("Multi-timeframe", (ups - downs) / len(horizons), 2.0, mtf.get("alignment", ""))

    # --- Long-term regime: price vs 200-day + golden/death cross ---
    rv = 0.0
    if regime.get("above_sma200") is True:
        rv += 0.5
    elif regime.get("above_sma200") is False:
        rv -= 0.5
    if regime.get("cross") == "golden":
        rv += 0.5
    elif regime.get("cross") == "death":
        rv -= 0.5
    if regime.get("cross"):
        add("Regime (50/200 MA)", rv, 2.0, regime.get("cross_label", ""))

    # --- RSI: overbought caution / oversold opportunity, mild momentum tilt ---
    rsi = latest.get("rsi")
    if rsi is not None:
        if rsi >= 70:
            rval = -0.6
        elif rsi <= 30:
            rval = 0.6
        else:
            rval = (rsi - 50) / 40 * 0.4  # gentle tilt within the neutral band
        add("RSI", rval, 1.0, f"RSI {rsi:.0f}")

    # --- MACD vs signal ---
    macd, msig = latest.get("macd"), latest.get("macd_signal")
    if macd is not None and msig is not None:
        add("MACD", 0.6 if macd > msig else -0.6, 1.0, "above signal" if macd > msig else "below signal")

    # --- Minervini stage / score ---
    if mino.get("available"):
        stage = mino.get("stage", "")
        sc = int(mino.get("score", 0))
        mv = (sc - 4) / 4.0  # 8/8 → +1, 0/8 → -1
        if "Stage 4" in stage:
            mv = min(mv, -0.5)
        if "Stage 2" in stage:
            mv = max(mv, 0.5)
        add("Minervini", mv, 2.0, f"{stage} ({sc}/8)")

    # --- Recent candlesticks, weighted by their backtested edge ---
    edge_map = {}
    horizons_bt = bt.get("horizons") or [10]
    mid = str(horizons_bt[len(horizons_bt) // 2])
    for p in (bt.get("patterns") or []):
        st = (p.get("stats") or {}).get(mid)
        if st:
            edge_map[(p["name"], p["bias"])] = st.get("edge", 0)
    if candles:
        cval, cw = 0.0, 0.0
        for j, s in enumerate(candles[:3]):
            b = 1 if s["bias"] == "bullish" else -1 if s["bias"] == "bearish" else 0
            edge = edge_map.get((s["name"], s["bias"]), 0.0)
            recency = 1.0 - j * 0.3
            cval += b * (0.4 + max(0.0, edge) * 2.0) * recency
            cw += recency
        if cw:
            add("Candlesticks (edge-weighted)", cval / cw, 1.5, candles[0]["name"])

    # --- Volume confirmation ---
    if vol.get("available"):
        vv = 0.0
        for s in (vol.get("signals") or [])[:3]:
            if s["name"] == "Breakout on Volume":
                vv += 0.6
            elif s["name"] == "Breakdown on Volume":
                vv -= 0.6
            elif s["name"] == "Volume Spike":
                vv += 0.2 if s["bias"] == "bullish" else -0.2
        add("Volume", vv, 1.0, f"{vol.get('obv_trend', 'flat')} OBV")

    # --- Recent chart patterns ---
    if patterns:
        pv = sum(1 if p["bias"] == "bullish" else -1 if p["bias"] == "bearish" else 0 for p in patterns[:3])
        add("Chart patterns", pv / 3.0, 1.0, patterns[0]["name"])

    # --- Relative strength vs the market (SPY) ---
    rs = ctx.get("relativeStrength")
    if rs:
        add("Relative strength", rs["value"], 1.5,
            f"{rs['excess_pct']:+}% vs SPY ({rs['lookback']}d)")

    return _compose(comps)


def _compose(comps: list[dict]) -> dict:
    disclaimer = "Describes current technical structure — not a prediction or investment advice."
    if not comps:
        return {
            "score": 0.0, "posture": "Neutral", "verdict": "HOLD",
            "confidence": 0, "interval": {"low": 0.0, "high": 0.0},
            "components": [], "disclaimer": disclaimer, "evidence": EVIDENCE,
        }

    weights = np.array([c["weight"] for c in comps], dtype=float)
    vals = np.array([c["value"] for c in comps], dtype=float)
    wmean = float(np.sum(vals * weights) / np.sum(weights))
    wstd = float(np.sqrt(np.sum(weights * (vals - wmean) ** 2) / np.sum(weights)))

    score100 = round(wmean * 100, 1)
    margin = round(min(wstd * 100, 100.0), 1)
    interval = {
        "low": round(max(-100.0, score100 - margin), 1),
        "high": round(min(100.0, score100 + margin), 1),
    }
    confidence = int(round(max(0.0, min(100.0, (1.0 - wstd) * 100))))

    s = score100
    # Posture DESCRIBES structure; verdict kept (internal) only for alert rules.
    if s >= 50:
        posture, verdict = "Strongly Bullish", "BUY"
    elif s >= 20:
        posture, verdict = "Bullish", "BUY"
    elif s <= -50:
        posture, verdict = "Strongly Bearish", "SELL"
    elif s <= -20:
        posture, verdict = "Bearish", "SELL"
    else:
        posture, verdict = "Neutral", "HOLD"

    return {
        "score": score100,
        "posture": posture,
        "verdict": verdict,
        "confidence": confidence,
        "interval": interval,
        "components": sorted(comps, key=lambda c: abs(c["value"] * c["weight"]), reverse=True),
        "disclaimer": disclaimer,
        "evidence": EVIDENCE,
    }
