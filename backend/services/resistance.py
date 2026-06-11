"""Key-resistance detection + HONEST breakout base rates.

Answers the user-level question directly: "this is the resistance — if price
crosses this line, how often did that historically continue toward the all-time
high vs fall back below the line?"

The level
---------
Resistance R = the highest HIGH of the prior 50 trading days (point-in-time,
excludes today). We also count how many distinct swing-high pivots (local max
over +/-3 bars) REJECTED within 1.5% of R inside the window — more touches =
a more meaningful level.

The evidence (measured, not vibes)
----------------------------------
Base rates measured on this project's cached universe: 80 large/mid caps,
10 years of daily bars (2016-05 .. 2026-05), all point-in-time, n=7,033 fresh
closes above the 50-day high:

  After a FRESH close above R:
    * 72% traded back below R at some point within 21 days (retests are NORMAL)
    * but only 42% failed decisively (closed >3% below R within 21d)
    * 49% held above R on >=80% of the next 21 days
      - with a volume surge (>1.5x avg): held 58%, decisive fail 38%
  Reaching the prior ALL-TIME HIGH within 63 days depends almost entirely on
  how far away it is at the breakout:
    * <2% below ATH  -> 88% reached it          (n=349)
    * 2-10% below    -> 62%                     (n=992)
    * 10-25% below   -> 33%                     (n=719)
    * >25% below     ->  8%                     (n=1,063)
    * uptrend + volume surge + within 10% of ATH -> 92% (n=1,094)
    * already in blue sky (no overhead) -> 95% made ANOTHER new high in 63d
  APPROACHING R (first day within 2% below it), n=12,181 episodes:
    * 81% broke above within 21 days; only 33% fell >5% first/instead.
      "It will bounce back at resistance" is the MINORITY outcome.

CRITICAL caveats baked into the payload:
  * NO ALPHA: per-date tests vs other stocks on the same dates show |t| < 2 for
    every breakout variant (incl. volume-confirmed VCP). These are base rates of
    PATH BEHAVIOUR, not evidence the stock will beat the market.
  * SURVIVORSHIP BIAS: the 80-name universe is today's large caps (winners), so
    ATH-reach rates are optimistic for the average stock.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LOOKBACK = 50      # resistance = prior 50d high
PIVOT = 3          # swing high = local max over +/-3 bars
TOL = 0.015        # a pivot within 1.5% of the level counts as a "touch"
NEAR = 0.02        # "approaching" = within 2% below the level

EVIDENCE = {
    "tested": True,
    "universe": "80 large/mid caps, 10y daily (2016-2026), point-in-time",
    "n_breakouts": 7033,
    "n_approaches": 12181,
    "alpha": (
        "No edge vs other stocks on the same dates (per-date diff t < 2 for every "
        "variant, including volume-confirmed). These are PATH base rates, not a "
        "buy signal."
    ),
    "survivorship": (
        "Universe is today's surviving large caps, so reach-the-high rates are "
        "optimistic for the average stock."
    ),
}

# Reached prior ATH within 63d, bucketed by distance below ATH at the breakout.
ATH_BY_DISTANCE = [
    # (lo, hi, label, p_reach_ath_63d, n)
    (-9.0, 0.00, "blue sky (above old high)", 0.95, 3896),  # p = makes ANOTHER new high
    (0.00, 0.02, "<2% below the old high", 0.88, 349),
    (0.02, 0.10, "2-10% below", 0.62, 992),
    (0.10, 0.25, "10-25% below", 0.33, 719),
    (0.25, 9.00, ">25% below", 0.08, 1063),
]

BREAKOUT_RATES = {
    "retest_21d": 0.72,          # traded back below the level at some point
    "decisive_fail_21d": 0.42,   # closed >3% below the level
    "held_21d": 0.49,            # above the level >=80% of next 21 days
    "held_21d_volume": 0.58,
    "decisive_fail_21d_volume": 0.38,
    "best_combo_ath_63d": 0.92,  # uptrend + volume surge + within 10% of ATH
}

APPROACH_RATES = {
    "broke_within_21d": 0.81,
    "rejected_5pct_21d": 0.33,
}
APPROACH_RATES_N = EVIDENCE["n_approaches"]


def _swing_high_touches(high: np.ndarray, level: float) -> int:
    """Count confirmed swing-high pivots within TOL of `level`."""
    n = len(high)
    touches = 0
    for i in range(PIVOT, n - PIVOT):
        w = high[i - PIVOT : i + PIVOT + 1]
        if high[i] == w.max() and np.sum(w == w.max()) == 1:
            if abs(high[i] - level) / level <= TOL:
                touches += 1
    return touches


def _ath_bucket(dist: float) -> dict:
    for lo, hi, label, p, n in ATH_BY_DISTANCE:
        if lo <= dist < hi:
            return {"label": label, "p_reach_ath_63d": p, "n": n}
    return {"label": ">25% below", "p_reach_ath_63d": 0.08, "n": 1063}


def analyze(df: pd.DataFrame) -> dict:
    """Return the key resistance level, the current state vs it, and the
    historically measured odds for that state. Needs daily OHLCV with columns
    high/low/close/volume (volume optional)."""
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    if len(close) < LOOKBACK + PIVOT + 5:
        return {"available": False, "reason": "not enough history"}

    c = float(close.iloc[-1])
    c_prev = float(close.iloc[-2])

    # Point-in-time level: prior 50d high, excluding today.
    win_high = high.iloc[-(LOOKBACK + 1) : -1]
    level = float(win_high.max())
    level_prev = float(high.iloc[-(LOOKBACK + 2) : -2].max())
    touches = _swing_high_touches(win_high.to_numpy(), level)

    # All-time high context (point-in-time: prior to today).
    ath = float(close.iloc[:-1].max())
    dist_ath = ath / c - 1  # negative => today is already above the old high

    # Volume confirmation (if volume present).
    vol_surge = None
    if "volume" in df.columns and df["volume"].notna().sum() > LOOKBACK:
        v = df["volume"].astype(float)
        avg = float(v.iloc[-(LOOKBACK + 1) : -1].mean())
        if avg > 0:
            vol_surge = bool(float(v.iloc[-1]) > 1.5 * avg)

    # Long-term trend filter.
    uptrend = None
    if len(close) >= 200:
        uptrend = bool(c > float(close.rolling(200).mean().iloc[-1]))

    # ---- State machine ----
    above = c > level
    was_above = c_prev > level_prev
    pct_to_level = (level / c - 1) * 100

    if above and not was_above:
        state = "fresh_breakout"
    elif above:
        # how long has it held?
        recent = close.iloc[-21:]
        lv = high.shift(1).rolling(LOOKBACK).max().iloc[-21:]
        frac = float((recent > lv).mean())
        state = "holding_above" if frac >= 0.6 else "choppy_above"
    elif pct_to_level <= NEAR * 100:
        state = "approaching"
    else:
        state = "below"

    bucket = _ath_bucket(dist_ath)
    best_combo = bool(uptrend) and bool(vol_surge) and (dist_ath < 0.10)

    # ---- Honest narrative per state ----
    lvl_s = f"{level:,.2f}"
    odds: list[str] = []
    if state == "approaching":
        headline = f"Pressing into resistance at {lvl_s} ({pct_to_level:+.1f}% away, {touches} prior rejection{'s' if touches != 1 else ''})."
        odds.append(
            f"Historically (n={APPROACH_RATES_N}), {APPROACH_RATES['broke_within_21d']:.0%} of such approaches "
            f"broke above within a month; only {APPROACH_RATES['rejected_5pct_21d']:.0%} fell more than 5% first. "
            "A hard bounce-back is the minority outcome."
        )
        odds.append(
            f"IF it closes above {lvl_s}: {bucket['label']} breakouts reached the old all-time high within "
            f"3 months {bucket['p_reach_ath_63d']:.0%} of the time (n={bucket['n']})."
        )
    elif state == "fresh_breakout":
        headline = f"Fresh close above the {lvl_s} resistance ({touches} prior rejection{'s' if touches != 1 else ''} at this level)."
        if dist_ath <= 0:
            odds.append(
                f"Blue sky — no overhead supply left: {bucket['p_reach_ath_63d']:.0%} of such breakouts made "
                f"ANOTHER new high within 3 months (n={bucket['n']})."
            )
        else:
            odds.append(
                f"From here, {bucket['label']}: {bucket['p_reach_ath_63d']:.0%} historically went on to the prior "
                f"all-time high within 3 months (n={bucket['n']})."
            )
        if best_combo:
            odds.append(
                f"This one has the strongest measured setup — uptrend + volume surge + within 10% of the high: "
                f"{BREAKOUT_RATES['best_combo_ath_63d']:.0%} of those reached the old high within 3 months (n=1,094)."
            )
        hold = BREAKOUT_RATES["held_21d_volume"] if vol_surge else BREAKOUT_RATES["held_21d"]
        fail = BREAKOUT_RATES["decisive_fail_21d_volume"] if vol_surge else BREAKOUT_RATES["decisive_fail_21d"]
        odds.append(
            f"Expect a retest: {BREAKOUT_RATES['retest_21d']:.0%} dip back below the line within a month — that "
            f"alone is NOT failure. Decisive failure (closing >3% below) happened {fail:.0%} of the time"
            f"{' (volume-confirmed)' if vol_surge else ''}; {hold:.0%} held the level most of the month."
        )
    elif state in ("holding_above", "choppy_above"):
        headline = (
            f"Trading above the former {lvl_s} resistance"
            + (" and holding it well." if state == "holding_above" else ", but choppily — the line is being retested.")
        )
        if dist_ath <= 0:
            odds.append(
                f"Blue sky: {bucket['p_reach_ath_63d']:.0%} of comparable breakouts made another new high "
                f"within 3 months (n={bucket['n']})."
            )
        else:
            odds.append(
                f"{bucket['label']}: {bucket['p_reach_ath_63d']:.0%} of comparable breakouts reached the prior "
                f"all-time high within 3 months (n={bucket['n']})."
            )
    else:
        headline = f"Overhead resistance at {lvl_s} ({pct_to_level:+.1f}% above), {touches} prior rejection{'s' if touches != 1 else ''}."
        odds.append(
            "Too far below the level for breakout odds to apply yet. Watch for an approach within 2%."
        )

    return {
        "available": True,
        "level": round(level, 2),
        "touches": int(touches),
        "pct_to_level": round(pct_to_level, 2),
        "state": state,
        "ath": round(ath, 2),
        "dist_ath_pct": round(dist_ath * 100, 2),
        "ath_bucket": bucket,
        "volume_surge": vol_surge,
        "uptrend": uptrend,
        "best_combo": best_combo,
        "headline": headline,
        "odds": odds,
        "evidence": EVIDENCE,
        "caveat": (
            "Path base rates from 80 surviving large caps — descriptive, survivorship-biased, "
            "and with NO measured edge vs other stocks. Not a prediction or a buy/sell signal."
        ),
    }
