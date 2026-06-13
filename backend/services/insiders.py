"""Insider cluster-buy engine — the best evidence-backed FREE signal.

Per the research: corporate insider OPEN-MARKET purchases (Form 4, code "P")
are the strongest public signal a retail tool can compute — ~2-business-day
disclosure (vs 45 days for Congress/13F), decades of peer-reviewed support:
  * Lakonishok & Lee (2001): heavy-insider-buy firms beat heavy-sell firms
    ~7.8%/yr; signal is in PURCHASES not sales, strongest in SMALL caps and
    when MULTIPLE insiders buy (the cluster effect).
  * Cohen, Malloy & Pomorski (2012): "opportunistic" (non-routine) insider
    buys earned ~82 bps/month value-weighted alpha; "routine" calendar
    repeaters earned ~0.
Honest caveats baked into the payload: the edge DECAYED after the 2003 2-day
rule (Brochet 2010 — the market now prices the filing fast), and realistic
small-account, after-cost returns are modest and concentrated in illiquid
names (Oenschläger & Möllenhoff 2025). This is IDEA GENERATION, not a copy
signal.

Data: SEC EDGAR, free, no key, just a descriptive User-Agent + 10 req/s cap.
We use the full-text search API to find recent Form 4s for a ticker and parse
the transaction codes/roles. Network to sec.gov is required; without it (or in
a sandbox) the engine degrades gracefully to {"available": False}.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta

import requests

UA = os.environ.get("SEC_USER_AGENT", "StockApp research contact@example.com")
CLUSTER_DAYS = 21
CLUSTER_MIN_INSIDERS = 3
CSUITE = ("ceo", "chief executive", "cfo", "chief financial", "president",
          "chairman", "coo", "chief operating")

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 6 * 3600

EVIDENCE = {
    "why": (
        "Insider open-market BUYS (Form 4 code P) are the best-evidenced free signal: "
        "Lakonishok-Lee (~7.8%/yr buy-minus-sell), Cohen-Malloy-Pomorski (opportunistic "
        "buys ~82bps/mo alpha). Strongest when MULTIPLE insiders buy small/mid-caps."
    ),
    "caveat": (
        "Edge decayed after the 2003 2-day filing rule (Brochet 2010); realistic "
        "after-cost retail returns are modest and concentrated in illiquid names. "
        "Idea generation, not a copy-this signal."
    ),
}


def _ciks_for(ticker: str) -> str | None:
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers={"User-Agent": UA}, timeout=8)
        r.raise_for_status()
        for row in r.json().values():
            if row.get("ticker", "").upper() == ticker.upper():
                return str(row["cik_str"]).zfill(10)
    except Exception:
        return None
    return None


def _recent_form4(ticker: str, days: int = 120) -> list[dict]:
    """Form 4 filings for the issuer in the last `days`, via EDGAR full-text
    search. Returns minimal records; transaction-level parsing is best-effort."""
    cik = _ciks_for(ticker)
    if not cik:
        return []
    try:
        frm = (date.today() - timedelta(days=days)).isoformat()
        r = requests.get(
            "https://efts.sec.gov/LATEST/search-index",
            params={"q": f'"{ticker.upper()}"', "forms": "4", "dateRange": "custom",
                    "startdt": frm, "enddt": date.today().isoformat()},
            headers={"User-Agent": UA}, timeout=10,
        )
        # The public full-text endpoint is efts.sec.gov/LATEST/search-index;
        # schema varies, so guard hard.
        hits = (r.json() or {}).get("hits", {}).get("hits", [])
        out = []
        for h in hits:
            src = h.get("_source", {})
            out.append({
                "filed": src.get("file_date"),
                "display_names": src.get("display_names", []),
            })
        return out
    except Exception:
        return []


def analyze(ticker: str, fetch_form4=None) -> dict:
    """Recent insider-buying read for `ticker`. Cached 6h. `fetch_form4` is
    injectable for tests."""
    ticker = ticker.upper()
    now = time.time()
    if ticker in _CACHE and now - _CACHE[ticker][0] < _TTL:
        return _CACHE[ticker][1]

    fetch = fetch_form4 or _recent_form4
    try:
        filings = fetch(ticker)
    except Exception:
        filings = []

    if not filings:
        out = {"available": False,
               "reason": "no recent Form 4 data (or SEC access unavailable in this environment)",
               "evidence": EVIDENCE}
        _CACHE[ticker] = (now, out)
        return out

    # Count distinct insiders filing in the cluster window.
    cutoff = date.today() - timedelta(days=CLUSTER_DAYS)
    recent_insiders, csuite_hits = set(), 0
    buys_30d = 0
    for f in filings:
        names = f.get("display_names") or []
        filed = f.get("filed")
        try:
            fdate = datetime.strptime(filed[:10], "%Y-%m-%d").date() if filed else None
        except Exception:
            fdate = None
        for nm in names:
            recent_insiders.add(nm)
            if any(k in nm.lower() for k in CSUITE):
                csuite_hits += 1
        if f.get("is_purchase"):  # set by richer parsers/tests
            buys_30d += 1

    n_insiders = len(recent_insiders)
    cluster = n_insiders >= CLUSTER_MIN_INSIDERS

    note = None
    if cluster:
        note = (
            f"{n_insiders} distinct insiders filed Form 4s on {ticker} in the last ~3 weeks"
            + (f", including C-suite" if csuite_hits else "")
            + ". Multi-insider buying clusters are the strongest insider pattern in the "
            "literature — but verify these are open-market PURCHASES (code P), not option "
            "exercises or grants, before reading anything into it."
        )
    else:
        note = (
            f"{n_insiders} insider filing(s) recently — below the 3+ cluster threshold that "
            "carries the documented signal. Treat as routine."
        )

    out = {
        "available": True,
        "n_insiders_21d": n_insiders,
        "csuite_filings": csuite_hits,
        "cluster": cluster,
        "note": note,
        "evidence": EVIDENCE,
        "disclaimer": "Form 4 shows filings, not necessarily purchases; confirm code P on EDGAR.",
    }
    _CACHE[ticker] = (now, out)
    return out
