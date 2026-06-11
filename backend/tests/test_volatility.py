import numpy as np
import pandas as pd
import pytest

from services import volatility as V


def _ohlc(closes, vol=0.01, seed=0):
    rng = np.random.default_rng(seed)
    closes = np.asarray(closes, float)
    idx = pd.bdate_range("2022-01-03", periods=len(closes))
    span = closes * vol
    high = closes + np.abs(rng.normal(0, 1, len(closes))) * span
    low = closes - np.abs(rng.normal(0, 1, len(closes))) * span
    openp = closes * (1 + rng.normal(0, vol / 2, len(closes)))
    return pd.DataFrame({"open": openp, "high": np.maximum(high, np.maximum(openp, closes)),
                         "low": np.minimum(low, np.minimum(openp, closes)),
                         "close": closes, "volume": 1_000_000}, index=idx)


def test_estimators_positive_and_ordered_by_vol():
    rng = np.random.default_rng(1)
    calm = 100 * np.exp(rng.normal(0, 0.004, 300).cumsum())
    wild = 100 * np.exp(rng.normal(0, 0.03, 300).cumsum())
    for fn in (V.close_to_close, V.ewma):
        assert fn(calm) > 0 and fn(wild) > 0
        assert fn(wild) > fn(calm)


def test_range_estimators_finite():
    df = _ohlc(100 * np.exp(np.random.default_rng(2).normal(0, 0.01, 300).cumsum()), vol=0.012)
    o, h, l, c = (df[x].to_numpy() for x in ("open", "high", "low", "close"))
    for fn in (V.parkinson, V.garman_klass, V.rogers_satchell):
        v = fn(o, h, l, c, 20) if fn is not V.parkinson else fn(h, l, 20)
        assert np.isfinite(v) and v > 0
    assert np.isfinite(V.yang_zhang(o, h, l, c, 20))


def test_blend_series_is_point_in_time_and_finite():
    df = _ohlc(100 * np.exp(np.random.default_rng(3).normal(0.0003, 0.012, 400).cumsum()), vol=0.012)
    s = V.blend_vol_series(df)
    assert len(s) == len(df)
    assert np.isnan(s[0])               # bar 0 has no return yet
    assert np.isfinite(s[40:]).all()    # populated once EWMA+YZ are warm
    assert (s[np.isfinite(s)] > 0).all()
    # scalar matches last finite of the series
    assert V.blend_vol(df) == pytest.approx(float(s[np.isfinite(s)][-1]))


def test_qlike_means_are_valid_and_blend_not_catastrophic():
    """QLIKE >= 0 by construction; sanity-check both estimators on real-ish data.
    (The actual blend-beats-cc edge is measured on real data in vol_backtest.py.)"""
    rng = np.random.default_rng(5)
    close = 100 * np.exp(rng.normal(0.0003, 0.013, 600).cumsum())
    df = _ohlc(close, vol=0.013, seed=6)
    sb = V.blend_vol_series(df)
    H = 5
    logc = np.log(df["close"].to_numpy())
    cc = np.array([np.std(np.diff(logc[max(0, t - 20):t]), ddof=1) if t > 21 else np.nan
                   for t in range(len(logc))])
    q_blend, q_cc = [], []
    for t in range(60, len(logc) - H):
        rv = np.sum(np.diff(logc[t:t + H + 1]) ** 2)
        for ser, bucket in ((sb, q_blend), (cc, q_cc)):
            s = ser[t]
            if np.isfinite(s) and s > 0 and rv > 0:
                ratio = rv / (s * s * H)
                bucket.append(ratio - np.log(ratio) - 1)
    assert np.mean(q_blend) >= 0 and np.mean(q_cc) >= 0      # QLIKE is non-negative
    assert np.mean(q_blend) <= np.mean(q_cc) * 2.0           # not catastrophically worse
