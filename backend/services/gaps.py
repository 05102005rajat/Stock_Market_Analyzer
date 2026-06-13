"""Opening-gap engine — tests the user's hypothesis on THIS stock's own data.

Hypothesis (user): "opens below last close -> good possibility it keeps going
down; opens above -> possibility it goes up" (gap CONTINUATION).

What the literature says (the opposite, on average, for big liquid names):
  * Lou, Polk & Skouras (2019, JFE) — the overnight/intraday "tug of war":
    overnight returns are systematically positive, intraday returns ~zero or
    negative; overnight moves tend to partially REVERSE during the day.
  * Berkman et al. — attention-driven buying at the open pushes gap-up opens
    too high; the day fades them.
  * Day-trader folklore agrees: "gaps tend to fill" — but LARGE news gaps
    behave differently from small drift gaps, so size buckets matter.

Because the truth is stock- and size-dependent, this engine computes the
displayed ticker's OWN history from the ~5y of daily OHLC the app already
fetches (open included): for every gap up/down >= 0.5%, did the rest of the
day CONTINUE the gap (close beyond the open) or FADE it (trade back to touch
yesterday's close)? Shown only on days the stock actually gapped.

Universe-level answer: run gap_universe_test.py (needs network) — it applies
the same definitions across the 80-name cache universe with per-date t-tests.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_GAP = 0.005   # 0.5% — below this, it's noise, card stays hidden
BIG_GAP = 0.02    # 2% — news-sized

EVIDENCE = {
    "literature": (
        "Documented average for large liquid stocks is the OPPOSITE of gap "
        "continuation: overnight moves partially reverse intraday (Lou/Polk/"
        "Skouras 2019 'tug of war'; attention-reversal literature). Large news "
        "gaps can behave differently from small drift gaps — hence the size "
        "buckets and per-stock measurement below."
    ),
}


def _bucket(g: float) -> str:
    a = abs(g)
    if a >= BIG_GAP:
        return "big"
    return "small"


def _own_gap_stats(o, h, l, c, pc) -> dict:
    """Per-stock gap history. Arrays exclude today's (possibly live) bar."""
    gap = o / pc - 1
    out = {}
    for direction in ("up", "down"):
        for bucket in ("small", "big", "all"):
            if direction == "up":
                m = gap >= MIN_GAP
                cont = c > o          # day ADDED to the gap
                fill = l <= pc        # traded back to touch yesterday's close
            else:
                m = gap <= -MIN_GAP
                cont = c < o
                fill = h >= pc
            if bucket == "small":
                m = m & (np.abs(gap) < BIG_GAP)
            elif bucket == "big":
                m = m & (np.abs(gap) >= BIG_GAP)
            m = m & ~np.isnan(gap) & ~np.isnan(c) & ~np.isnan(o)
            n = int(m.sum())
            if n < 10:
                continue
            o2c = (c[m] / o[m] - 1)
            out[f"{direction}_{bucket}"] = {
                "n": n,
                "continued_pct": round(100 * float(cont[m].mean()), 0),
                "faded_to_prior_close_pct": round(100 * float(fill[m].mean()), 0),
                "avg_open_to_close_pct": round(100 * float(np.nanmean(o2c)), 2),
            }
    return out


def analyze(df: pd.DataFrame) -> dict:
    """Today's gap state + this stock's own gap base rates. Needs daily OHLC
    with an 'open' column (the app's standard fetch includes it)."""
    need = {"open", "high", "low", "close"}
    if not need.issubset(df.columns) or len(df) < 121:
        return {"available": False, "reason": "need 120+ daily bars of history with open prices"}

    o = df["open"].astype(float).to_numpy()
    h = df["high"].astype(float).to_numpy()
    l = df["low"].astype(float).to_numpy()
    c = df["close"].astype(float).to_numpy()
    pc = np.concatenate([[np.nan], c[:-1]])

    # History excludes today's bar (it may still be trading).
    stats = _own_gap_stats(o[:-1], h[:-1], l[:-1], c[:-1], pc[:-1])
    if not stats:
        return {"available": False, "reason": "not enough gap history"}

    today_gap = float(o[-1] / pc[-1] - 1) if not np.isnan(pc[-1]) else np.nan
    if np.isnan(today_gap) or abs(today_gap) < MIN_GAP:
        return {
            "available": True,
            "gapped_today": False,
            "today_gap_pct": round(100 * (0 if np.isnan(today_gap) else today_gap), 2),
            "own": stats,
            "evidence": EVIDENCE,
        }

    direction = "up" if today_gap > 0 else "down"
    bucket = _bucket(today_gap)
    key = f"{direction}_{bucket}"
    rates = stats.get(key) or stats.get(f"{direction}_all")

    note = None
    if rates:
        verb = "added to the gap (closed beyond the open)" if direction == "up" else "kept falling (closed below the open)"
        note = (
            f"Opened {today_gap*100:+.1f}% vs yesterday's close — a {bucket} gap {direction}. "
            f"This stock's own {bucket} gaps {direction} (n={rates['n']}): {rates['continued_pct']:.0f}% "
            f"{verb}, while {rates['faded_to_prior_close_pct']:.0f}% traded back to touch yesterday's "
            f"close intraday; average open-to-close {rates['avg_open_to_close_pct']:+.2f}%. "
            "The documented market-wide average leans toward FADE, not continuation — "
            "the open is where overnight emotion is priced, not where the day ends."
        )

    return {
        "available": True,
        "gapped_today": True,
        "today_gap_pct": round(100 * today_gap, 2),
        "direction": direction,
        "bucket": bucket,
        "today_rates": rates,
        "own": stats,
        "note": note,
        "evidence": EVIDENCE,
        "caveat": (
            "Descriptive base rates from this stock's own history; intraday paths vary and "
            "averages are not destiny. Run gap_universe_test.py for the 80-name answer."
        ),
    }
