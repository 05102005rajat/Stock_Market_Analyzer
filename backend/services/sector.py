"""Sector Pulse — what the displayed stock's sector is doing, with HONEST odds.

Detects sector-wide moves (e.g., 8 of 9 semis down >1% today) and tells the
user what such days historically meant — which, per crosssection_test.py, is
mostly: NOT further sector-specific downside. The point of this card is
context and panic-prevention, not prediction.

EVIDENCE (cached 80-name universe, 2016-2026, point-in-time, n=442
non-overlapping sector-event days):
  * After >=80% of a sector fell >=1% in one day, the sector tracked the
    MARKET afterward: vs-market +0.03% (5d) / -0.21% (21d). The event prices
    the news; it does not start a sector-only slide.
  * The member that stayed GREEN on the event day showed no delayed
    contagion: next-5d +0.51% / 53% win vs +0.49% / 51% unconditional.
  * Within-sector laggards do NOT catch up to leaders (-0.24%/21d, t=-0.6,
    906 sector-months) — mild momentum, if anything.
  * Chip designers -> equipment makers: same-month corr 0.71 but NO usable
    lag (predictive spread negative). Megacap links are priced same-day.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Hand-mapped sectors for the cached universe; analyze() falls back to
# "uncovered" for tickers outside it (UI then hides the card).
SECTORS: dict[str, list[str]] = {
    "Semiconductors": ["AMAT", "AMD", "AVGO", "INTC", "LRCX", "MU", "NVDA", "QCOM", "TXN"],
    "Software/Cloud": ["ADBE", "CRM", "CRWD", "DDOG", "DOCU", "IBM", "MSFT", "NET", "ORCL", "PLTR", "SNOW", "ZM"],
    "Internet/Consumer Tech": ["AAPL", "AMZN", "GOOGL", "META", "NFLX", "ABNB", "UBER", "SHOP", "ETSY", "RBLX", "ROKU", "CVNA", "PDD"],
    "Financials": ["BAC", "C", "GS", "JPM", "MS", "WFC", "COIN", "PYPL"],
    "Healthcare/Pharma": ["ABBV", "BMY", "JNJ", "LLY", "MRK", "MRNA", "PFE", "UNH"],
    "Utilities/Power": ["CEG", "DUK", "NEE", "SO", "VST"],
    "Consumer Staples": ["KO", "PEP", "PG", "COST", "WMT", "TGT"],
    "Consumer Discretionary": ["HD", "LOW", "MCD", "SBUX", "NKE", "AZO", "TSLA"],
    "Industrials": ["BA", "CAT", "DE", "GE", "HON", "UNP"],
    "Energy": ["CVX", "XOM"],
    "Telecom": ["T", "VZ", "CSCO"],
}

TICKER_SECTOR = {t: s for s, tks in SECTORS.items() for t in tks}

EVIDENCE = {
    "tested": True,
    "n_events": 442,
    "universe": "80 large/mid caps, 10y daily, point-in-time",
    "finding_event": (
        "Sector-wide down days did NOT predict further sector-specific weakness: "
        "vs-market +0.03% (5d) / -0.21% (21d) afterward. The drop priced the news."
    ),
    "finding_survivor": (
        "Members that stayed green on the event day showed NO delayed contagion "
        "(next-5d +0.51%, 53% win — same as the unconditional 51%)."
    ),
    "finding_laggard": (
        "Within-sector laggards did not catch up to leaders (-0.24%/21d, t=-0.6, "
        "n=906 sector-months)."
    ),
    "finding_divergence": (
        "Tight-pair divergences (one twin drops >2.5%, the other doesn't, n=324): the "
        "untouched twin did NOT fall later — next-5d +0.69% vs +0.49% unconditional."
    ),
    "finding_bellwether": (
        "Megacap -5% crash days dragged the market the SAME day (NVDA crashes: market "
        "-2.54%), but the NEXT day averaged a bounce (+0.27% vs +0.10% base), not "
        "continuation."
    ),
}


def sector_of(ticker: str) -> str | None:
    return TICKER_SECTOR.get(ticker.upper())


def analyze(ticker: str, fetch_close) -> dict:
    """Sector pulse for `ticker`. `fetch_close(tk) -> pd.Series` of daily
    closes (>= ~30 bars); injected so the caller controls source + caching."""
    ticker = ticker.upper()
    sec = sector_of(ticker)
    if not sec:
        return {"available": False, "reason": "ticker not in sector map"}

    peers = SECTORS[sec]
    closes = {}
    for tk in peers:
        try:
            s = fetch_close(tk)
            if s is not None and len(s.dropna()) >= 25:
                closes[tk] = s.astype(float)
        except Exception:
            continue
    if len(closes) < max(4, len(peers) // 2):
        return {"available": False, "reason": "not enough peer data"}

    px = pd.DataFrame(closes).dropna(how="all")
    ret = px.pct_change()
    today = ret.iloc[-1].dropna()
    r5 = (px.iloc[-1] / px.iloc[-6] - 1).dropna() if len(px) > 6 else today
    r21 = (px.iloc[-1] / px.iloc[-22] - 1).dropna() if len(px) > 22 else r5

    frac_down = float((today < -0.01).mean())
    frac_up = float((today > 0.01).mean())
    event = None
    if frac_down >= 0.8:
        event = "broad_selloff"
    elif frac_up >= 0.8:
        event = "broad_rally"

    me_today = float(today.get(ticker, np.nan))
    survivor = event == "broad_selloff" and not np.isnan(me_today) and me_today > 0

    # peer-relative standing over the last month
    gap21 = None
    if ticker in r21.index and len(r21) >= 5:
        gap21 = float(r21[ticker] - r21.mean())

    members = [
        {"ticker": tk, "today_pct": round(100 * float(today[tk]), 2) if tk in today else None,
         "r21_pct": round(100 * float(r21[tk]), 2) if tk in r21.index else None}
        for tk in peers if tk in px.columns
    ]
    members.sort(key=lambda m: (m["today_pct"] is None, -(m["today_pct"] or 0)))

    notes: list[str] = []
    if event == "broad_selloff":
        notes.append(
            f"{int(round(frac_down * (today.size)))} of {today.size} {sec} names are down >1% today — a "
            "sector-wide event. Historically (n=442) these days did NOT start a sector-only slide: the "
            "sector tracked the market afterward (+0.03% vs market over the next week). The drop already "
            "priced the news; panic-adding to it had no historical support."
        )
        if survivor:
            notes.append(
                f"{ticker} stayed green while its sector bled. Measured across 584 such survivors: no "
                "delayed contagion (next-5d +0.51%, 53% win — same as any stock on any day)."
            )
    elif event == "broad_rally":
        notes.append(
            f"Most of {sec} is up >1% today — a sector-wide rally day. Same evidence applies in reverse: "
            "these days mark news being priced, not the start of a sector-only run."
        )
    if gap21 is not None and abs(gap21) > 0.05 and not event:
        if gap21 < 0:
            notes.append(
                f"{ticker} has lagged its sector by {abs(gap21)*100:.1f}% over the past month. Honest "
                "finding: laggards did NOT reliably catch up (-0.24%/21d vs leaders, t=-0.6) — don't buy "
                "it just because peers ran."
            )
        else:
            notes.append(
                f"{ticker} has led its sector by {abs(gap21)*100:.1f}% over the past month. Honest "
                "finding: leaders did not reliably mean-revert to the pack either (mild momentum, if "
                "anything) — being extended vs peers alone was not a sell signal."
            )

    # ---- "Is it me or is it everyone?" attribution via closest peers ----
    closest, attribution = [], None
    if ticker in ret.columns and len(ret) >= 40:
        cors = ret.corr()[ticker].drop(ticker, errors="ignore").dropna()
        closest = list(cors.nlargest(3).index)
        if closest and not np.isnan(me_today) and abs(me_today) >= 0.025:
            peer_today = float(today[closest].mean())
            resid = me_today - peer_today
            if abs(peer_today) < 0.01 and abs(resid) >= 0.02:
                attribution = (
                    f"{ticker} {me_today*100:+.1f}% today while its closest peers "
                    f"({', '.join(closest)}) are flat ({peer_today*100:+.1f}%) — this move is "
                    "STOCK-SPECIFIC news, not an industry event. (And the peers aren't 'due' to "
                    "follow: across 324 measured divergences, the untouched twin's next 5 days "
                    "averaged +0.69% — slightly BETTER than the +0.49% base rate.)"
                )
            elif np.sign(peer_today) == np.sign(me_today) and abs(peer_today) >= abs(me_today) * 0.5:
                attribution = (
                    f"{ticker} {me_today*100:+.1f}% with closest peers ({', '.join(closest)}) at "
                    f"{peer_today*100:+.1f}% — a GROUP move, not company news. Measured on megacap "
                    "-5% crash days: the market fell with them SAME day, then averaged a small bounce "
                    "the next day (e.g., +0.27% after NVDA crashes vs +0.10% base) — not continuation."
                )
            if attribution:
                notes.insert(0, attribution)

    return {
        "available": True,
        "sector": sec,
        "closest_peers": closest,
        "n_members": int(today.size),
        "frac_down_today": round(frac_down, 2),
        "frac_up_today": round(frac_up, 2),
        "event": event,
        "survivor": survivor,
        "ticker_gap21_pct": round(gap21 * 100, 2) if gap21 is not None else None,
        "sector_today_pct": round(100 * float(today.mean()), 2),
        "sector_r5_pct": round(100 * float(r5.mean()), 2),
        "sector_r21_pct": round(100 * float(r21.mean()), 2),
        "members": members,
        "notes": notes,
        "evidence": EVIDENCE,
        "caveat": (
            "Context, not prediction: sector co-movement is real but priced same-day in large caps. "
            "Base rates from 80 surviving large caps."
        ),
    }
