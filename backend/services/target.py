"""Weekly trade planner — targets & probabilities instead of direction.

Day-to-day direction is unpredictable (coin flip). But the DISTRIBUTION of how
far price travels within a week is stable and estimable from the stock's own
recent path. So rather than predict where it goes, we answer:

  * If you buy at today's close, how often (historically) was a profitable exit
    available within the next week?
  * What take-profit target gets reached in ~2/3 of weeks (a "safe" target)?
  * What stop would have been breached only ~1/3 of the time?

These come from the empirical distribution of the H-day maximum favorable /
adverse excursion (MFE/MAE) — calibrated to reality, not forecast. Educational,
not investment advice.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services import volatility


def plan(df: pd.DataFrame, horizon: int = 5, window: int = 252,
         sig_series: np.ndarray | None = None) -> dict:
    """Weekly trade plan: vol-standardized excursion SHAPE × current-regime SCALE.

    The *shape* of the standardized excursion distribution is stable and
    estimable over 252 windows; the *scale* (today's vol) is read from a fast
    blend estimator, so targets adapt to the regime in ~2 weeks while keeping
    the ~66% hit calibration. `sig_series` may be passed precomputed (backtests).
    """
    close = df["close"].to_numpy(dtype=float)
    high = df["high"].to_numpy(dtype=float)
    low = df["low"].to_numpy(dtype=float)
    n = len(close)
    if n < horizon + 80:
        return {"available": False, "reason": "Not enough history for a reliable plan."}

    if sig_series is None:
        sig_series = volatility.blend_vol_series(df)

    sqh = np.sqrt(horizon)
    lo = max(0, n - horizon - window)
    mfe_std, mae_std, mfe_raw, endret, sig5 = [], [], [], [], []
    for t in range(lo, n - horizon):
        sd = sig_series[t]
        if not np.isfinite(sd) or sd <= 0:
            continue
        s5 = sd * sqh
        entry_t = close[t]
        mfe = high[t + 1: t + 1 + horizon].max() / entry_t - 1.0
        mae = low[t + 1: t + 1 + horizon].min() / entry_t - 1.0
        mfe_std.append(mfe / s5)
        mae_std.append(mae / s5)
        mfe_raw.append(mfe)
        endret.append(close[t + horizon] / entry_t - 1.0)
        sig5.append(s5)

    if len(mfe_std) < 40:
        return {"available": False, "reason": "Not enough sample windows."}

    finite = sig_series[np.isfinite(sig_series)]
    if len(finite) == 0:
        return {"available": False, "reason": "Volatility unavailable."}
    sigma5_now_raw = float(finite[-1]) * sqh
    median_sig5 = float(np.median(sig5))
    # Guardrail: a single earnings print shouldn't blow up the target.
    sigma5_now = float(np.clip(sigma5_now_raw, 0.5 * median_sig5, 2.0 * median_sig5))

    entry = round(float(close[-1]), 2)

    def lvl(ret):
        return round(entry * (1 + ret), 2)

    tp_safe = float(np.quantile(mfe_std, 0.34)) * sigma5_now    # reached ~66%
    tp_stretch = float(np.quantile(mfe_std, 0.50)) * sigma5_now  # reached ~50%
    stop = float(np.quantile(mae_std, 0.34)) * sigma5_now        # breached ~33%

    vol_ratio = sigma5_now_raw / median_sig5 if median_sig5 else 1.0
    regime = ("elevated" if vol_ratio > 1.25 else "calm" if vol_ratio < 0.8 else "normal")

    return {
        "available": True,
        "horizon": horizon,
        "entry": entry,
        "prob_profit_intraweek": round(float(np.mean(np.array(mfe_raw) > 0)), 3),
        "prob_profit_at_close": round(float(np.mean(np.array(endret) > 0)), 3),
        "take_profit": {"ret_pct": round(tp_safe * 100, 2), "price": lvl(tp_safe), "hist_hit_rate": 0.66},
        "stretch_target": {"ret_pct": round(tp_stretch * 100, 2), "price": lvl(tp_stretch), "hist_hit_rate": 0.50},
        "stop": {"ret_pct": round(stop * 100, 2), "price": lvl(stop), "hist_breach_rate": 0.33},
        "vol_regime": {
            "ratio": round(float(vol_ratio), 2),
            "label": regime,
            "weekly_vol_pct": round(sigma5_now * 100, 2),
        },
        "sample_weeks": int(len(mfe_std)),
        "disclaimer": "Vol-scaled to the current regime; calibrated from this stock's path — a risk/reward framework, not a prediction.",
    }
