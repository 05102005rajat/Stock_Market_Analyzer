"""Buy-Zone Scanner — a DISCIPLINED ENTRY screen, not a winner predictor.

It ranks a fixed universe (your holdings + watchlist + important liquid names)
by a transparent "buy the dip in a quality uptrend" rule and attaches calibrated
entry / target / stop levels. It does NOT predict which will go up — we proved
direction is a coin flip. The honest value is: IF you want exposure to a name,
which ones are currently on sale within an uptrend, and at what price/odds.

The one weak empirical tilt we found (RSI mean-reversion) is gated behind a
trend + relative-strength quality filter so it surfaces leaders on pullbacks,
not falling knives.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services import candlesticks, data, dipsignal, indicators, portfolio, relative, target

# Curated important, liquid names to round out the user's own book.
IMPORTANT = ["AMD", "AVGO", "JPM", "V", "MA", "LLY", "UNH", "HD", "ORCL", "CRM", "PLTR"]
FUNDS = {"VOO", "QQQ", "SPYM", "SPY", "DIA", "IVV"}  # index funds: no single-name "dip" setup


def universe() -> list[str]:
    cfg = portfolio.load_config()
    tickers = [h["ticker"] for h in cfg["holdings"]] + cfg.get("watchlist", []) + IMPORTANT
    seen, out = set(), []
    for t in tickers:
        if t in FUNDS or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def setup_score(rsi: float, price: float, sma20: float, sma200: float,
                rs_excess: float, reversal: bool) -> tuple[float, bool]:
    """0–100 'buy-the-dip-in-an-uptrend' score. Gate: uptrend + outperforming."""
    gated = price > sma200 and rs_excess > 0
    if not gated or not np.isfinite(rsi):
        return 0.0, gated
    rsi_score = float(np.clip((55 - rsi) / 30, 0, 1))      # more oversold → higher
    pullback = float(np.clip((sma20 / price - 1) / 0.05, 0, 1))  # below 20-DMA → on sale
    score = 100 * (0.55 * rsi_score + 0.35 * pullback + 0.10) + (8 if reversal else 0)
    return float(min(score, 100)), gated


def _breakout(close: pd.Series, price: float, rsi: float, sma200: float) -> dict | None:
    """Breakout WATCH (NOT a buy edge). Tested on 10y/80 names: breakouts,
    fresh-breaks-from-a-base and retests ALL under-performed buy-hold. Pure
    level-watching so you can WAIT for an oversold pullback (the real edge)
    instead of chasing the rip. "In a zone for a month" = a rangebound base whose
    ceiling (R) it either just cleared ("broke") or is still coiling under."""
    base = close.iloc[-31:-6]                       # the ~month-long zone (5wk→1wk ago)
    if len(base) < 20:
        return None
    R, lo = float(base.max()), float(base.min())
    rangebound = (R - lo) / R <= 0.15               # a real base, not a trend
    broke = bool(rangebound and price > R and float(close.iloc[-6]) <= R)
    coiling = bool(rangebound and price <= R and (R - price) / R <= 0.04)
    if not (broke or coiling):
        return None
    return {
        "level": round(R, 2),
        "status": "broke" if broke else "coiling",
        "fresh": bool(broke and float(close.iloc[-2]) <= R),   # crossed in last ~2d
        "dist_pct": round((price / R - 1) * 100, 1),
        "overbought": bool(np.isfinite(rsi) and rsi >= 68),
        "overhead_200": bool(sma200 > price),                  # 200-day = next wall up
        "dist_200_pct": round((price / sma200 - 1) * 100, 1),
    }


def _row(ticker: str, spy: pd.DataFrame, horizon: int) -> dict | None:
    try:
        d = data.fetch_ohlcv(ticker, period="5y", interval="1d")  # 5y so the dip win-rate is robust
    except Exception:
        return None
    close = d["close"]
    if len(close) < 210:
        return None
    price = float(close.iloc[-1])
    sma20 = float(close.iloc[-20:].mean())
    sma200 = float(close.iloc[-200:].mean())
    rsi = float(indicators.rsi(close).iloc[-1])
    rs = relative.relative_strength(d, spy)
    rs_excess = rs["excess_pct"] if rs else -99.0
    recent = candlesticks.detect(d, lookback=4)
    reversal = any(s["bias"] == "bullish" for s in recent)
    score, gated = setup_score(rsi, price, sma20, sma200, rs_excess, reversal)

    res = _breakout(close, price, rsi, sma200)

    # Target/stop calibrated to the chosen holding horizon (longer = bigger).
    plan = target.plan(d, horizon=horizon)
    levels = plan if plan.get("available") else None
    weekly_vol = (levels["vol_regime"]["weekly_vol_pct"] / 100) if levels else 0.0
    dip = round(price * (1 - 0.5 * weekly_vol), 2)

    # The tested edge: replay the dip-buy rule on THIS stock for its live state +
    # own win-rate (active = oversold dip inside an uptrend = the alert that fires).
    dv = dipsignal.verdict(d)
    dh = dv.get("history") or {}
    return {
        "breakout": res,
        "dip_available": bool(dv.get("available")),
        "dip_active": bool(dv.get("active")),
        "dip_in_uptrend": bool(dv.get("in_uptrend")),
        "dip_rsi2": dv.get("rsi2"),
        "dip_win_pct": round(dh["win_rate"] * 100) if dh else None,
        "dip_n_trades": dh.get("n_trades"),
        "dip_plan": dv.get("plan"),
        "ticker": ticker,
        "price": round(price, 2),
        "setup_score": round(score, 1),
        "in_uptrend": bool(price > sma200),
        "outperforming": bool(rs_excess > 0),
        "rsi": round(rsi, 1),
        "rs_excess_pct": round(rs_excess, 2),
        "reversal_candle": bool(reversal),
        "buy_zone": [dip, round(price, 2)],
        "take_profit": levels["take_profit"]["price"] if levels else None,
        "take_profit_pct": levels["take_profit"]["ret_pct"] if levels else None,
        "stop": levels["stop"]["price"] if levels else None,
        "prob_green_week": levels["prob_profit_intraweek"] if levels else None,
        "vol_label": levels["vol_regime"]["label"] if levels else None,
    }


# UI horizon options → trading days.
HORIZONS = {"1w": 5, "2w": 10, "1m": 21}


def _dip_buckets(rows: list[dict]) -> dict:
    """Split the universe by live dip-buy state: firing now / waiting / edge-off."""
    active = sorted([r for r in rows if r.get("dip_active") and r.get("dip_plan")],
                    key=lambda r: -(r.get("dip_win_pct") or 0))
    waiting = sorted(
        [r for r in rows if r.get("dip_available") and r.get("dip_in_uptrend") and not r.get("dip_active")],
        key=lambda r: r.get("dip_rsi2") if r.get("dip_rsi2") is not None else 99)
    downtrend = [r["ticker"] for r in rows
                 if r.get("dip_available") and not r.get("dip_in_uptrend")]
    return {"active": active, "waiting": waiting, "downtrend": downtrend}


def scan(top_n: int = 5, horizon_key: str = "1m") -> dict:
    horizon = HORIZONS.get(horizon_key, 21)
    spy = data.fetch_ohlcv("SPY", period="5y", interval="1d")
    rows = [r for r in (_row(t, spy, horizon) for t in universe()) if r]
    rows.sort(key=lambda r: r["setup_score"], reverse=True)
    candidates = [r for r in rows if r["setup_score"] > 0]
    label = {"1w": "1 week", "2w": "2 weeks", "1m": "1 month"}.get(horizon_key, "1 month")

    # Breakout WATCH — levels only, NOT buy signals (tested null).
    watch = [r for r in rows if r.get("breakout")]
    broke = sorted([r for r in watch if r["breakout"]["status"] == "broke"],
                   key=lambda r: (not r["breakout"]["fresh"], -r["breakout"]["dist_pct"]))
    coiling = sorted([r for r in watch if r["breakout"]["status"] == "coiling"],
                     key=lambda r: r["breakout"]["dist_pct"], reverse=True)

    return {
        "dip_alerts": _dip_buckets(rows),
        "breakout_watch": {
            "broke": broke,
            "coiling": coiling,
            "note": ("WATCH ONLY — these are NOT buy signals. Backtested on 10y/80 names, "
                     "EVERY breakout form under-performed simply holding — fresh-from-base, "
                     "retests, AND volume-confirmed / tight-base VCP setups (the VCP was the "
                     "worst, +1.6% vs +6%/3mo). Use this to know your levels and to WAIT for "
                     "an oversold pullback (your one tested edge), not to chase a break."),
        },
        "generated_for": "buy-zone setups (entry discipline, NOT a return prediction)",
        "horizon_key": horizon_key,
        "horizon_label": label,
        "top": candidates[:top_n],
        "all": rows,
        "disclaimer": (
            f"Targets are calibrated to a ~{label} hold — the level price reached ~2 of 3 times "
            f"within {label} historically (bigger horizon = bigger target). These are rule-based "
            "ENTRY setups, NOT predictions they will rise; backtested, setup rank does not beat "
            "buy-and-hold on direction. Use them to time entries on names you already want."
        ),
    }
