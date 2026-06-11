"""Portfolio analytics for the user's own holdings.

Two honest, NON-predictive things that matter for a real book:
  1. value each position (cost basis vs current) — what you own & what it's worth,
  2. ETF look-through — your TRUE single-name exposure once VOO/QQQ/SPYM are
     resolved into their constituents (you may be far less diversified than the
     direct weights suggest).

Plus a light per-holding read (trend + the weekly vol-scaled target) reusing the
single-stock engines. Per-stock direction is NOT predicted (proven futile).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import yfinance as yf

from services import data, indicators, target, trends

HOLDINGS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "holdings.json")
MEGACAP8 = {"AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA"}
_fund_cache: dict[str, dict | None] = {}
_fund_sector_cache: dict[str, dict | None] = {}
_stock_sector_cache: dict[str, str] = {}

_SECTOR_LABELS = {
    "technology": "Technology", "financial_services": "Financial Services",
    "healthcare": "Healthcare", "consumer_cyclical": "Consumer Cyclical",
    "communication_services": "Communication Services", "industrials": "Industrials",
    "consumer_defensive": "Consumer Defensive", "energy": "Energy",
    "utilities": "Utilities", "realestate": "Real Estate", "basic_materials": "Basic Materials",
}


def _norm_sector(s: str) -> str:
    return _SECTOR_LABELS.get(s, s.title() if s else "Other")


def load_config() -> dict:
    with open(HOLDINGS_FILE) as f:
        return json.load(f)


def _fund_holdings(ticker: str) -> dict | None:
    """Top holdings {underlying: weight} for an ETF, or None if not a fund."""
    if ticker in _fund_cache:
        return _fund_cache[ticker]
    try:
        th = yf.Ticker(ticker).funds_data.top_holdings
        d = {str(idx): float(row["Holding Percent"]) for idx, row in th.iterrows()}
        _fund_cache[ticker] = d or None
    except Exception:
        _fund_cache[ticker] = None
    return _fund_cache[ticker]


def _fund_sectors(ticker: str) -> dict | None:
    """ETF sector weightings {readable_sector: weight}, or None if not a fund."""
    if ticker in _fund_sector_cache:
        return _fund_sector_cache[ticker]
    try:
        sw = yf.Ticker(ticker).funds_data.sector_weightings
        d = {_norm_sector(k): float(v) for k, v in sw.items()} if sw else None
    except Exception:
        d = None
    _fund_sector_cache[ticker] = d
    return d


def _stock_sector(ticker: str) -> str:
    """Best-effort sector for a single stock."""
    if ticker in _stock_sector_cache:
        return _stock_sector_cache[ticker]
    try:
        s = _norm_sector(yf.Ticker(ticker).info.get("sector", "") or "")
    except Exception:
        s = "Other"
    _stock_sector_cache[ticker] = s
    return s


# Weinstein-style trend STAGE — a RISK/CONTEXT descriptor, not a buy signal.
# We backtested "buy the uptrend / buy the recovery": neither beat just holding
# (continuation t≈0; recovery slightly NEGATIVE short-term). So a stage tells you
# whether a stock is HEALTHY or BROKEN — it does NOT predict above-average returns.
def _trend_stage(close: pd.Series) -> dict:
    price = float(close.iloc[-1])
    sma50 = float(close.iloc[-50:].mean())
    sma200 = float(close.iloc[-200:].mean())
    sma200_prev = float(close.iloc[-221:-21].mean())     # the 200-day ~1 month ago
    slope200 = sma200 / sma200_prev - 1
    above200, above50 = price > sma200, price > sma50
    rising200, falling200 = slope200 > 0.005, slope200 < -0.005

    if above200 and rising200:
        key, label, emoji = "stage2", "Uptrend", "🟢"
        note = ("Healthy advance — above a rising 200-day. The normal, lower-risk state. "
                "Context only: an uptrend does NOT predict above-average returns (tested).")
    elif above200:
        key, label, emoji = "stage3", "Topping", "🟡"
        note = ("Above its 200-day but the trend is flattening — momentum fading near the highs. "
                "A watch flag, not a sell trigger.")
    elif above50:
        key, label, emoji = "recovering", "Recovering", "🌤️"
        note = ("Below its 200-day but back above its 50-day — it has stopped being a falling knife. "
                "A safety milestone, NOT a buy signal (backtested: 'buy the recovery' doesn't beat holding).")
    elif falling200:
        key, label, emoji = "stage4", "Declining", "🔴"
        note = ("Below a falling 200-day and its 50-day — the higher-drawdown zone. "
                "Falling knife: hold to your stop or reduce, don't average down on hope.")
    else:
        key, label, emoji = "stage1", "Basing", "⚪"
        note = ("Below a flattening 200-day, not yet turning up — building a base. "
                "Wait for it to reclaim the 50-day before calling it a recovery.")
    return {"stage": key, "stage_label": label, "stage_emoji": emoji, "stage_note": note}


def _light(daily: pd.DataFrame) -> dict:
    """Cheap per-holding read in PLAIN ENGLISH: trend, sell target, stop, status."""
    out: dict = {}
    close = daily["close"]
    price = float(close.iloc[-1])

    # 200-day trend flag — the one backtested-robust RISK signal (it cut
    # drawdowns historically). Below the 200-day avg = the higher-drawdown zone.
    # The 200-day is only a meaningful trend line once the stock has traded long
    # enough that the average reflects a real trend, not a young IPO/spinoff ramp.
    # Need ~1.5y (≈400 bars) — a 200-day on a 1y-old stock (e.g. SNDK +247% above
    # its own average) is noise, so we don't flag or show it.
    if len(close) >= 400:
        sma200 = float(close.iloc[-200:].mean())
        out["below_200dma"] = bool(price < sma200)
        out["dist_200dma_pct"] = round((price / sma200 - 1) * 100, 1)
        out["sma200_price"] = round(sma200, 2)
        # The 200-day lags badly after a crash, so a stock can be recovering and
        # still sit below it. Use the faster 50-day to tell "recovering" (above
        # its 50-day = climbing back) from "still weak" (below it = falling knife).
        if out["below_200dma"]:
            sma50 = float(close.iloc[-50:].mean())
            out["recovering"] = bool(price > sma50)
        out.update(_trend_stage(close))   # Base/Uptrend/Topping/Declining — risk context
    elif len(close) >= 60:
        out["young_for_200d"] = True
    try:
        mtf = trends.multi_timeframe(daily)
        a = mtf["alignment"].lower()
        out["trend"] = "up" if "up" in a else "down" if ("down" in a or "bearish" in a) else "mixed"
    except Exception:
        out["trend"] = "mixed"
    try:
        out["rsi"] = round(float(indicators.rsi(daily["close"]).iloc[-1]), 0)
    except Exception:
        out["rsi"] = None
    try:
        pl = target.plan(daily)
        if pl.get("available"):
            out["weekly_tp_pct"] = pl["take_profit"]["ret_pct"]
            out["stop_pct"] = pl["stop"]["ret_pct"]
            out["take_profit_price"] = round(price * (1 + pl["take_profit"]["ret_pct"] / 100), 2)
            out["stop_price"] = round(price * (1 + pl["stop"]["ret_pct"] / 100), 2)
            out["prob_green"] = pl["prob_profit_intraweek"]
            out["vol_label"] = pl["vol_regime"]["label"]
    except Exception:
        pass

    # Plain-English one-liner anyone can read.
    trend_word = {"up": "in an uptrend", "down": "in a downtrend", "mixed": "moving sideways"}[out["trend"]]
    rsi = out.get("rsi")
    mom = ("overbought — it's run up fast and may pause/pull back" if rsi and rsi > 70
           else "oversold — it's been beaten down and may bounce" if rsi and rsi < 30
           else "with normal momentum")
    out["summary"] = f"{trend_word.capitalize()}, {mom}."

    # Action bucket — describes the stock's CURRENT STATE (not a prediction).
    if out["trend"] == "down":
        out["bucket"] = "review"          # 🔴 falling over months — review
    elif rsi is not None and rsi >= 70:
        out["bucket"] = "trim"            # 🟢 extended / overbought — could take profit
    elif out["trend"] == "up" and rsi is not None and rsi <= 45:
        out["bucket"] = "dip"             # 🟡 uptrend on sale — reasonable add-zone
    else:
        out["bucket"] = "hold"           # 🔵 steady — nothing to do
    return out


def _row(ticker: str, shares: float, avg_cost: float, analyze: bool) -> dict:
    try:
        daily = data.fetch_ohlcv(ticker, period="2y", interval="1d")
        price = round(float(daily["close"].iloc[-1]), 2)
    except Exception:
        return {"ticker": ticker, "shares": round(shares, 4), "avg_cost": avg_cost, "error": "no data"}
    value = shares * price
    row = {
        "ticker": ticker,
        "shares": round(shares, 4),
        "avg_cost": round(avg_cost, 2) if avg_cost else None,
        "price": price,
        "value": round(value, 2),
        "cost": round(shares * avg_cost, 2) if avg_cost else None,
        "gain_pct": round((price / avg_cost - 1) * 100, 2) if avg_cost else None,
        "is_fund": _fund_holdings(ticker) is not None,
    }
    if analyze:
        row.update(_light(daily))
    return row


def value_holdings(holdings: list[dict], analyze: bool = True) -> list[dict]:
    rows = [_row(h["ticker"], h["shares"], h.get("avg_cost"), analyze) for h in holdings]
    total = sum(r.get("value", 0) for r in rows)
    for r in rows:
        r["weight"] = round(r.get("value", 0) / total * 100, 1) if total else 0
    return sorted(rows, key=lambda r: r.get("value", 0), reverse=True)


def look_through(rows: list[dict], cash: float = 0.0) -> dict:
    """Resolve ETFs into constituents → TRUE effective single-name exposure.
    `cash` dilutes the weights so percentages are of the whole account."""
    exposure: dict[str, float] = {}
    sources: dict[str, set] = {}            # underlying -> {where it comes from}
    sector_exp: dict[str, float] = {}
    residual = 0.0
    total = sum(r.get("value", 0) for r in rows) + cash
    if total <= 0:
        return {"available": False}

    for r in rows:
        v = r.get("value", 0)
        if not v:
            continue
        t = r["ticker"]
        fh = _fund_holdings(t)
        if fh:
            covered = 0.0
            for u, w in fh.items():
                u = "GOOGL" if u == "GOOG" else u  # merge share classes
                exposure[u] = exposure.get(u, 0) + v * w
                sources.setdefault(u, set()).add(t)
                covered += w
            residual += v * max(0.0, 1 - covered)
            # Sectors: distribute the fund's value across its sector weights.
            fs = _fund_sectors(t)
            if fs:
                tot_w = sum(fs.values()) or 1.0
                for sec, w in fs.items():
                    sector_exp[sec] = sector_exp.get(sec, 0) + v * (w / tot_w)
            else:
                sector_exp["Diversified fund"] = sector_exp.get("Diversified fund", 0) + v
        else:
            exposure[t] = exposure.get(t, 0) + v
            sources.setdefault(t, set()).add(t)
            sector_exp[_stock_sector(t)] = sector_exp.get(_stock_sector(t), 0) + v

    weights = np.array(list(exposure.values())) / total
    hhi = float(np.sum(weights ** 2))
    eff = sorted(exposure.items(), key=lambda kv: -kv[1])
    mega_pct = sum(val for u, val in exposure.items() if u in MEGACAP8) / total * 100
    top3 = sum(val for _, val in eff[:3]) / total * 100

    effective = []
    for u, val in eff[:12]:
        src = sources.get(u, set())
        effective.append({
            "ticker": u, "value": round(val, 2), "weight": round(val / total * 100, 1),
            "places": len(src),                          # held in how many holdings (direct + via ETFs)
            "stacked": bool(u in src and len(src) > 1),   # owned directly AND inside an ETF
        })

    sectors = sorted(
        ({"sector": s, "weight": round(val / total * 100, 1)} for s, val in sector_exp.items()),
        key=lambda x: -x["weight"],
    )
    top_name = effective[0] if effective else None
    flags = []
    if top_name and top_name["weight"] > 10:
        flags.append(f"{top_name['ticker']} is {top_name['weight']}% of everything (over the 10% single-name rule of thumb)")
    if sectors and sectors[0]["weight"] > 40:
        flags.append(f"{sectors[0]['sector']} is {sectors[0]['weight']}% of your money (over the 40% one-sector guide)")

    return {
        "available": True,
        "total": round(total, 2),
        "cash_pct": round(cash / total * 100, 1),
        "effective": effective,
        "sectors": sectors,
        "flags": flags,
        "residual_diversified_pct": round(residual / total * 100, 1),
        "concentration": {
            "hhi": round(hhi, 3),
            "effective_n": round(1 / hhi, 1) if hhi > 0 else None,
            "top3_pct": round(top3, 1),
            "megacap8_pct": round(mega_pct, 1),
        },
        "note": "ETF look-through covers each fund's TOP-10 holdings (rest is the 'diversified remainder'); "
                "effective single-name weights are a floor, not exact.",
    }


# --- Fund expense ratios (percent units; fallback for what yfinance omits) ---
_FEE_FALLBACK = {"SPYM": 0.03, "VOO": 0.03, "QQQ": 0.20, "SPY": 0.0945, "DIA": 0.16,
                 "IVV": 0.03, "VTI": 0.03, "SPLG": 0.02}


def _expense_ratio(ticker: str) -> float | None:
    """Fund expense ratio in PERCENT (0.03 = 0.03%), or None for a plain stock."""
    if _fund_holdings(ticker) is None:
        return None
    try:
        er = yf.Ticker(ticker).info.get("netExpenseRatio")
    except Exception:
        er = None
    return er if er is not None else _FEE_FALLBACK.get(ticker)


def portfolio_fees(rows: list[dict], invested: float) -> dict:
    """Blended fund fee + the compounded dollar drag — and what a 1% fund would cost."""
    if invested <= 0:
        return {"available": False}
    blended = 0.0
    funds = []
    for r in rows:
        v = r.get("value", 0)
        if not v:
            continue
        er = _expense_ratio(r["ticker"])
        if er is not None:
            blended += (v / invested) * er
            funds.append({"ticker": r["ticker"], "fee_pct": round(er, 3),
                          "annual_cost": round(v * er / 100, 2)})

    def drag(years, fee_pct, g=0.07):
        f = fee_pct / 100.0
        return invested * ((1 + g) ** years - (1 + g - f) ** years)

    return {
        "available": True,
        "blended_fee_pct": round(blended, 3),
        "annual_cost": round(invested * blended / 100, 2),
        "drag_10y": round(drag(10, blended)),
        "drag_30y": round(drag(30, blended)),
        "vs_1pct_30y": round(drag(30, 1.0)),
        "funds": sorted(funds, key=lambda f: -f["annual_cost"]),
        "assumption": "Assumes 7%/yr growth on today's balance, no new deposits — illustrative, not a forecast.",
    }


def _portfolio_returns(rows: list[dict], period: str = "5y"):
    """Value-weighted daily portfolio return series + index.

    Holdings with too-short history (e.g. a recent spinoff) are dropped so they
    don't truncate the whole window; weights are renormalized over the rest.
    """
    val = {r["ticker"]: r.get("value", 0) for r in rows if r.get("value")}
    series = {}
    for t in val:
        try:
            series[t] = data.fetch_ohlcv(t, period=period, interval="1d")["close"].pct_change()
        except Exception:
            continue
    if not series:
        return None, None
    df = pd.DataFrame(series)
    n = len(df)
    keep = [c for c in df.columns if df[c].notna().sum() >= 0.8 * n]  # long-history only
    if not keep:
        return None, None
    df = df[keep].dropna()
    total = sum(val[c] for c in keep)
    w = np.array([val[c] for c in keep]) / total
    return df.to_numpy() @ w, df.index


def portfolio_weekly_vol(rows: list[dict]) -> dict:
    """Realized portfolio weekly vol from value-weighted returns (captures correlations)."""
    port_ret, _ = _portfolio_returns(rows, period="2y")
    if port_ret is None:
        return {"available": False}
    daily_vol = float(np.std(port_ret[-252:], ddof=1))
    return {
        "available": True,
        "weekly_vol_pct": round(daily_vol * np.sqrt(5) * 100, 2),
        "annual_vol_pct": round(daily_vol * np.sqrt(252) * 100, 1),
        "typical_week_range_pct": round(1.96 * daily_vol * np.sqrt(5) * 100, 2),
    }


def portfolio_drawdown(rows: list[dict], invested: float, cash: float) -> dict:
    """Worst peak-to-trough drop your CURRENT mix would have had, in dollars + recovery time.
    Backward-looking history, NOT a forecast."""
    port_ret, idx = _portfolio_returns(rows, period="5y")
    if port_ret is None or len(port_ret) < 60:
        return {"available": False}
    eq = np.cumprod(1 + port_ret)
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1
    trough = int(np.argmin(dd))
    maxdd = float(dd[trough] * 100)
    peak_i = int(np.argmax(eq[: trough + 1]))
    # recovery: first day after the trough that regains the prior peak
    rec = next((i for i in range(trough + 1, len(eq)) if eq[i] >= eq[peak_i]), None)
    months = round((idx[rec] - idx[trough]).days / 30.0, 1) if rec else None
    trough_invested = round(invested * (1 + maxdd / 100), 2)
    return {
        "available": True,
        "max_drawdown_pct": round(maxdd, 1),
        "years": round(len(eq) / 252, 1),
        "peak_date": idx[peak_i].strftime("%b %Y"),
        "trough_date": idx[trough].strftime("%b %Y"),
        "recovery_months": months,
        "stocks_now": round(invested, 2),
        "stocks_at_trough": trough_invested,
        "total_at_trough": round(trough_invested + cash, 2),
    }


def analyze_portfolio(holdings: list[dict] | None = None, cash: float | None = None,
                      analyze: bool = True) -> dict:
    cfg = load_config()
    holdings = holdings if holdings is not None else cfg["holdings"]
    cash = float(cfg.get("cash", 0.0)) if cash is None else float(cash or 0.0)
    rows = value_holdings(holdings, analyze=analyze)
    watch = value_holdings([{"ticker": t, "shares": 0, "avg_cost": None} for t in cfg.get("watchlist", [])],
                           analyze=analyze)

    invested = sum(r.get("value", 0) for r in rows)
    invested_cost = sum(r.get("cost", 0) or 0 for r in rows)
    total_value = round(invested + cash, 2)
    # Re-weight each holding against the WHOLE account (incl. cash).
    for r in rows:
        r["weight"] = round(r.get("value", 0) / total_value * 100, 1) if total_value else 0

    return {
        "holdings": rows,
        "watchlist": watch,
        "cash": round(cash, 2),
        "summary": {
            "total_value": total_value,
            "invested": round(invested, 2),
            "cash": round(cash, 2),
            "total_cost": round(invested_cost + cash, 2),
            "total_gain": round(invested - invested_cost, 2),
            "total_gain_pct": round((invested / invested_cost - 1) * 100, 2) if invested_cost else None,
            "positions": len([r for r in rows if r.get("value")]),
        },
        "look_through": look_through(rows, cash),
        "risk": portfolio_weekly_vol(rows),
        "fees": portfolio_fees(rows, invested),
        "drawdown": portfolio_drawdown(rows, invested, cash),
        "disclaimer": "Descriptive analytics — concentration & risk measurement, not return predictions or advice.",
    }
