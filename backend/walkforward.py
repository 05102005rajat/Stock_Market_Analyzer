"""Walk-forward, point-in-time evaluation of the forecast and the buy/sell signal.

At each historical date t we use ONLY data up to t (no lookahead — every
sub-analysis, including the candlestick-edge backtest, is recomputed on the
truncated series), then compare the prediction to what actually happened after t.
Results are reported against dumb baselines so we can see real edge, if any.

Run:  ./venv/bin/python walkforward.py
"""
import sys
import time

import numpy as np
import pandas as pd

from services import (
    backtest, candlesticks, forecast, indicators,
    minervini, patterns, signal as signal_engine, trends, volume,
)

TICKERS = ["AAPL", "SPY"]
LOOKBACK = 120          # how many recent trading days to evaluate over
FC_HORIZON = 5          # forecast this many days ahead
SIGNAL_EVERY = 8        # sample the (expensive) signal every N days
SIGNAL_HORIZONS = (5, 20)


def _p(msg):
    print(msg, flush=True)


def compute_signal(daily_t: pd.DataFrame) -> dict:
    """Full composite signal using only data up to the cutoff (point-in-time)."""
    chart = daily_t.tail(260)
    ind = indicators.compute_all(chart)
    pat = patterns.analyze(chart)
    ctx = {
        "trend": pat["trend"],
        "multiTimeframe": trends.multi_timeframe(daily_t),
        "latest": ind["latest"],
        "levels": pat["levels"],
        "candlesticks": candlesticks.detect(chart),
        "patterns": pat["patterns"],
        "volume": volume.analyze(chart),
        "minervini": minervini.trend_template(daily_t),
        "backtest": backtest.run(daily_t),   # edge recomputed point-in-time
    }
    return signal_engine.score(ctx)


def eval_forecast(full: pd.DataFrame):
    close = full["close"].to_numpy(float)
    n = len(full)
    start = max(260, n - LOOKBACK)
    acc = {h: {"model_ae": [], "naive_ae": [], "model_dir": [], "up": [], "in_band": []}
           for h in (1, FC_HORIZON)}

    total = n - FC_HORIZON - start
    t0 = time.time()
    for k, ti in enumerate(range(start, n - FC_HORIZON)):
        if k % 25 == 0:
            _p(f"    forecast {k}/{total}  ({time.time() - t0:.0f}s)")
        fc = forecast.forecast(full.iloc[: ti + 1], horizon=FC_HORIZON, interval="1d")
        if not fc["available"]:
            continue
        last = close[ti]
        for h in (1, FC_HORIZON):
            p = fc["points"][h - 1]
            actual = close[ti + h]
            acc[h]["model_ae"].append(abs(p["value"] - actual) / actual)
            acc[h]["naive_ae"].append(abs(last - actual) / actual)   # persistence baseline
            acc[h]["model_dir"].append(np.sign(p["value"] - last) == np.sign(actual - last))
            acc[h]["up"].append(actual > last)                        # base rate / drift
            acc[h]["in_band"].append(p["lower"] <= actual <= p["upper"])
    return acc


def eval_signal(full: pd.DataFrame):
    close = full["close"].to_numpy(float)
    n = len(full)
    start = max(260, n - LOOKBACK)
    records = []
    pts = list(range(start, n - max(SIGNAL_HORIZONS), SIGNAL_EVERY))
    t0 = time.time()
    for k, ti in enumerate(pts):
        if k % 5 == 0:
            _p(f"    signal {k}/{len(pts)}  ({time.time() - t0:.0f}s)")
        sig = compute_signal(full.iloc[: ti + 1])
        last = close[ti]
        fwd = {h: close[ti + h] / last - 1.0 for h in SIGNAL_HORIZONS}
        records.append({"verdict": sig["verdict"], "score": sig["score"], "fwd": fwd})
    return records


def pct(x):
    return f"{x * 100:.1f}%"


def main():
    from services import data
    _p(f"Walk-forward eval — last {LOOKBACK} trading days, point-in-time (no lookahead)\n")

    for t in TICKERS:
        full = data.fetch_ohlcv(t, period="5y", interval="1d")
        _p(f"================ {t}  ({len(full)} bars) ================")

        # ---- Forecast vs naive persistence ----
        acc = eval_forecast(full)
        for h in (1, FC_HORIZON):
            a = acc[h]
            if not a["model_ae"]:
                continue
            m_mae, n_mae = np.mean(a["model_ae"]), np.mean(a["naive_ae"])
            dir_acc = np.mean(a["model_dir"])
            base = max(np.mean(a["up"]), 1 - np.mean(a["up"]))  # majority-class baseline
            cov = np.mean(a["in_band"])
            verdict = "BEATS naive" if m_mae < n_mae else "loses to naive"
            _p(f"  Forecast h={h}: MAE {pct(m_mae)} vs naive {pct(n_mae)} ({verdict}) | "
                  f"dir {pct(dir_acc)} vs base {pct(base)} | band cover {pct(cov)} (target 95%)")

        # ---- Signal: forward return by verdict bucket ----
        recs = eval_signal(full)
        for h in SIGNAL_HORIZONS:
            buckets = {}
            for v in ("BUY", "HOLD", "SELL"):
                rs = [r["fwd"][h] for r in recs if r["verdict"] == v]
                buckets[v] = (len(rs), np.mean(rs) if rs else float("nan"))
            uncond = np.mean([r["fwd"][h] for r in recs]) if recs else float("nan")
            # Does score rank forward returns? (Spearman-ish via correlation of ranks.)
            scores = np.array([r["score"] for r in recs])
            fwds = np.array([r["fwd"][h] for r in recs])
            corr = np.corrcoef(scores, fwds)[0, 1] if len(recs) > 2 else float("nan")
            line = " | ".join(
                f"{v}: n={buckets[v][0]} avg {pct(buckets[v][1])}" if buckets[v][0] else f"{v}: n=0"
                for v in ("BUY", "HOLD", "SELL")
            )
            _p(f"  Signal {h}d fwd → {line} | uncond {pct(uncond)} | score↔return corr {corr:+.2f}")
        _p("")

    _p("Read: forecast should BEAT naive on MAE and cover ~95% in-band; "
          "signal has edge if BUY avg > uncond > SELL avg and corr > 0.")


if __name__ == "__main__":
    main()
