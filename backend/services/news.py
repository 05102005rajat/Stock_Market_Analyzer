"""Recent headlines — the "WHY is it moving" layer.

Shows the 3 most recent headlines for the ticker (via Yahoo through yfinance)
so a price move can be connected to its catalyst (earnings, policy news, the
"the president said something about chips" days) instead of traded blind.

HONESTY: headlines are for ATTRIBUTION, not prediction. News-reaction edges
are the fastest-arbitraged in the market; by the time a headline is readable,
the first move is priced. Use this to understand the move and to avoid
trading on stale panic — not to front-run anything.
"""
from __future__ import annotations

import time


def _extract(item: dict) -> dict | None:
    """yfinance news schema has changed across versions; handle both."""
    if not isinstance(item, dict):
        return None
    content = item.get("content") if isinstance(item.get("content"), dict) else item
    title = content.get("title") or item.get("title")
    if not title:
        return None
    publisher = (
        (content.get("provider") or {}).get("displayName")
        if isinstance(content.get("provider"), dict)
        else item.get("publisher")
    )
    link = None
    if isinstance(content.get("canonicalUrl"), dict):
        link = content["canonicalUrl"].get("url")
    link = link or item.get("link")
    ts = item.get("providerPublishTime") or content.get("pubDate")
    when = None
    if isinstance(ts, (int, float)):
        age_h = max(0.0, (time.time() - float(ts)) / 3600)
        when = f"{age_h:.0f}h ago" if age_h < 48 else f"{age_h/24:.0f}d ago"
    elif isinstance(ts, str):
        when = ts[:10]
    return {"title": str(title)[:160], "publisher": publisher, "link": link, "when": when}


def headlines(ticker: str, limit: int = 3, fetch_news=None) -> dict:
    if fetch_news is None:
        def fetch_news(tk):  # pragma: no cover - network path
            import yfinance as yf
            return yf.Ticker(tk).news or []
    try:
        raw = fetch_news(ticker) or []
    except Exception:
        return {"available": False, "items": []}
    items = [x for x in (_extract(i) for i in raw) if x][:limit]
    return {
        "available": bool(items),
        "items": items,
        "caveat": (
            "For attribution only — by the time a headline is readable, the first move is priced."
        ),
    }
