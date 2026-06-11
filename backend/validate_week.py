"""Out-of-sample check: train on data through a cutoff date, forecast the next
N business days, and compare to the actual closes the model never saw. Also
reports the technical posture as of the cutoff.

Usage:
  ./venv/bin/python validate_week.py [CUTOFF] [N_DAYS]
  e.g.  ./venv/bin/python validate_week.py 2026-05-15 5   # train thru Fri, test all of next week
Defaults to 2026-05-27 / 2 (this week's Wed -> Thu+Fri).
"""
import sys

import pandas as pd

from services import (
    backtest, candlesticks, forecast, indicators, minervini,
    patterns, relative, signal as signal_engine, trends, volume,
)

CUTOFF = pd.Timestamp(sys.argv[1]) if len(sys.argv) > 1 else pd.Timestamp("2026-05-27")
N_DAYS = int(sys.argv[2]) if len(sys.argv) > 2 else 2
TICKERS = ["AAPL", "MSFT", "NVDA", "SPY", "KO"]


def analyze_through(daily, bench, horizon):
    chart = daily.tail(260)
    ind = indicators.compute_all(chart)
    pat = patterns.analyze(chart)
    rs = relative.relative_strength(daily, bench)
    ctx = {
        "ticker": "X", "trend": pat["trend"], "multiTimeframe": trends.multi_timeframe(daily),
        "latest": ind["latest"], "levels": pat["levels"], "candlesticks": candlesticks.detect(chart),
        "patterns": pat["patterns"], "volume": volume.analyze(chart),
        "minervini": minervini.trend_template(daily, rs_excess=(rs["excess_pct"] if rs else None)),
        "backtest": backtest.run(daily), "relativeStrength": rs,
    }
    return signal_engine.score(ctx), forecast.forecast(chart, horizon=horizon, interval="1d")


def main():
    from services import data
    bench = data.fetch_ohlcv("SPY", period="5y", interval="1d")
    print(f"Out-of-sample test — trained THROUGH {CUTOFF.date()}, testing the next "
          f"{N_DAYS} trading day(s)\n")
    rows = []
    for t in TICKERS:
        full = data.fetch_ohlcv(t, period="5y", interval="1d")
        train = full[full.index <= CUTOFF]
        actual = full[full.index > CUTOFF].head(N_DAYS)
        if len(train) < 260 or len(actual) < N_DAYS:
            print(f"{t}: insufficient data, skipping")
            continue

        cut_close = float(train["close"].iloc[-1])
        sig, fc = analyze_through(train, bench, horizon=N_DAYS)
        preds = fc["points"]

        print(f"=== {t} ===")
        print(f"  Posture as of {CUTOFF.date()}: {sig['posture']} (score {sig['score']:+}, agree {sig['confidence']}%)")
        print(f"  Cutoff close: {cut_close:.2f}")
        for k in range(N_DAYS):
            a = float(actual['close'].iloc[k])
            day = actual.index[k].strftime("%a %m-%d")
            p = preds[k]
            err = (p['value'] - a) / a * 100
            pred_dir = "up" if p['value'] >= cut_close else "down"
            act_dir = "up" if a >= cut_close else "down"
            in_band = p['lower'] <= a <= p['upper']
            hit = "✓" if pred_dir == act_dir else "✗"
            star = "  ★MON" if actual.index[k].weekday() == 0 else ""
            print(f"  {day}: pred {p['value']:.2f} [{p['lower']:.2f},{p['upper']:.2f}] "
                  f"| actual {a:.2f} | err {err:+.2f}% | {pred_dir} vs {act_dir} {hit} "
                  f"| in band: {'yes' if in_band else 'no'}{star}")
            rows.append((hit == "✓", abs(err), in_band))
        last_actual = float(actual['close'].iloc[-1])
        print(f"  Week move: {(last_actual/cut_close-1)*100:+.2f}% vs posture {sig['posture']}\n")

    n = len(rows)
    if n:
        dir_hits = sum(1 for r in rows if r[0])
        band_hits = sum(1 for r in rows if r[2])
        mae = sum(r[1] for r in rows) / n
        print("=" * 60)
        print(f"AGGREGATE over {n} forecasts ({len(TICKERS)} tickers × {N_DAYS} days):")
        print(f"  Direction correct: {dir_hits}/{n} ({dir_hits/n*100:.0f}%)")
        print(f"  Actual inside 95% band: {band_hits}/{n} ({band_hits/n*100:.0f}%)")
        print(f"  Mean abs price error: {mae:.2f}%")


if __name__ == "__main__":
    main()
