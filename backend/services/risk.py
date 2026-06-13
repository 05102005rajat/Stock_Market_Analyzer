"""Position sizing & portfolio risk — the tools that actually move real P&L.

Four honest, non-predictive calculators:
  1. ATR stop + size: given account, risk%, entry, and recent ATR, how many
     shares keep the loss to risk% if stopped at entry - k*ATR.
  2. Portfolio heat: sum of open risk (per position: shares * (entry - stop))
     as % of account — the total you'd lose if every stop hit at once.
  3. Fractional Kelly: from a win rate and payoff ratio, the Kelly fraction,
     then the recommended QUARTER/HALF-Kelly (full Kelly draws down ~50% a
     third of the time; practitioners use a fraction).
  4. Concentration check: single-name and theme caps with look-through.

All descriptive risk math — no prediction. Defaults reflect the project's
stated rules for a small account (single name <=10%, AI/semi theme <=~40%).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_RISK_PCT = 1.0
DEFAULT_ATR_MULT = 2.0
SINGLE_NAME_CAP = 0.10
THEME_CAP = 0.40


def atr(df: pd.DataFrame, period: int = 14) -> float | None:
    """Average True Range over `period` from daily OHLC."""
    if not {"high", "low", "close"}.issubset(df.columns) or len(df) < period + 1:
        return None
    h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return float(tr.rolling(period).mean().iloc[-1])


def size_position(account: float, entry: float, df: pd.DataFrame,
                  risk_pct: float = DEFAULT_RISK_PCT,
                  atr_mult: float = DEFAULT_ATR_MULT) -> dict:
    """ATR-based stop and share count for a fixed-fractional risk budget."""
    a = atr(df)
    if a is None or entry <= 0:
        return {"available": False, "reason": "need OHLC history for ATR"}
    if a < entry * 1e-4:  # essentially flat — a stop would be at the entry
        return {"available": False, "reason": "price too flat to set a meaningful ATR stop"}
    stop = entry - atr_mult * a
    risk_per_share = entry - stop
    dollar_risk = account * (risk_pct / 100)
    shares = dollar_risk / risk_per_share if risk_per_share > 0 else 0
    position_value = shares * entry
    return {
        "available": True,
        "atr": round(a, 2),
        "stop_price": round(stop, 2),
        "stop_pct": round(-atr_mult * a / entry * 100, 1),
        "risk_per_share": round(risk_per_share, 2),
        "dollar_risk": round(dollar_risk, 2),
        "shares": round(shares, 3),
        "position_value": round(position_value, 2),
        "position_pct_of_account": round(position_value / account * 100, 1) if account else None,
        "note": (
            f"Risking {risk_pct}% (${dollar_risk:.0f}) with a {atr_mult}x ATR stop at "
            f"${stop:.2f} ({-atr_mult*a/entry*100:.1f}%) means ~{shares:.2f} shares "
            f"(${position_value:.0f}). If that position is >10% of the account, the stop is "
            "wide enough that fixed-fractional sizing wants a smaller bite — trust the math, "
            "not the conviction."
        ),
    }


def kelly(win_rate: float, payoff_ratio: float, fraction: float = 0.25) -> dict:
    """Kelly fraction from win rate p and win/loss payoff ratio b, then the
    recommended fractional-Kelly stake. win_rate in 0-1."""
    p = max(0.0, min(1.0, win_rate))
    q = 1 - p
    b = max(0.01, payoff_ratio)
    f_star = (b * p - q) / b
    rec = f_star * fraction
    if f_star <= 0:
        msg = ("Negative Kelly — this edge/payoff combination has no positive expectancy. "
               "The correct size is ZERO. Don't trade it.")
    else:
        msg = (f"Full Kelly says {f_star*100:.0f}% of capital — but full Kelly draws down "
               f"~50% about a third of the time. Quarter-Kelly ({rec*100:.1f}%) captures most "
               "of the growth at a fraction of the pain. Use the fraction.")
    return {
        "available": True,
        "full_kelly_pct": round(f_star * 100, 1),
        "fractional_pct": round(max(0.0, rec) * 100, 1),
        "fraction_used": fraction,
        "note": msg,
    }


def portfolio_heat(positions: list[dict], account: float,
                   atr_mult: float = DEFAULT_ATR_MULT) -> dict:
    """positions: [{ticker, shares, entry, stop?}]. If no stop, none assumed
    (counts as full position at risk only if you set one). Returns total open
    risk as % of account."""
    total_risk = 0.0
    rows = []
    for pchg in positions:
        entry = pchg.get("entry")
        stop = pchg.get("stop")
        shares = pchg.get("shares", 0)
        if entry and stop and stop < entry:
            r = shares * (entry - stop)
            total_risk += r
            rows.append({"ticker": pchg["ticker"], "risk": round(r, 2)})
    heat = total_risk / account * 100 if account else None
    flag = heat is not None and heat > 6
    return {
        "available": True,
        "total_open_risk": round(total_risk, 2),
        "heat_pct": round(heat, 1) if heat is not None else None,
        "positions": rows,
        "note": (
            (f"Total open risk (sum of distance-to-stop) is {heat:.1f}% of the account. "
             + ("That's hot — most position-sizing frameworks cap portfolio heat near 6%. "
                "A cluster of correlated stops (e.g. all your semis) could realize most of it "
                "at once." if flag else "Within a typical ~6% heat budget."))
            if heat is not None else "Set stops on positions to compute heat."
        ),
    }


def concentration(weights: dict[str, float], themes: dict[str, list[str]] | None = None) -> dict:
    """weights: ticker -> fraction of account (0-1), INCLUDING ETF look-through if
    you pass it pre-resolved. Flags single-name and theme breaches."""
    over_single = {t: round(w * 100, 1) for t, w in weights.items() if w > SINGLE_NAME_CAP}
    theme_exposure = {}
    if themes:
        for name, tickers in themes.items():
            exp = sum(weights.get(t, 0) for t in tickers)
            theme_exposure[name] = round(exp * 100, 1)
    over_theme = {n: e for n, e in theme_exposure.items() if e > THEME_CAP * 100}
    notes = []
    if over_single:
        notes.append("Single-name >10%: " + ", ".join(f"{t} {p}%" for t, p in over_single.items())
                     + ". On a small account, one name above 10% is a bet, not a position.")
    if over_theme:
        notes.append("Theme >40% (look-through): " + ", ".join(f"{n} {e}%" for n, e in over_theme.items())
                     + ". Correlated names sell off together — this is your real risk, not the line items.")
    if not notes:
        notes.append("Within single-name (<=10%) and theme (<=40%) caps. Diversified for the size.")
    return {
        "available": True,
        "over_single_name": over_single,
        "theme_exposure": theme_exposure,
        "over_theme": over_theme,
        "notes": notes,
    }
