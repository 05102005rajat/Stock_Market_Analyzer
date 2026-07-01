"""Volatility estimators for the forecast bands and the weekly trade plan.

Each function takes point-in-time OHLC arrays (oldest→newest) and returns the
latest DAILY volatility estimate (a standard deviation of log-returns per bar).
Consumers scale to an H-day horizon by multiplying by sqrt(H).

Range/OHLC estimators (Parkinson, Garman-Klass, Rogers-Satchell, Yang-Zhang) use
the high/low and are far more efficient than close-to-close for estimating how
far price travels intraperiod — exactly what an intraweek MFE/MAE target needs.

Background: a close-to-close std throws away the intrabar path; the high-low
range carries ~5x the information per observation (Parkinson 1980), so these
estimators converge faster and adapt quicker to regime shifts.
"""
from __future__ import annotations

import numpy as np

_LN2 = np.log(2.0)


def _tail(a: np.ndarray, window: int) -> np.ndarray:
    return np.asarray(a, dtype=float)[-window:]


def close_to_close(close: np.ndarray, window: int = 20) -> float:
    """Classic std of daily log returns over the trailing window."""
    c = np.asarray(close, dtype=float)
    if len(c) < window + 1:
        return float("nan")
    r = np.diff(np.log(c))[-window:]
    return float(np.std(r, ddof=1))


def ewma(close: np.ndarray, lam: float = 0.94) -> float:
    """RiskMetrics EWMA daily vol — adaptive, parameter-light."""
    c = np.asarray(close, dtype=float)
    if len(c) < 30:
        return float("nan")
    r = np.diff(np.log(c))
    var = r[0] ** 2
    for x in r[1:]:
        var = lam * var + (1 - lam) * x * x
    return float(np.sqrt(var))


def parkinson(high: np.ndarray, low: np.ndarray, window: int = 20) -> float:
    """Parkinson (1980): high-low range estimator (assumes no drift, no gaps)."""
    h, l = _tail(high, window), _tail(low, window)
    if len(h) < window:
        return float("nan")
    hl = np.log(h / l) ** 2
    return float(np.sqrt(np.mean(hl) / (4 * _LN2)))


def garman_klass(o, h, l, c, window: int = 20) -> float:
    """Garman-Klass (1980): uses O/H/L/C, more efficient than Parkinson."""
    o, h, l, c = (_tail(x, window) for x in (o, h, l, c))
    if len(o) < window:
        return float("nan")
    term = 0.5 * np.log(h / l) ** 2 - (2 * _LN2 - 1) * np.log(c / o) ** 2
    return float(np.sqrt(np.mean(term)))


def rogers_satchell(o, h, l, c, window: int = 20) -> float:
    """Rogers-Satchell (1991): drift-independent (handles trending series)."""
    o, h, l, c = (_tail(x, window) for x in (o, h, l, c))
    if len(o) < window:
        return float("nan")
    term = np.log(h / c) * np.log(h / o) + np.log(l / c) * np.log(l / o)
    return float(np.sqrt(np.mean(term)))


def yang_zhang(o, h, l, c, window: int = 20) -> float:
    """Yang-Zhang (2000): combines overnight, open-to-close and Rogers-Satchell;
    handles both opening gaps and drift — the most accurate OHLC estimator."""
    o, h, l, c = (np.asarray(x, dtype=float) for x in (o, h, l, c))
    if len(o) < window + 1:
        return float("nan")
    o, h, l, c = o[-(window + 1):], h[-(window + 1):], l[-(window + 1):], c[-(window + 1):]
    n = window
    # Overnight (close-to-open) and open-to-close log returns.
    overnight = np.log(o[1:] / c[:-1])
    open_close = np.log(c[1:] / o[1:])
    sig2_on = np.var(overnight, ddof=1)
    sig2_oc = np.var(open_close, ddof=1)
    # Rogers-Satchell over the same bars.
    oo, hh, ll, cc = o[1:], h[1:], l[1:], c[1:]
    rs = np.mean(np.log(hh / cc) * np.log(hh / oo) + np.log(ll / cc) * np.log(ll / oo))
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    return float(np.sqrt(sig2_on + k * sig2_oc + (1 - k) * rs))


def ewma_var_series(close: np.ndarray, lam: float = 0.94) -> np.ndarray:
    """Point-in-time RiskMetrics EWMA variance per bar (bar t uses returns ≤ t)."""
    c = np.asarray(close, dtype=float)
    n = len(c)
    out = np.full(n, np.nan)
    if n < 2:
        return out
    r = np.diff(np.log(c))           # r[i] = return into bar i+1
    v = r[0] ** 2
    out[1] = v
    for i in range(1, len(r)):
        v = lam * v + (1 - lam) * r[i] ** 2
        out[i + 1] = v
    return out


def yz_var_series(o, h, l, c, window: int = 20) -> np.ndarray:
    """Point-in-time Yang-Zhang variance per bar (rolling window ending at t)."""
    o, h, l, c = (np.asarray(x, dtype=float) for x in (o, h, l, c))
    n = len(c)
    out = np.full(n, np.nan)
    for t in range(window, n):
        s = yang_zhang(o[: t + 1], h[: t + 1], l[: t + 1], c[: t + 1], window)
        out[t] = s * s if np.isfinite(s) else np.nan
    return out


def blend_vol_series(df, window: int = 20, lam: float = 0.94) -> np.ndarray:
    """Per-bar daily vol = sqrt(0.5*YangZhang² + 0.5*EWMA²), point-in-time.

    YZ supplies efficient OHLC-range + overnight-gap information; EWMA supplies
    fast regime reaction and a close-only floor when OHLC is degenerate.
    """
    c = df["close"].to_numpy(dtype=float)
    ev = ewma_var_series(c, lam)
    yv = yz_var_series(df["open"].to_numpy(), df["high"].to_numpy(),
                       df["low"].to_numpy(), c, window)
    yv_eff = np.where(np.isfinite(yv), yv, ev)        # fall back to EWMA when YZ unusable
    blend = np.sqrt(np.maximum(0.5 * yv_eff + 0.5 * ev, 1e-12))
    blend[~np.isfinite(ev)] = np.nan                  # keep warm-up NaNs
    return blend


def blend_vol(df, window: int = 20, lam: float = 0.94) -> float:
    """Latest point-in-time blended daily vol (scalar). NaN if uncomputable."""
    s = blend_vol_series(df, window, lam)
    s = s[np.isfinite(s)]
    return float(s[-1]) if len(s) else float("nan")


# Registry for the backtest harness.
ESTIMATORS = {
    "blend": lambda df, w: blend_vol(df, w),
    "close_to_close": lambda df, w: close_to_close(df["close"].to_numpy(), w),
    "ewma": lambda df, w: ewma(df["close"].to_numpy()),
    "parkinson": lambda df, w: parkinson(df["high"].to_numpy(), df["low"].to_numpy(), w),
    "garman_klass": lambda df, w: garman_klass(*(df[x].to_numpy() for x in ("open", "high", "low", "close")), w),
    "rogers_satchell": lambda df, w: rogers_satchell(*(df[x].to_numpy() for x in ("open", "high", "low", "close")), w),
    "yang_zhang": lambda df, w: yang_zhang(*(df[x].to_numpy() for x in ("open", "high", "low", "close")), w),
}
