"""Point-in-time evaluation of volatility estimators for the 5-day horizon.

Each estimator's per-bar forecast is computed ONCE per ticker as a point-in-time
series (bar t uses only data ≤ t), then scored against the realized next-5-day
outcome:

  * QLIKE  — proper, scale-invariant vol loss: RV/F - ln(RV/F) - 1 (lower=better).
  * rank   — Spearman corr of forecast vol vs realized |5-day return|.
  * coverage + sharpness — a ±1.96·σ̂·√5 log band; coverage ~0.95, then narrowest wins.

Run:  ./venv/bin/python -u vol_backtest.py
"""
import numpy as np
from scipy.stats import spearmanr

from services import data, volatility as V

BASKET = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "KO", "JNJ", "XOM"]
HORIZON = 5
WINDOW = 20


def cc_var_series(close, window=20):
    c = np.asarray(close, float)
    r = np.diff(np.log(c))
    out = np.full(len(c), np.nan)
    for t in range(window, len(c)):
        out[t] = np.var(r[t - window:t], ddof=1)
    return out


def yz_only(df):
    s = V.yz_var_series(df["open"].to_numpy(), df["high"].to_numpy(),
                        df["low"].to_numpy(), df["close"].to_numpy(), WINDOW)
    return s


def series_for(df):
    c = df["close"].to_numpy()
    ev = V.ewma_var_series(c, 0.94)
    return {
        "close_to_close": np.sqrt(cc_var_series(c, WINDOW)),
        "ewma": np.sqrt(ev),
        "yang_zhang": np.sqrt(yz_only(df)),
        "blend": V.blend_vol_series(df, WINDOW, 0.94),
    }


def main():
    print(f"Volatility estimator backtest — {HORIZON}-day horizon, point-in-time\n", flush=True)
    names = ["close_to_close", "ewma", "yang_zhang", "blend"]
    agg = {nm: {"qlike": [], "fvar": [], "rvar": [], "cover": [], "width": []} for nm in names}

    for t in BASKET:
        full = data.fetch_ohlcv(t, period="5y", interval="1d")
        logc = np.log(full["close"].to_numpy(float))
        n = len(full)
        ser = series_for(full)
        for ti in range(WINDOW + 30, n - HORIZON):
            daily_r = np.diff(logc[ti: ti + HORIZON + 1])
            rvar = float(np.sum(daily_r ** 2))
            move = float(logc[ti + HORIZON] - logc[ti])
            for nm in names:
                sig_d = ser[nm][ti]
                if not np.isfinite(sig_d) or sig_d <= 0:
                    continue
                fvar = (sig_d ** 2) * HORIZON
                ratio = rvar / fvar
                if np.isfinite(ratio) and ratio > 0:
                    agg[nm]["qlike"].append(ratio - np.log(ratio) - 1)
                agg[nm]["fvar"].append(sig_d)
                agg[nm]["rvar"].append(abs(move))
                sig_h = sig_d * np.sqrt(HORIZON)
                agg[nm]["cover"].append(int(abs(move) <= 1.96 * sig_h))
                agg[nm]["width"].append(2 * 1.96 * sig_h)
        print(f"  scored {t}", flush=True)

    print(f"\n  {'estimator':16} {'QLIKE':>8} {'rank':>7} {'coverage':>9} {'width':>8}")
    rows = []
    for nm in names:
        a = agg[nm]
        qlike = float(np.mean(a["qlike"]))
        rank = float(spearmanr(a["fvar"], a["rvar"]).correlation)
        cover = float(np.mean(a["cover"]))
        width = float(np.mean(a["width"]))
        rows.append((nm, qlike, rank, cover, width))
        print(f"  {nm:16} {qlike:8.4f} {rank:7.3f} {cover*100:8.1f}% {width*100:7.2f}%")

    best_q = min(rows, key=lambda r: r[1])
    print(f"\nBest QLIKE: {best_q[0]} ({best_q[1]:.4f}).")
    cc = next(r for r in rows if r[0] == "close_to_close")
    bl = next(r for r in rows if r[0] == "blend")
    print(f"blend vs close_to_close QLIKE: {bl[1]:.4f} vs {cc[1]:.4f} "
          f"({(1-bl[1]/cc[1])*100:+.1f}%); coverage {bl[3]*100:.1f}% vs {cc[3]*100:.1f}%")


if __name__ == "__main__":
    main()
