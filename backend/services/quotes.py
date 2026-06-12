"""Live(ish) quote — the latest price instead of yesterday's close.

Uses yfinance fast_info (Yahoo). Honesty: free Yahoo quotes are typically
~15 minutes delayed for US equities; good enough for swing decisions, not
for scalping the open. Cached for 30s so UI polling stays cheap.
"""
from __future__ import annotations

import time

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 30.0


def fetch(ticker: str, fetch_fast_info=None) -> dict:
    ticker = ticker.upper()
    now = time.time()
    if ticker in _CACHE and now - _CACHE[ticker][0] < _TTL:
        return _CACHE[ticker][1]

    if fetch_fast_info is None:
        def fetch_fast_info(tk):  # pragma: no cover - network path
            import yfinance as yf
            return yf.Ticker(tk).fast_info

    try:
        fi = fetch_fast_info(ticker)
        get = (lambda k: fi.get(k)) if isinstance(fi, dict) else (lambda k: getattr(fi, k, None))
        last = get("last_price") or get("lastPrice")
        prev = get("previous_close") or get("previousClose")
        out = {
            "available": last is not None,
            "price": round(float(last), 2) if last else None,
            "prev_close": round(float(prev), 2) if prev else None,
            "change_pct": round((float(last) / float(prev) - 1) * 100, 2) if last and prev else None,
            "day_high": round(float(get("day_high") or 0), 2) or None,
            "day_low": round(float(get("day_low") or 0), 2) or None,
            "asof": int(now),
            "caveat": "Yahoo free quotes are typically ~15 min delayed.",
        }
    except Exception:
        out = {"available": False, "reason": "quote unavailable"}
    _CACHE[ticker] = (now, out)
    return out
