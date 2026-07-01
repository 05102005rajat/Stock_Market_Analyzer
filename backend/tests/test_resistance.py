"""Tests for services/resistance.py — level detection, state machine, payload."""
import numpy as np
import pandas as pd
import pytest

from services import resistance


def _df(close, high=None, volume=None):
    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float) if high is not None else close * 1.005
    vol = np.asarray(volume, dtype=float) if volume is not None else np.full(len(close), 1e6)
    idx = pd.bdate_range("2022-01-03", periods=len(close))
    return pd.DataFrame({"close": close, "high": high, "low": close * 0.995, "volume": vol}, index=idx)


def test_too_short_history():
    out = resistance.analyze(_df(np.linspace(10, 12, 30)))
    assert out["available"] is False


def test_level_is_prior_50d_high_point_in_time():
    # Flat at 100, a spike high of 120 thirty bars ago, today closes at 100.
    n = 80
    close = np.full(n, 100.0)
    high = close * 1.005
    high[n - 30] = 120.0
    out = resistance.analyze(_df(close, high))
    assert out["available"]
    assert out["level"] == pytest.approx(120.0, abs=0.01)
    assert out["state"] == "below"  # 20% away, far below


def test_fresh_breakout_state_and_odds_text():
    # Resistance ~110 (several rejections), then today closes above it.
    n = 120
    close = np.full(n, 100.0) + np.random.default_rng(0).normal(0, 0.3, n)
    high = close * 1.004
    for i in (60, 75, 90):  # three swing-high rejections at ~110
        high[i] = 110.0
        close[i] = 108.0
    close[-2] = 109.0
    close[-1] = 111.5  # fresh close above the 110 level
    high[-1] = 112.0
    out = resistance.analyze(_df(close, high))
    assert out["state"] == "fresh_breakout"
    assert out["touches"] >= 2
    assert any("retest" in o.lower() for o in out["odds"])
    assert "n=" in " ".join(out["odds"])  # sample sizes surfaced


def test_approaching_state():
    n = 120
    close = np.full(n, 100.0)
    high = close * 1.004
    high[70] = 110.0
    close_last = 108.5  # within 2% below 110
    close[-1] = close_last
    high[-1] = 109.0
    out = resistance.analyze(_df(close, high))
    assert out["state"] == "approaching"
    assert out["pct_to_level"] > 0
    assert any("minority" in o.lower() for o in out["odds"])


def test_blue_sky_bucket_when_above_old_ath():
    # Steady uptrend making new highs — today above all prior closes.
    close = np.linspace(50, 150, 300)
    out = resistance.analyze(_df(close))
    assert out["dist_ath_pct"] <= 0 or out["ath_bucket"]["label"].startswith("blue sky")


def test_caveats_always_present():
    close = np.linspace(50, 150, 300)
    out = resistance.analyze(_df(close))
    assert "survivorship" in out["evidence"]
    assert "Not a prediction" in out["caveat"]
