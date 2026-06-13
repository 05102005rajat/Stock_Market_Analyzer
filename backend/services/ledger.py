"""Signal ledger — the integrity capstone.

Every directional call the app makes (resistance breakout, dip-buy, pattern
tilt, extension, gap, earnings run-up) gets logged here with a timestamp, the
predicted base rate, the regime at emission, and the entry price. A scheduled
job later prices each signal at 5 / 21 / 63 trading days and records the
realized return. Over months this builds the app's OWN live, out-of-sample
track record — the only evidence immune to backtest overfitting — plus a
calibration curve (did "81% break above" actually resolve ~81% live?).

This is what turns "no predictive edge found" from a disclaimer into a
measured, falsifiable claim. SQLite, zero dependencies, zero cost.

Schema (table `signals`):
  id, ts (ISO), ticker, signal_type, direction (up/down/neutral),
  predicted_p (0-1 or null), regime (calm/normal/stressed/null),
  entry_price, horizon_done (0/5/21/63 = furthest scored),
  ret_5, ret_21, ret_63, bench_5, bench_21, bench_63, note
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "signal_ledger.db")
HORIZONS = (5, 21, 63)


def _conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    with closing(_conn()) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                ticker TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                predicted_p REAL,
                regime TEXT,
                entry_price REAL NOT NULL,
                horizon_done INTEGER DEFAULT 0,
                ret_5 REAL, ret_21 REAL, ret_63 REAL,
                bench_5 REAL, bench_21 REAL, bench_63 REAL,
                note TEXT,
                UNIQUE(ts, ticker, signal_type)
            )"""
        )
        c.commit()


def log(ticker: str, signal_type: str, direction: str, entry_price: float,
        predicted_p: float | None = None, regime: str | None = None,
        note: str | None = None, ts: str | None = None) -> bool:
    """Record one signal. De-duplicated per (day, ticker, type) so polling
    doesn't spam the ledger. Returns True if a new row was inserted."""
    init()
    ts = ts or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with closing(_conn()) as c:
        try:
            c.execute(
                """INSERT INTO signals
                   (ts, ticker, signal_type, direction, predicted_p, regime, entry_price, note)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (ts, ticker.upper(), signal_type, direction, predicted_p, regime,
                 float(entry_price), note),
            )
            c.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # already logged this signal today


def log_from_analysis(ticker: str, payload: dict) -> list[str]:
    """Extract any directional signals from an /api/analyze payload and log
    them. Returns the list of signal_types newly logged."""
    price = None
    q = payload.get("quote") or {}
    if q.get("available"):
        price = q.get("price")
    if price is None:
        price = (payload.get("resistance") or {}).get("level")  # fallback ref
    if price is None:
        return []

    regime = None
    ext = payload.get("extension") or {}

    logged = []

    # Resistance: fresh breakout = an "up" call with a measured base rate.
    res = payload.get("resistance") or {}
    if res.get("available") and res.get("state") == "fresh_breakout":
        p = (res.get("ath_bucket") or {}).get("p_reach_ath_63d")
        if log(ticker, "resistance_breakout", "up", price, predicted_p=p, regime=regime,
               note=res.get("headline")):
            logged.append("resistance_breakout")

    # Dip signal: active oversold-in-uptrend = an "up" call.
    dip = payload.get("dipSignal") or {}
    if dip.get("available") and dip.get("active"):
        if log(ticker, "dip_buy", "up", price, regime=regime):
            logged.append("dip_buy")

    # Pattern tilt: only when it's not flat.
    pr = payload.get("patternRead") or {}
    if pr.get("available") and pr.get("direction") in ("BULLISH", "BEARISH"):
        d = "up" if pr["direction"] == "BULLISH" else "down"
        if log(ticker, "pattern_tilt", d, price, predicted_p=pr.get("p_up_10bar"),
               regime=regime, note=f"{pr.get('tilt_pp')}pp"):
            logged.append("pattern_tilt")

    # Earnings hot run-up: a "expectations pre-paid" caution = a "down" lean.
    earn = payload.get("earningsWatch") or {}
    if earn.get("available") and earn.get("hot_runup"):
        if log(ticker, "earnings_runup", "down", price, regime=regime, note=earn.get("note")):
            logged.append("earnings_runup")

    return logged


def _bdays_after(prices, start_ts: str, n: int):
    """Return (entry_price, future_price) n trading bars after start_ts using a
    pandas Series of closes indexed by date, or (None, None)."""
    import pandas as pd
    idx = prices.index
    start = pd.Timestamp(start_ts)
    after = prices[idx >= start]
    if len(after) < n + 1:
        return None, None
    return float(after.iloc[0]), float(after.iloc[n])


def evaluate(fetch_close, bench_ticker: str = "SPY") -> dict:
    """Score every signal whose horizons have elapsed. `fetch_close(tk)` returns
    a pandas Series of daily closes. Idempotent — only fills missing horizons."""
    init()
    import pandas as pd

    bench = None
    try:
        bench = fetch_close(bench_ticker)
    except Exception:
        pass

    updated = 0
    with closing(_conn()) as c:
        rows = c.execute("SELECT * FROM signals WHERE horizon_done < 63").fetchall()
        price_cache: dict[str, object] = {}
        for r in rows:
            tk = r["ticker"]
            try:
                px = price_cache.get(tk)
                if px is None:
                    px = price_cache[tk] = fetch_close(tk)
            except Exception:
                continue
            if px is None or len(px) == 0:
                continue
            done = r["horizon_done"]
            vals = {}
            for h in HORIZONS:
                if h <= done:
                    continue
                e, f = _bdays_after(px, r["ts"], h)
                if e is None:
                    continue
                vals[f"ret_{h}"] = f / e - 1
                if bench is not None:
                    be, bf = _bdays_after(bench, r["ts"], h)
                    if be is not None:
                        vals[f"bench_{h}"] = bf / be - 1
                vals["horizon_done"] = h
            if vals:
                sets = ", ".join(f"{k}=?" for k in vals)
                c.execute(f"UPDATE signals SET {sets} WHERE id=?",
                          (*vals.values(), r["id"]))
                updated += 1
        c.commit()
    return {"evaluated": updated}


def calibration(min_n: int = 5) -> dict:
    """Predicted vs realized: for signals that carried a predicted probability,
    bucket by predicted decile and report realized up-rate. Also per-type
    summary stats (hit rate vs benchmark)."""
    init()
    import numpy as np

    with closing(_conn()) as c:
        rows = [dict(r) for r in c.execute(
            "SELECT * FROM signals WHERE horizon_done >= 21").fetchall()]

    if not rows:
        return {"available": False, "n": 0,
                "message": "No signals have reached the 21-day horizon yet. The ledger "
                           "is logging; check back after signals mature."}

    # Per-type: realized 21d return, and edge vs benchmark.
    by_type: dict[str, list] = {}
    for r in rows:
        by_type.setdefault(r["signal_type"], []).append(r)
    type_stats = []
    for t, rs in sorted(by_type.items()):
        rets = [x["ret_21"] for x in rs if x["ret_21"] is not None]
        # direction-adjust: for "down" signals, a profitable call is a fall
        dir_rets = [
            (x["ret_21"] if x["direction"] != "down" else -x["ret_21"])
            for x in rs if x["ret_21"] is not None
        ]
        edges = [
            (x["ret_21"] - (x["bench_21"] or 0)) * (1 if x["direction"] != "down" else -1)
            for x in rs if x["ret_21"] is not None
        ]
        if not dir_rets:
            continue
        type_stats.append({
            "signal_type": t,
            "n": len(dir_rets),
            "win_rate": round(100 * float(np.mean([d > 0 for d in dir_rets])), 0),
            "avg_dir_return_21d": round(100 * float(np.mean(dir_rets)), 2),
            "avg_edge_vs_spy_21d": round(100 * float(np.mean(edges)), 2),
        })

    # Calibration curve for probability-bearing signals.
    probs = [(r["predicted_p"], r["ret_21"]) for r in rows
             if r["predicted_p"] is not None and r["ret_21"] is not None]
    curve = []
    if probs:
        arr = np.array(probs)
        for lo in (0.0, 0.5, 0.6, 0.7, 0.8):
            hi = lo + (0.5 if lo == 0.0 else 0.1)
            m = (arr[:, 0] >= lo) & (arr[:, 0] < (hi if hi < 0.9 else 1.01))
            if m.sum() >= min_n:
                curve.append({
                    "predicted_band": f"{int(lo*100)}-{int(min(hi,1)*100)}%",
                    "n": int(m.sum()),
                    "realized_up_rate": round(100 * float((arr[m, 1] > 0).mean()), 0),
                })

    return {
        "available": True,
        "n_total": len(rows),
        "type_stats": type_stats,
        "calibration_curve": curve,
        "note": (
            "Live out-of-sample track record built from the app's own signals. "
            "This is the honest scoreboard — if a signal's realized edge vs SPY "
            "is ~0, it is descriptive, not predictive."
        ),
    }


def recent(limit: int = 50) -> list[dict]:
    init()
    with closing(_conn()) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM signals ORDER BY ts DESC, id DESC LIMIT ?", (limit,)).fetchall()]
