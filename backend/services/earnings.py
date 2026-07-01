"""Earnings run-up watch — the ONE cross-sectional idea that tested positive.

Finding (crosssection_test.py, volume-spike-event proxy, n=962, t=-2.39):
stocks that ran hard (top 30%, ~+10%) in the 10 days into an event went FLAT
over the next month (-0.07%, 51% win), while weak-run-up names gained +2.82%
(58% win). Consistent with the earnings-announcement-premium reversal
(Frazzini & Lamont 2007). So: a big pre-earnings run-up is a "much is already
priced in" flag — not a sell signal, a expectations-are-high flag.

Earnings dates come from Finnhub's free tier (60 calls/min). Set
FINNHUB_API_KEY in the environment; without it this module degrades
gracefully to {"available": False}. Responses are cached for 12h.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta

import requests

_CACHE: dict[str, tuple[float, "date | None"]] = {}
_TTL = 12 * 3600

RUNUP_LOOKBACK = 10   # trading days
RUNUP_BIG = 0.08      # ~top-30% threshold from the study (mean +9.6%)
WINDOW_DAYS = 7       # flag earnings within the next calendar week

EVIDENCE = {
    "tested": True,
    "n_events": 962,
    "finding": (
        "Big 10-day run-ups into high-attention events went flat over the next month "
        "(-0.07%, 51% win) vs +2.82% (58% win) after weak run-ups; spread t=-2.39. "
        "A hot run INTO earnings means expectations are already paid for."
    ),
    "proxy_caveat": (
        "Measured on volume-spike events (an earnings proxy that under-detects "
        "mega-caps); treat magnitudes as approximate."
    ),
}


def next_earnings_date(ticker: str) -> date | None:
    """Next confirmed earnings date via Finnhub, or None (no key / none found)."""
    ticker = ticker.upper()
    now = time.time()
    if ticker in _CACHE and now - _CACHE[ticker][0] < _TTL:
        return _CACHE[ticker][1]
    key = os.environ.get("FINNHUB_API_KEY")
    if not key:
        return None
    try:
        frm = date.today().isoformat()
        to = (date.today() + timedelta(days=120)).isoformat()
        r = requests.get(
            "https://finnhub.io/api/v1/calendar/earnings",
            params={"symbol": ticker, "from": frm, "to": to, "token": key},
            timeout=8,
        )
        r.raise_for_status()
        items = (r.json() or {}).get("earningsCalendar") or []
        dates = sorted(
            datetime.strptime(it["date"], "%Y-%m-%d").date()
            for it in items
            if it.get("date")
        )
        nxt = dates[0] if dates else None
    except Exception:
        # Transient failure (timeout, rate-limit, 5xx): don't poison the 12h
        # cache with a false "no earnings" — just skip caching and retry later.
        return None
    _CACHE[ticker] = (now, nxt)
    return nxt


def analyze(ticker: str, df) -> dict:
    """Earnings-proximity + run-up flag. `df` = daily OHLCV with 'close'."""
    nxt = next_earnings_date(ticker)
    if nxt is None:
        return {
            "available": False,
            "reason": "no upcoming earnings found (or FINNHUB_API_KEY not set)",
        }
    days_to = (nxt - date.today()).days
    close = df["close"].astype(float)
    runup = None
    if len(close) > RUNUP_LOOKBACK + 1:
        runup = float(close.iloc[-1] / close.iloc[-(RUNUP_LOOKBACK + 1)] - 1)

    flag = days_to <= WINDOW_DAYS and runup is not None and runup >= RUNUP_BIG
    note = None
    if flag:
        note = (
            f"Earnings in {days_to} day{'s' if days_to != 1 else ''} and {ticker} has already run "
            f"{runup*100:+.1f}% in the last {RUNUP_LOOKBACK} sessions. Historically, names this hot into "
            "an event went FLAT over the following month (-0.1%, 51% win) while calm names gained +2.8% "
            "(58% win). Expectations look pre-paid — size and stops accordingly."
        )
    elif days_to <= WINDOW_DAYS:
        note = (
            f"Earnings in {days_to} day{'s' if days_to != 1 else ''}; no unusual pre-earnings run-up "
            f"({(runup or 0)*100:+.1f}% / {RUNUP_LOOKBACK}d). Event risk applies, but the "
            "expectations-pre-paid pattern does not."
        )

    return {
        "available": True,
        "next_earnings": nxt.isoformat(),
        "days_to_earnings": days_to,
        "runup_10d_pct": round(runup * 100, 2) if runup is not None else None,
        "hot_runup": bool(flag),
        "note": note,
        "evidence": EVIDENCE,
        "caveat": "Descriptive base rate, not a sell signal. Event-day direction still depends on the surprise.",
    }
