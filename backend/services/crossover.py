"""EMA-ribbon + MACD crossover signal — the user-specified trend system.

This implements the exact rules requested:

  EMA ribbon (closing basis): 55, 89, 204
    - macro cross : EMA89 vs EMA204
    - fast  cross : EMA55 vs EMA89
    - a BULLISH stack is 55 > 89 > 204 (all aligned up); bearish is the mirror.

  MACD (13, 34, 9)
    - the requested 13/34 fast/slow (the "Fibonacci MACD"); the signal length is
      9, NOT 81 — an 81-period signal lags so far it is unusable, so it was
      treated as a transcription slip and set to the standard 9. NOTE: a
      ZERO-LINE cross of the MACD line depends ONLY on the 13/34 EMAs, so the
      signal length does not affect the zero-line rule at all.

  COMBINED BUY when all three agree up:
    bullish EMA stack  AND  MACD line above zero  AND  price above EMA55.
  COMBINED SELL is the exact mirror. Anything else is NEUTRAL.

Convention note: this uses the STANDARD reading — faster EMA crossing ABOVE the
slower one is BULLISH (a "golden" cross). The original verbal spec said "cut
down then buy", which is the opposite (a contrarian read); set CONTRARIAN=True
below to invert every buy/sell if that was actually intended.

────────────────────────────────────────────────────────────────────────────
HONESTY (the whole point of this app): moving-average + MACD crossover systems
are TREND-FOLLOWING. The rigorous evidence is not kind to them as buy/sell
edges — after correcting for data-snooping (Sullivan-Timmermann-White 1999) and
trading costs, the backtested edge largely vanishes, win rates cluster near a
coin flip, and results decayed sharply after ~2000 once the rules were public
(Park-Irwin 2007). They confirm trends LATE and structurally CANNOT call a
reversal. Custom/optimised parameters (like a hand-picked Fibonacci set) are
exactly the ones least likely to survive out-of-sample. So this is NOT a
recommendation engine: the signal is logged to the Signal Ledger and scored
forward vs SPY at 5/21/63 days, so you can read its REAL accuracy on YOUR
tickers instead of trusting the label. Trust the ledger, not the arrow.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import ema, macd

# Flip to True to invert buy/sell (the "cut down = buy" contrarian reading).
CONTRARIAN = False

# Ribbon + MACD parameters (exactly as requested, signal fixed 81 -> 9).
EMA_FAST, EMA_MID, EMA_SLOW = 55, 89, 204
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 13, 34, 9

# Surfaced verbatim in the UI so the arrow is never mistaken for a forecast.
EVIDENCE = {
    "tested_literature": True,
    "finding": (
        "EMA/MACD crossovers are trend-following, not predictive. After "
        "correcting for data-snooping (Sullivan-Timmermann-White 1999) and "
        "trading costs, the historical edge largely disappears; MACD win rates "
        "sit near a coin flip and weakened after ~2000 once the rules were "
        "public (Park-Irwin 2007). This system confirms trends late and cannot "
        "call reversals. It is logged to the Signal Ledger and scored forward "
        "vs SPY so you can judge its REAL out-of-sample accuracy — trust the "
        "ledger, not the arrow."
    ),
    "params_note": (
        f"MACD {MACD_FAST}/{MACD_SLOW}/{MACD_SIGNAL} (signal set to 9, not 81 — "
        "an 81-period signal is unusable). Zero-line crosses depend only on the "
        f"{MACD_FAST}/{MACD_SLOW} EMAs, so the signal length is irrelevant there."
    ),
}


def _last(s: pd.Series):
    s = s.dropna()
    return float(s.iloc[-1]) if not s.empty else None


def _recent_cross(a: pd.Series, b: pd.Series, lookback: int = 90) -> dict | None:
    """Most recent crossing of series a through series b within `lookback` bars.

    Returns {direction: 'up'|'down', bars_ago, date} or None if no valid cross.
    'up' = a crossed from below b to above b (bullish for a-faster-than-b).
    """
    df = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    if len(df) < 2:
        return None
    diff = (df["a"] - df["b"]).to_numpy()
    sign = np.sign(diff)
    n = len(sign)
    start = max(1, n - lookback)
    for i in range(n - 1, start - 1, -1):
        if sign[i] != 0 and sign[i - 1] != 0 and sign[i] != sign[i - 1]:
            return {
                "direction": "up" if sign[i] > 0 else "down",
                "bars_ago": int(n - 1 - i),
                "date": df.index[i].strftime("%Y-%m-%d"),
            }
    return None


def analyze(df: pd.DataFrame) -> dict:
    """Compute the ribbon + MACD state and the combined buy/sell signal.

    `df` should be a long daily history (>= ~210 bars for the EMA204 to warm up).
    """
    close = df["close"].astype(float)
    n = len(close)
    if n < EMA_SLOW + 5:
        return {
            "available": False,
            "reason": f"Need >= {EMA_SLOW + 5} daily bars for the EMA{EMA_SLOW}; "
                      f"have {n}.",
            "evidence": EVIDENCE,
        }

    e_fast = ema(close, EMA_FAST)
    e_mid = ema(close, EMA_MID)
    e_slow = ema(close, EMA_SLOW)
    m = macd(close, fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
    macd_line, sig_line, hist = m["macd"], m["signal"], m["hist"]

    price = _last(close)
    v_fast, v_mid, v_slow = _last(e_fast), _last(e_mid), _last(e_slow)
    v_macd, v_sig = _last(macd_line), _last(sig_line)
    if None in (price, v_fast, v_mid, v_slow, v_macd):
        return {"available": False, "reason": "indicator warm-up incomplete",
                "evidence": EVIDENCE}

    # --- current binary conditions -------------------------------------------
    bull_stack = v_fast > v_mid > v_slow
    bear_stack = v_fast < v_mid < v_slow
    macd_above_zero = v_macd > 0
    price_above_fast = price > v_fast
    macd_above_signal = (v_sig is not None) and (v_macd > v_sig)

    # --- combined signal (their rule) ----------------------------------------
    raw_buy = bull_stack and macd_above_zero and price_above_fast
    raw_sell = bear_stack and (not macd_above_zero) and (not price_above_fast)
    if CONTRARIAN:
        raw_buy, raw_sell = raw_sell, raw_buy

    if raw_buy:
        state, direction = "buy", "up"
        label = "BUY signal — EMA stack bullish, MACD > 0, price > EMA55 (all aligned)"
    elif raw_sell:
        state, direction = "sell", "down"
        label = "SELL signal — EMA stack bearish, MACD < 0, price < EMA55 (all aligned)"
    else:
        state, direction = "neutral", None
        label = "No clean signal — the three conditions do not all agree yet"

    # --- recent crossover events (with dates) --------------------------------
    macd_zero = pd.Series(0.0, index=macd_line.index)
    events = {
        "ema89_x_ema204": _recent_cross(e_mid, e_slow),     # macro cross
        "ema55_x_ema89": _recent_cross(e_fast, e_mid),      # fast cross
        "macd_zero_line": _recent_cross(macd_line, macd_zero),
        "macd_x_signal": _recent_cross(macd_line, sig_line),
    }

    # how many of the 3 buy-conditions are met (for a progress read)
    conds = [bull_stack, macd_above_zero, price_above_fast]
    met = sum(1 for c in conds if c)

    return {
        "available": True,
        "state": state,            # buy | sell | neutral
        "direction": direction,    # up | down | None  (for the ledger)
        "label": label,
        "conditions_met": met,     # 0..3 toward a BUY
        "components": [
            {"name": "EMA stack 55>89>204", "ok": bool(bull_stack),
             "detail": "bullish (aligned up)" if bull_stack
                       else "bearish (aligned down)" if bear_stack
                       else "mixed / not aligned"},
            {"name": "MACD line vs 0", "ok": bool(macd_above_zero),
             "detail": f"{v_macd:+.3f} ({'above' if macd_above_zero else 'below'} zero)"},
            {"name": "Price vs EMA55", "ok": bool(price_above_fast),
             "detail": f"{price:.2f} vs {v_fast:.2f} "
                       f"({'above' if price_above_fast else 'below'})"},
            {"name": "MACD vs signal", "ok": bool(macd_above_signal),
             "detail": f"{'above' if macd_above_signal else 'below'} signal line"},
        ],
        "events": events,
        "values": {
            "price": round(price, 2),
            "ema55": round(v_fast, 2),
            "ema89": round(v_mid, 2),
            "ema204": round(v_slow, 2),
            "macd": round(v_macd, 4),
            "macd_signal": round(v_sig, 4) if v_sig is not None else None,
            "macd_hist": round(_last(hist), 4) if _last(hist) is not None else None,
        },
        "params": {
            "ema": [EMA_FAST, EMA_MID, EMA_SLOW],
            "macd": [MACD_FAST, MACD_SLOW, MACD_SIGNAL],
            "contrarian": CONTRARIAN,
        },
        "evidence": EVIDENCE,
    }
