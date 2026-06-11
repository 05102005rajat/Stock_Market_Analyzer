"""Point-in-time coverage + sharpness test of the forecast band, old vs new.

Compares three H-day bands at each historical day (calibration uses only past
outcomes), scoring coverage (target ~95%) and mean width (smaller = sharper):

  1. old:   close-to-close std × 1.96 (symmetric)          — the incumbent proxy
  2. scale: blend vol × 1.96 (symmetric)                   — isolates the scale fix
  3. new:   blend vol × empirical per-tail z (asymmetric)  — the shipped band

The win is criterion 3 holding ~95% coverage while being NARROWER than 1 at
matched coverage.

Run:  ./venv/bin/python -u band_backtest.py
"""
import numpy as np

from services import data, volatility as V

BASKET = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "KO", "JNJ", "XOM"]
HORIZON = 5
WINDOW = 20
CAL = 504  # trailing standardized-move window for the empirical z


def cc_series(close, window=20):
    r = np.diff(np.log(close))
    out = np.full(len(close), np.nan)
    for t in range(window, len(close)):
        out[t] = np.std(r[t - window:t], ddof=1)
    return out


def main():
    print(f"Band coverage/sharpness — {HORIZON}-day, point-in-time\n", flush=True)
    agg = {nm: {"cov": [], "w": []} for nm in ("old_cc_1.96", "blend_1.96", "blend_adaptive")}
    for t in BASKET:
        full = data.fetch_ohlcv(t, period="5y", interval="1d")
        logc = np.log(full["close"].to_numpy(float))
        n = len(full)
        cc = cc_series(full["close"].to_numpy(float), WINDOW)
        bl = V.blend_vol_series(full, WINDOW, 0.94)
        sqh = np.sqrt(HORIZON)
        # precompute standardized H-day moves u[s] for the empirical-z calibration
        u = np.full(n, np.nan)
        for s in range(n - HORIZON):
            if np.isfinite(bl[s]) and bl[s] > 0:
                u[s] = (logc[s + HORIZON] - logc[s]) / (bl[s] * sqh)
        for ti in range(WINDOW + 40, n - HORIZON):
            move = logc[ti + HORIZON] - logc[ti]
            # 1) old cc × 1.96
            if np.isfinite(cc[ti]):
                w = 1.96 * cc[ti] * sqh
                agg["old_cc_1.96"]["cov"].append(int(-w <= move <= w)); agg["old_cc_1.96"]["w"].append(2 * w)
            if np.isfinite(bl[ti]) and bl[ti] > 0:
                # 2) blend × 1.96
                w = 1.96 * bl[ti] * sqh
                agg["blend_1.96"]["cov"].append(int(-w <= move <= w)); agg["blend_1.96"]["w"].append(2 * w)
                # 3) blend × ADAPTIVE multiplier = this stock's own |z|95 over the
                # trailing window, floored at 1.96 and capped at 2.6 (measures each
                # stock's tail fatness, calibrated point-in-time on past outcomes).
                cal = u[max(0, ti - CAL - HORIZON): ti - HORIZON]
                cal = cal[np.isfinite(cal)]
                zmult = float(np.clip(np.quantile(np.abs(cal), 0.95), 1.96, 2.6)) if len(cal) >= 60 else 1.96
                w = zmult * bl[ti] * sqh
                agg["blend_adaptive"]["cov"].append(int(-w <= move <= w))
                agg["blend_adaptive"]["w"].append(2 * w)
        print(f"  scored {t}", flush=True)

    print(f"\n  {'band':16} {'coverage':>9} {'mean width':>11}")
    for nm, a in agg.items():
        print(f"  {nm:16} {np.mean(a['cov'])*100:8.1f}% {np.mean(a['w'])*100:10.2f}%")
    old = agg["old_cc_1.96"]; new = agg["blend_adaptive"]
    print(f"\nNew vs old: coverage {np.mean(new['cov'])*100:.1f}% vs {np.mean(old['cov'])*100:.1f}% | "
          f"width {np.mean(new['w'])*100:.2f}% vs {np.mean(old['w'])*100:.2f}% "
          f"({(1-np.mean(new['w'])/np.mean(old['w']))*100:+.1f}% width)")


if __name__ == "__main__":
    main()
