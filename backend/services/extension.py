"""Extension gauge — how stretched price is above/below its 50d MA, and what
that stretch has HONESTLY meant.

User hypothesis: "rises too fast above its average -> falls until they meet ->
then goes up; the stretch is where I should get out."

Measured (80 large caps, 10y, point-in-time, non-overlapping episodes):
  ext >= 15% above the 50d MA (n=1,092):
    * forward 63d return +11.0% vs +6.0% unconditional (21d t=2.59) —
      extension was a MOMENTUM signal, not a top signal. Exiting here
      historically GAVE UP excess return.
    * BUT avg max drawdown inside that quarter was -20.2% (median -17.4%) —
      extension predicts TURBULENCE, not direction.
    * 79% touched the 50d MA within 63d (median day 30) — the user's
      convergence intuition is right...
    * ...but median only 29% of the gap closed by PRICE FALLING; ~70% closed
      by the MA RISING underneath (sideways time-correction, not a crash).
    * after the touch: next 21d +4.31%, 59% win — the touch WAS a decent
      add/re-entry spot ("then it goes up" confirmed).
  ext >= 25% blow-off (n=384): same shape, hotter — fwd 63d +12.9%,
  avg max DD -25.0%, 80% touch, ~30% price-fall share, post-touch +5.7%.

Translation built into the card: the stretch is a SIZE-AND-SEATBELT gauge,
not an exit signal. If a -17% interim dip would shake you out, trim for
sleep; the data says don't sell the strength itself.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MA_LEN = 50
EXTENDED = 0.15
BLOWOFF = 0.25
NEAR_MA = 0.02

EVIDENCE = {
    "tested": True,
    "universe": "80 large/mid caps, 10y daily, point-in-time, non-overlapping episodes",
    "n_extended": 1092,
    "n_blowoff": 384,
    "fwd63_extended_pct": 11.0,
    "fwd63_uncond_pct": 6.0,
    "max_dd_median_pct": -17.4,
    "touch_rate_pct": 79,
    "price_fall_share_median_pct": 29,
    "post_touch_21d_pct": 4.31,
    "post_touch_win_pct": 59,
}


def analyze(df: pd.DataFrame) -> dict:
    close = df["close"].astype(float)
    if len(close) < MA_LEN + 70:
        return {"available": False, "reason": "not enough history"}

    ma = close.rolling(MA_LEN).mean()
    ext = close / ma - 1
    e_now = float(ext.iloc[-1])
    if np.isnan(e_now):
        return {"available": False, "reason": "not enough history"}

    # percentile of current stretch vs this stock's own last ~2y
    hist = ext.iloc[-504:].dropna()
    pctile = float((hist <= e_now).mean() * 100) if len(hist) > 100 else None

    # was there a recent hot run that has now come back to the MA? (re-entry spot)
    recent_max_ext = float(ext.iloc[-63:].max())
    near_ma = abs(e_now) <= NEAR_MA
    touch_after_run = near_ma and recent_max_ext >= EXTENDED

    if e_now >= BLOWOFF:
        state = "blowoff"
    elif e_now >= EXTENDED:
        state = "extended"
    elif touch_after_run:
        state = "ma_touch_after_run"
    elif e_now <= -EXTENDED:
        state = "stretched_below"
    else:
        state = "normal"

    notes: list[str] = []
    if state in ("extended", "blowoff"):
        deg = "blow-off territory (25%+)" if state == "blowoff" else "extended (15%+)"
        notes.append(
            f"Price is {e_now*100:+.1f}% above its 50d MA — {deg}"
            + (f", the {pctile:.0f}th percentile of its own last 2 years" if pctile is not None else "")
            + "."
        )
        notes.append(
            "Honest history of this setup (n=1,092): it was a MOMENTUM signal, not a top — next-quarter "
            "return averaged +11.0% vs +6.0% baseline. Selling the stretch itself cost money on average."
        )
        notes.append(
            "The catch: the median episode also served a -17% drawdown somewhere inside that quarter, and "
            "79% of these touched the 50d MA within ~6 weeks — but ~70% of that convergence happened by the "
            "MA RISING under a sideways price, not by a crash. If a -17% dip would make you sell at the "
            "bottom, trim to a size you can sit through — that's a sleep decision, not a prediction."
        )
    elif state == "ma_touch_after_run":
        notes.append(
            f"Price has come back to its 50d MA ({e_now*100:+.1f}%) after running {recent_max_ext*100:+.0f}% "
            "above it within the last quarter — the user-described 'averages meet' moment."
        )
        notes.append(
            "Measured across ~860 such touches: next 21 days averaged +4.3% with a 59% win rate — "
            "historically one of the better add/re-entry spots, though hardly a guarantee."
        )
    elif state == "stretched_below":
        notes.append(
            f"Price is {e_now*100:+.1f}% BELOW its 50d MA — stretched the other way. Symmetric caution: "
            "deep stretches mark turbulence and capitulation zones, not reliable bottoms by themselves; "
            "pair with the dip signal and sector attribution before acting."
        )

    return {
        "available": True,
        "ext_pct": round(e_now * 100, 1),
        "ma": round(float(ma.iloc[-1]), 2),
        "percentile_2y": round(pctile, 0) if pctile is not None else None,
        "recent_max_ext_pct": round(recent_max_ext * 100, 1),
        "state": state,
        "notes": notes,
        "evidence": EVIDENCE,
        "caveat": (
            "Risk gauge, not a signal: extension predicted turbulence and slower per-unit-risk gains, "
            "not direction. Base rates from surviving large caps."
        ),
    }
