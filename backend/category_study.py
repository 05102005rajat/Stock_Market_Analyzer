"""Do volatility dynamics differ by STOCK CATEGORY enough to warrant
category-specific logic? Point-in-time across categories, measuring:

  * vol level (already auto-handled by the blend's scaling),
  * excess kurtosis of the standardized 5-day move (fat tails → wider multiplier),
  * the band multiplier each category actually needs for 95% coverage,
  * the best vol estimator per category by QLIKE.

If the multiplier / best-estimator is STABLE within a category but DIFFERS across
categories, category-aware (or characteristic-adaptive) logic is justified.

Run:  ./venv/bin/python -u category_study.py
"""
import numpy as np
from scipy.stats import kurtosis

from services import data, volatility as V

CATEGORIES = {
    "mega_tech": ["AAPL", "MSFT", "GOOGL", "AMZN"],
    "high_vol_growth": ["NVDA", "TSLA", "AMD", "META"],
    "low_vol_defensive": ["KO", "JNJ", "PG", "WMT"],
    "index_etf": ["SPY", "QQQ", "DIA"],
    "cyclical_energy": ["XOM", "CVX", "CAT"],
}
HORIZON = 5
WINDOW = 20


def cc_series(close, w=20):
    r = np.diff(np.log(close))
    out = np.full(len(close), np.nan)
    for t in range(w, len(close)):
        out[t] = np.std(r[t - w:t], ddof=1)
    return out


def per_ticker(full):
    logc = np.log(full["close"].to_numpy(float))
    n = len(full)
    bl = V.blend_vol_series(full, WINDOW)
    # WINDOW returns (not WINDOW prices -> WINDOW-1 returns) to match the
    # reference cc estimator; include the most recent return r[t-1].
    r = np.diff(logc)
    cc = np.sqrt(np.array([np.var(r[t - WINDOW:t], ddof=1) if t >= WINDOW else np.nan
                           for t in range(n)]))
    ev = np.sqrt(V.ewma_var_series(full["close"].to_numpy(float)))
    yz = np.sqrt(V.yz_var_series(full["open"].to_numpy(), full["high"].to_numpy(),
                                 full["low"].to_numpy(), full["close"].to_numpy(), WINDOW))
    sqh = np.sqrt(HORIZON)
    z, qrows = [], {nm: [] for nm in ("blend", "cc", "ewma", "yz")}
    sers = {"blend": bl, "cc": cc, "ewma": ev, "yz": yz}
    daily_vol = []
    for t in range(WINDOW + 40, n - HORIZON):
        move = logc[t + HORIZON] - logc[t]
        rv = np.sum(np.diff(logc[t:t + HORIZON + 1]) ** 2)
        if np.isfinite(bl[t]) and bl[t] > 0:
            z.append(move / (bl[t] * sqh))
            daily_vol.append(bl[t])
        for nm, ser in sers.items():
            s = ser[t]
            if np.isfinite(s) and s > 0 and rv > 0:
                ratio = rv / (s * s * HORIZON)
                qrows[nm].append(ratio - np.log(ratio) - 1)
    return np.array(z), {nm: np.array(v) for nm, v in qrows.items()}, np.array(daily_vol)


def main():
    print("Category vol study — point-in-time, 5-day standardized moves\n", flush=True)
    print(f"  {'category':18} {'dailyvol':>8} {'kurtosis':>9} {'cov±1.96':>9} {'z95':>6}  best-QLIKE")
    summary = {}
    for cat, tickers in CATEGORIES.items():
        zs, qs, vols = [], {nm: [] for nm in ("blend", "cc", "ewma", "yz")}, []
        for t in tickers:
            try:
                full = data.fetch_ohlcv(t, period="5y", interval="1d")
            except Exception:
                continue
            z, q, dv = per_ticker(full)
            zs.append(z); vols.append(dv)
            for nm in qs:
                qs[nm].append(q[nm])
        if not zs:                       # every ticker in the category failed to fetch
            print(f"  {cat:18} no data — skipped")
            continue
        z = np.concatenate(zs)
        vols = np.concatenate(vols)
        qmean = {nm: float(np.mean(np.concatenate(v))) for nm, v in qs.items()}
        best = min(qmean, key=qmean.get)
        kurt = float(kurtosis(z))                       # excess kurtosis (0 = normal)
        cov = float(np.mean(np.abs(z) <= 1.96))          # coverage of a ±1.96 band
        z95 = float(np.quantile(np.abs(z), 0.95))        # multiplier needed for 95%
        summary[cat] = dict(dailyvol=float(np.mean(vols)), kurt=kurt, cov=cov, z95=z95, best=best, q=qmean)
        print(f"  {cat:18} {np.mean(vols)*100:7.2f}% {kurt:9.2f} {cov*100:8.1f}% {z95:6.2f}  "
              f"{best} ({qmean[best]:.3f})")

    print("\nInterpretation:")
    z95s = {c: s['z95'] for c, s in summary.items()}
    bests = {c: s['best'] for c, s in summary.items()}
    print(f"  z95 (multiplier for 95% coverage) ranges {min(z95s.values()):.2f}–{max(z95s.values()):.2f} "
          f"across categories (universal uses 1.96).")
    print(f"  best estimator per category: {bests}")
    spread = max(z95s.values()) - min(z95s.values())
    print(f"  -> multiplier spread = {spread:.2f}. "
          f"{'MATERIAL — category/char-adaptive multiplier is justified.' if spread > 0.25 else 'small — universal 1.96 is fine.'}")


if __name__ == "__main__":
    main()
