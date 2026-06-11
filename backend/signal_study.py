"""Multi-ticker, multi-regime study of the signal's components.

Point-in-time across a basket over 5y (includes the 2022 bear, so the signal
actually produces SELLs). For each sampled day we record every component value
and the realized forward returns. Then:
  * which components correlate with forward returns (edge diagnosis),
  * forward return by verdict bucket,
  * a walk-forward logistic fit (train early years → test late) whose learned
    weights become evidence-based replacements for the hand-set ones,
  * comparison vs buy-and-hold.

Run:  ./venv/bin/python -u signal_study.py
"""
import json
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from services import (
    backtest, candlesticks, data, indicators, minervini,
    patterns, relative, signal as signal_engine, trends, volume,
)

BASKET = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM",
          "XOM", "KO", "PG", "JNJ", "WMT", "AMD", "QQQ"]
SAMPLE_EVERY = 3
HORIZONS = (5, 20, 60)
SPLIT = pd.Timestamp("2024-09-01")  # train < split, test >= split (walk-forward)
COMPONENTS = ["Trend", "Multi-timeframe", "Regime (50/200 MA)", "RSI", "MACD",
              "Minervini", "Candlesticks (edge-weighted)", "Volume",
              "Chart patterns", "Relative strength"]


def _p(m):
    print(m, flush=True)


def compute_signal(daily_t, bench_full):
    chart = daily_t.tail(260)
    ind = indicators.compute_all(chart)
    pat = patterns.analyze(chart)
    rs = relative.relative_strength(daily_t, bench_full)
    ctx = {
        "trend": pat["trend"], "multiTimeframe": trends.multi_timeframe(daily_t),
        "latest": ind["latest"], "levels": pat["levels"],
        "candlesticks": candlesticks.detect(chart), "patterns": pat["patterns"],
        "volume": volume.analyze(chart),
        "minervini": minervini.trend_template(daily_t, rs_excess=(rs["excess_pct"] if rs else None)),
        "backtest": backtest.run(daily_t), "relativeStrength": rs,
    }
    return signal_engine.score(ctx)


def collect():
    bench = data.fetch_ohlcv("SPY", period="5y", interval="1d")
    rows = []
    for t in BASKET:
        try:
            full = data.fetch_ohlcv(t, period="5y", interval="1d")
        except Exception as e:
            _p(f"  {t}: fetch failed ({e})")
            continue
        close = full["close"].to_numpy(float)
        n = len(full)
        pts = list(range(260, n - max(HORIZONS), SAMPLE_EVERY))
        t0 = time.time()
        for k, ti in enumerate(pts):
            sig = compute_signal(full.iloc[: ti + 1], bench)
            comp = {c["name"]: c["value"] for c in sig["components"]}
            row = {name: comp.get(name, 0.0) for name in COMPONENTS}
            row.update({
                "ticker": t, "date": full.index[ti], "score": sig["score"], "verdict": sig["verdict"],
                **{f"fwd{h}": close[ti + h] / close[ti] - 1.0 for h in HORIZONS},
            })
            rows.append(row)
        _p(f"  {t}: {len(pts)} samples ({time.time() - t0:.0f}s)")
    return pd.DataFrame(rows)


def analyze(df):
    _p(f"\nCollected {len(df)} samples across {df['ticker'].nunique()} tickers, "
       f"{df['date'].min().date()}…{df['date'].max().date()}")
    _p(f"Verdict mix: " + ", ".join(f"{v}={int((df['verdict'] == v).sum())}" for v in ("BUY", "HOLD", "SELL")))

    # --- Per-component correlation with forward returns ---
    _p("\nComponent → forward-return correlation (edge diagnosis):")
    _p(f"  {'component':28} {'corr5':>8} {'corr20':>8} {'corr60':>8}")
    for c in COMPONENTS:
        cs = [f"{df[c].corr(df[f'fwd{h}']):+.3f}" for h in HORIZONS]
        _p(f"  {c:28} {cs[0]:>8} {cs[1]:>8} {cs[2]:>8}")

    # --- Current composite score vs forward returns ---
    _p("\nCurrent hand-weighted score → forward-return correlation:")
    for h in HORIZONS:
        _p(f"  {h}d: corr {df['score'].corr(df[f'fwd{h}']):+.3f}")

    # --- Forward return by verdict bucket (20d) ---
    _p("\nForward 20d return by verdict (current signal):")
    for v in ("BUY", "HOLD", "SELL"):
        sub = df[df["verdict"] == v]["fwd20"]
        if len(sub):
            _p(f"  {v}: n={len(sub)} mean {sub.mean() * 100:+.2f}% median {sub.median() * 100:+.2f}%")
    _p(f"  buy-and-hold (all): mean {df['fwd20'].mean() * 100:+.2f}%")

    # --- Walk-forward logistic fit (target: 20d forward return > 0) ---
    # Purge a 20-trading-day (~28 calendar) embargo before SPLIT: the fwd20 label
    # of rows just before SPLIT is realized AFTER it, so without this gap their
    # outcomes leak into the test window.
    embargo = pd.Timedelta(days=28)
    train = df[df["date"] < SPLIT - embargo]
    test = df[df["date"] >= SPLIT]
    _p(f"\nWalk-forward fit — train {len(train)} (<{SPLIT.date()}), test {len(test)} (>=):")
    if len(train) > 50 and len(test) > 20:
        X_tr, y_tr = train[COMPONENTS].to_numpy(), (train["fwd20"] > 0).to_numpy().astype(int)
        X_te, y_te = test[COMPONENTS].to_numpy(), (test["fwd20"] > 0).to_numpy().astype(int)
        sc = StandardScaler().fit(X_tr)
        clf = LogisticRegression(C=0.5, max_iter=1000).fit(sc.transform(X_tr), y_tr)
        prob = clf.predict_proba(sc.transform(X_te))[:, 1]
        base = max(y_te.mean(), 1 - y_te.mean())
        acc = ((prob > 0.5).astype(int) == y_te).mean()
        learned_corr = np.corrcoef(prob, test["fwd20"])[0, 1]
        cur_corr = test["score"].corr(test["fwd20"])
        _p(f"  test base-rate {base:.3f} | learned acc {acc:.3f} | "
           f"learned prob↔ret corr {learned_corr:+.3f} vs current-score corr {cur_corr:+.3f}")
        # Map standardized coefficients back to interpretable per-component weights.
        weights = dict(zip(COMPONENTS, (clf.coef_[0] / sc.scale_).round(3).tolist()))
        _p("  Learned weights (sign = helpful direction):")
        for c, w in sorted(weights.items(), key=lambda kv: -abs(kv[1])):
            _p(f"    {c:28} {w:+.3f}")
        json.dump({"weights": weights, "intercept": float(clf.intercept_[0])},
                  open("learned_weights.json", "w"), indent=2)
        _p("  -> saved learned_weights.json")
    else:
        _p("  insufficient train/test split")


def main():
    _p("Signal component study — point-in-time, 5y, multi-regime\n")
    df = collect()
    df.to_csv("signal_study.csv", index=False)
    analyze(df)


if __name__ == "__main__":
    main()
