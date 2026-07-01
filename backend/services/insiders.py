"""Insider buying/selling engine — parses ACTUAL transactions, not just filings.

The old version counted Form 4 *filings* and called any cluster "buying" — wrong,
because most large-cap Form 4s are option exercises and planned sales, not
open-market purchases. This version parses each Form 4's XML to extract the
transaction CODE, shares, and price, so it can say plainly: did insiders BUY or
SELL, how much, and at what price.

Codes: P = open-market PURCHASE (the real signal), S = sale, A = grant,
M = option exercise, F = tax withholding. We surface P/S and discount A/M/F.

Evidence: Lakonishok-Lee, Cohen-Malloy-Pomorski — signal is in PURCHASES,
strongest when multiple insiders buy. Edge decayed post-2003; modest after costs.

Data: SEC EDGAR, free, needs SEC_USER_AGENT. Degrades gracefully without net.
"""
from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

import requests

UA = os.environ.get("SEC_USER_AGENT", "StockApp research contact@example.com")
LOOKBACK_DAYS = 90
_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 6 * 3600

EVIDENCE = {
    "why": ("Open-market insider BUYS (code P) are the best-evidenced free signal "
            "(Lakonishok-Lee; Cohen-Malloy-Pomorski). Sales are noisier."),
    "caveat": ("Edge decayed after the 2003 2-day filing rule; modest after costs. "
               "Idea generation, not a copy-this signal."),
}


def _cik_for(ticker: str) -> str | None:
    r = requests.get("https://www.sec.gov/files/company_tickers.json",
                     headers={"User-Agent": UA}, timeout=8)
    r.raise_for_status()
    for row in r.json().values():
        if row.get("ticker", "").upper() == ticker.upper():
            return str(row["cik_str"]).zfill(10)
    return None


def _recent_form4_accessions(cik: str, days: int) -> list[dict]:
    r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                     headers={"User-Agent": UA}, timeout=10)
    r.raise_for_status()
    recent = r.json().get("filings", {}).get("recent", {})
    forms, accns = recent.get("form", []), recent.get("accessionNumber", [])
    dates, prim = recent.get("filingDate", []), recent.get("primaryDocument", [])
    cutoff = date.today() - timedelta(days=days)
    out = []
    for i, form in enumerate(forms):
        if form != "4":
            continue
        try:
            if datetime.strptime(dates[i], "%Y-%m-%d").date() < cutoff:
                continue
        except Exception:
            continue
        out.append({"accession": accns[i].replace("-", ""), "date": dates[i],
                    "doc": prim[i] if i < len(prim) else None})
    return out


def _parse_form4_xml(cik: str, accession: str, doc: str) -> list[dict]:
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{doc}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    owner = (root.findtext(".//reportingOwnerId/rptOwnerName") or "insider").strip()
    is_officer = root.findtext(".//reportingOwnerRelationship/isOfficer") or "0"
    is_director = root.findtext(".//reportingOwnerRelationship/isDirector") or "0"
    title = (root.findtext(".//reportingOwnerRelationship/officerTitle") or "").strip()
    role = title or ("Director" if is_director in ("1", "true") else
                     "Officer" if is_officer in ("1", "true") else "Insider")
    rows = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code = tx.findtext(".//transactionCoding/transactionCode") or ""
        shares = tx.findtext(".//transactionAmounts/transactionShares/value")
        price = tx.findtext(".//transactionAmounts/transactionPricePerShare/value")
        ad = tx.findtext(".//transactionAmounts/transactionAcquiredDisposedCode/value") or ""
        try:
            shares = float(shares) if shares else 0.0
            price = float(price) if price else 0.0
        except Exception:
            shares, price = 0.0, 0.0
        rows.append({"code": code, "shares": shares, "price": price,
                     "ad": ad, "owner": owner, "role": role})
    return rows


def _summarize(transactions: list[dict]) -> dict:
    buys = [t for t in transactions if t["code"] == "P"]
    sells = [t for t in transactions if t["code"] == "S"]
    routine = [t for t in transactions if t["code"] in ("A", "M", "F", "G")]

    def agg(rows):
        sh = sum(r["shares"] for r in rows)
        val = sum(r["shares"] * r["price"] for r in rows)
        people = sorted({r["owner"] for r in rows})
        prices = [r["price"] for r in rows if r["price"] > 0]
        return {"n_tx": len(rows), "n_people": len(people), "shares": int(sh),
                "value": round(val), "people": people[:6],
                "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
                "csuite": any(any(k in (r["role"] or "").lower()
                                  for k in ("ceo", "cfo", "chief", "president", "chairman"))
                              for r in rows)}

    b, s = agg(buys), agg(sells)
    cluster_buy = b["n_people"] >= 3 and b["shares"] > 0
    # Classify by dollar value when available, else fall back to shares — a real
    # purchase with a missing/zero price (gifts, some conversions) must not vanish.
    b_weight = b["value"] if b["value"] > 0 else b["shares"]
    s_weight = s["value"] if s["value"] > 0 else s["shares"]
    if b_weight > 0 and b_weight >= s_weight:
        signal, badge = "buying", "INSIDERS BOUGHT"
    elif s_weight > 0 and s_weight > b_weight:
        signal, badge = "selling", "INSIDERS SOLD"
    else:
        signal, badge = "routine", "NO OPEN-MARKET TRADES"
    return {"buys": b, "sells": s, "n_routine": len(routine),
            "signal": signal, "badge": badge, "cluster_buy": cluster_buy}


def analyze(ticker: str, fetch_transactions=None) -> dict:
    ticker = ticker.upper()
    now = time.time()
    if ticker in _CACHE and now - _CACHE[ticker][0] < _TTL:
        return _CACHE[ticker][1]
    try:
        if fetch_transactions is not None:
            txns = fetch_transactions(ticker)
        else:
            cik = _cik_for(ticker)
            if not cik:
                raise RuntimeError("no CIK")
            txns = []
            for f in _recent_form4_accessions(cik, LOOKBACK_DAYS):
                if not f["doc"]:
                    continue
                try:
                    txns.extend(_parse_form4_xml(cik, f["accession"], f["doc"]))
                except Exception:
                    continue
                time.sleep(0.12)
    except Exception:
        out = {"available": False,
               "reason": "SEC data unavailable here (set SEC_USER_AGENT and run with internet).",
               "evidence": EVIDENCE}
        _CACHE[ticker] = (now, out)
        return out

    if not txns:
        out = {"available": False, "reason": "no recent Form 4 transactions",
               "evidence": EVIDENCE}
        _CACHE[ticker] = (now, out)
        return out

    summ = _summarize(txns)
    b, s = summ["buys"], summ["sells"]
    if summ["signal"] == "buying":
        money = f"${b['value']:,}" if b["value"] else ""
        price = f" around ${b['avg_price']}" if b["avg_price"] else ""
        plain = (f"{b['n_people']} insider(s) BOUGHT about {b['shares']:,} shares"
                 f"{(' (' + money + ')') if money else ''}{price} in the last {LOOKBACK_DAYS} days"
                 + (", including a top executive" if b["csuite"] else "")
                 + ". Insiders buying with their own cash is the meaningful signal — still just one input.")
    elif summ["signal"] == "selling":
        money = f"${s['value']:,}" if s["value"] else ""
        plain = (f"Insiders SOLD about {s['shares']:,} shares{(' (' + money + ')') if money else ''} recently. "
                 "Selling is a weak signal alone — insiders sell for taxes, diversification, or planned schedules.")
    else:
        plain = (f"No open-market insider buys or sells in {LOOKBACK_DAYS} days — just {summ['n_routine']} "
                 "routine grant/option/tax filing(s), which don't signal a market view.")

    out = {"available": True, "signal": summ["signal"], "badge": summ["badge"],
           "cluster_buy": summ["cluster_buy"],
           "buy_shares": b["shares"], "buy_value": b["value"], "buy_people": b["n_people"],
           "buy_avg_price": b["avg_price"], "buy_csuite": b["csuite"],
           "sell_shares": s["shares"], "sell_value": s["value"], "sell_people": s["n_people"],
           "n_routine": summ["n_routine"], "plain": plain, "evidence": EVIDENCE,
           "lookback_days": LOOKBACK_DAYS}
    _CACHE[ticker] = (now, out)
    return out
