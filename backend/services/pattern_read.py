"""Pattern read — turns the name-dump into ONE directional verdict.

The complaint this solves: "you gave me the names ('Bullish Harami',
'Three Black Crows') but I don't know what they MEAN for this stock."

Method (all measured on THIS stock's own history, direction-aware):
  1. Take every candlestick signal from the last RECENT_BARS sessions.
  2. Look up that pattern's measured 10-bar stats on this stock from the
     backtest engine (win rate IN the pattern's direction vs baseline).
     Patterns with n < MIN_N are dropped as noise.
  3. Convert each to P(up in 10 bars) and combine with weights =
     sqrt(sample size) x recency decay.
  4. Compare the net P(up) to the unconditional baseline -> a tilt in
     percentage points, with a CONFLICT flag when bullish and bearish
     signals both carry real weight (which is itself information: no
     clean tape story).
  5. REGIME CHECK (the user's "AI-era vs 3 years ago" concern): the same
     stats are recomputed on only the last ~2 years. If a pattern's edge
     flips sign or moves a lot between windows, it is flagged as
     regime-unstable and the verdict says so. Non-stationarity is real:
     a 10-year average can describe a market that no longer exists.

Chart patterns (Double Top, H&S...) have no per-stock measured stats, so
they are reported as UNQUANTIFIED context — recent ones noted, stale ones
(ended >21 bars ago) explicitly marked stale — and excluded from the math.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services import backtest, candlesticks

RECENT_BARS = 10
MIN_N = 10
HORIZON = "10"
RECENT_WINDOW = 504        # ~2 trading years
DECAY = 0.9
STALE_BARS = 21


def _p_up(bias: str, win: float, base_up: float) -> float:
    if bias == "bullish":
        return win
    if bias == "bearish":
        return 1.0 - win
    return win  # neutral patterns measure up-rate directly


def _collect(df, signals, stats, base_up):
    """Recent signals joined with their measured stats."""
    time_to_i = {int(ts.timestamp()): i for i, ts in enumerate(df.index)}
    n = len(df)
    by_name = {(r["name"], r["bias"]): r for r in stats.get("patterns", [])}
    rows = []
    for s in signals:
        i = time_to_i.get(s["time"])
        if i is None or n - 1 - i > RECENT_BARS:
            continue
        rec = by_name.get((s["name"], s["bias"]))
        st = (rec or {}).get("stats", {}).get(HORIZON)
        if not st or st["samples"] < MIN_N:
            continue
        bars_ago = n - 1 - i
        rows.append({
            "name": s["name"], "bias": s["bias"], "bars_ago": bars_ago,
            "n": st["samples"], "win": st["win_rate"], "edge": st["edge"],
            "avg": st["avg_return"],
            "p_up": _p_up(s["bias"], st["win_rate"], base_up),
            "w": float(np.sqrt(min(st["samples"], 40)) * (DECAY ** bars_ago)),
        })
    return rows


def analyze(df: pd.DataFrame, chart_patterns: list | None = None,
            signals: list | None = None, stats_full: dict | None = None,
            stats_recent: dict | None = None) -> dict:
    if len(df) < 150:
        return {"available": False, "reason": "not enough history"}

    signals = signals if signals is not None else candlesticks.detect(df, lookback=RECENT_BARS + 5)
    stats_full = stats_full or backtest.run(df)
    if not stats_full.get("available"):
        return {"available": False, "reason": "no backtest stats"}
    base_up = stats_full["baseline"][HORIZON]["up_rate"]

    rows = _collect(df, signals, stats_full, base_up)
    if not rows:
        return {
            "available": True, "n_signals": 0,
            "verdict": "No measured pattern signals in the last two weeks — the candles are quiet. "
                       "That is a finding, not a failure: most days carry no tape signal.",
            "tilt_pp": 0.0, "conflict": False, "contributors": [],
            "chart_context": _chart_context(df, chart_patterns),
        }

    W = sum(r["w"] for r in rows)
    p_up = sum(r["p_up"] * r["w"] for r in rows) / W
    tilt = (p_up - base_up) * 100
    bull_w = sum(r["w"] for r in rows if r["p_up"] >= base_up) / W
    conflict = 0.35 <= bull_w <= 0.65

    # ---- regime check: same read on the last ~2y only ----
    regime = None
    if len(df) > RECENT_WINDOW + 60:
        stats_recent = stats_recent or backtest.run(df.iloc[-RECENT_WINDOW:])
        if stats_recent.get("available"):
            base_r = stats_recent["baseline"][HORIZON]["up_rate"]
            rows_r = _collect(df, signals, stats_recent, base_r)
            flips = []
            for r in rows:
                m = next((x for x in rows_r if x["name"] == r["name"]), None)
                if m and (np.sign(m["edge"]) != np.sign(r["edge"]) or abs(m["edge"] - r["edge"]) > 0.15):
                    flips.append(r["name"])
            p_up_r = (sum(r["p_up"] * r["w"] for r in rows_r) / sum(r["w"] for r in rows_r)) if rows_r else None
            regime = {
                "recent_window_years": 2,
                "p_up_recent": round(p_up_r, 3) if p_up_r is not None else None,
                "tilt_recent_pp": round((p_up_r - base_r) * 100, 1) if p_up_r is not None else None,
                "unstable_patterns": flips,
                "stable": not flips,
            }

    rows.sort(key=lambda r: -(abs(r["p_up"] - base_up) * r["w"]))
    top = rows[:3]

    direction = "BULLISH" if tilt > 2 else "BEARISH" if tilt < -2 else "FLAT"
    pieces = []
    pieces.append(
        f"Net tape read from the last {RECENT_BARS} sessions ({len(rows)} measured signals): "
        f"{p_up*100:.0f}% chance of being higher in 10 bars vs {base_up*100:.0f}% baseline — "
        f"a {abs(tilt):.0f}pp {direction.lower()} tilt." if direction != "FLAT" else
        f"Net tape read from the last {RECENT_BARS} sessions ({len(rows)} measured signals): "
        f"{p_up*100:.0f}% vs the {base_up*100:.0f}% baseline — within noise of flat. The honest "
        "summary of these candles is: nothing actionable."
    )
    if conflict:
        pieces.append(
            "Bullish and bearish signals are pulling against each other with comparable weight — the "
            "conflict itself is the message: no clean story, expect chop rather than trend."
        )
    if top:
        lead = ", ".join(
            f"{r['name']} ({r['bias']}, {r['bars_ago']}d ago, {r['win']*100:.0f}% on n={r['n']})"
            for r in top
        )
        pieces.append(f"Heaviest contributors on THIS stock's own history: {lead}.")
    if regime:
        if regime["stable"] and regime["tilt_recent_pp"] is not None:
            pieces.append(
                f"Regime check: restricted to the last 2 years only, the same signals read "
                f"{regime['tilt_recent_pp']:+.0f}pp — consistent with the full-history read."
            )
        elif regime["unstable_patterns"]:
            pieces.append(
                "Regime warning: " + ", ".join(regime["unstable_patterns"]) +
                " behaved differently in the last 2 years than over the full decade — the AI-era tape "
                "is not the 2016-2021 tape. Trust the 2-year number more for these."
            )

    return {
        "available": True,
        "n_signals": len(rows),
        "p_up_10bar": round(p_up, 3),
        "baseline_up": round(base_up, 3),
        "tilt_pp": round(tilt, 1),
        "direction": direction,
        "conflict": conflict,
        "contributors": top,
        "regime": regime,
        "verdict": " ".join(pieces),
        "chart_context": _chart_context(df, chart_patterns),
        "caveat": (
            "In-sample base rates on one stock; small samples are noisy and edges decay. "
            "A tilt under ~5pp is indistinguishable from nothing."
        ),
    }


def _chart_context(df, chart_patterns):
    if not chart_patterns:
        return []
    out = []
    last = df.index[-1]
    for p in chart_patterns[:4]:
        end = p.get("end") or p.get("end_date") or p.get("to")
        try:
            age = (last - pd.Timestamp(end)).days if end else None
        except Exception:
            age = None
        stale = age is None or age > STALE_BARS * 1.5
        out.append({
            "name": p.get("name"), "bias": p.get("bias"),
            "age_days": age, "stale": bool(stale),
            "note": (
                f"{p.get('name')} ({p.get('bias')}) — "
                + ("STALE, ended weeks ago; background context only."
                   if stale else "recent; unquantified — no per-stock stats exist for chart patterns, "
                                 "so it is context, not part of the probability above.")
            ),
        })
    return out
