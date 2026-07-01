"""What the pros are saying — ONE calm line, for panic moments.

Pulls the analyst consensus (rating + mean 12-mo target + analyst count) from
Yahoo via yfinance and renders a single sentence. When the stock is in a
double-digit drawdown but the street's targets still sit well above price, it
adds the one line the user actually needs at 11pm: the consensus reads this
as volatility, not a broken thesis.

HONESTY NOTE baked into the payload: sell-side targets skew optimistic
(documented in the analyst-forecast literature), so this is a SENTIMENT
gauge — "what the pros say" — not an expected return.
"""
from __future__ import annotations

import numpy as np

REC_LABEL = {
    "strong_buy": "Strong Buy",
    "buy": "Buy",
    "hold": "Hold",
    "underperform": "Underperform",
    "sell": "Sell",
}


def snapshot(ticker: str, df, fetch_info=None) -> dict:
    """One-line analyst consensus. `fetch_info(ticker) -> dict` is injectable
    for tests; defaults to yfinance Ticker.info."""
    if fetch_info is None:
        def fetch_info(tk):  # pragma: no cover - network path
            import yfinance as yf
            return yf.Ticker(tk).info or {}
    try:
        info = fetch_info(ticker) or {}
    except Exception:
        return {"available": False, "reason": "analyst data unavailable"}

    target = info.get("targetMeanPrice")
    n = info.get("numberOfAnalystOpinions")
    key = (info.get("recommendationKey") or "").lower()
    mean = info.get("recommendationMean")
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None and df is not None and len(df):
        price = float(df["close"].iloc[-1])
    if not target or not price or not n:
        return {"available": False, "reason": "no consensus data for this ticker"}

    upside = (float(target) / float(price) - 1) * 100
    label = REC_LABEL.get(key, key.title() or "n/a")

    line = (
        f"Street consensus: {label}"
        + (f" ({mean:.1f}/5 scale)" if isinstance(mean, (int, float)) else "")
        + f" across {int(n)} analysts; average 12-mo target {float(target):,.0f} "
        f"({upside:+.0f}% vs price)."
    )

    # The calm line for drawdown panics: consensus intact + targets above.
    calm = None
    if df is not None and len(df) > 63:
        close = df["close"].astype(float)
        dd = float(close.iloc[-1] / close.iloc[-63:].max() - 1)
        if dd < -0.12 and upside > 10 and key in ("buy", "strong_buy"):
            calm = (
                f"Despite the {abs(dd)*100:.0f}% pullback from the 3-month high, the consensus rating "
                f"hasn't moved off {label} and targets sit {upside:+.0f}% above price — the street is "
                "treating this as volatility, not a broken thesis."
            )

    return {
        "available": True,
        "rating": label,
        "rating_mean": round(float(mean), 2) if isinstance(mean, (int, float)) else None,
        "n_analysts": int(n),
        "target_mean": round(float(target), 2),
        "upside_pct": round(upside, 1),
        "line": line,
        "calm_line": calm,
        "caveat": (
            "Sentiment gauge only: sell-side targets skew optimistic on average, so read the "
            "direction and the CHANGE in consensus, not the level."
        ),
    }
