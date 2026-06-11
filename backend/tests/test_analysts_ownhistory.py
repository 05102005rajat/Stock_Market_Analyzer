"""Tests for services/analysts.py and resistance._own_history."""
import numpy as np
import pandas as pd

from services import analysts, resistance


def _df(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({
        "close": close, "high": close * 1.004, "low": close * 0.996,
        "volume": np.full(len(close), 1e6),
    }, index=pd.bdate_range("2021-01-04", periods=len(close)))


def test_pros_line_and_upside():
    info = {"targetMeanPrice": 255.0, "numberOfAnalystOpinions": 43,
            "recommendationKey": "buy", "recommendationMean": 1.9,
            "currentPrice": 200.0}
    out = analysts.snapshot("ORCL", _df(np.full(80, 200.0)), fetch_info=lambda t: info)
    assert out["available"] and out["rating"] == "Buy"
    assert abs(out["upside_pct"] - 27.5) < 0.1
    assert "43 analysts" in out["line"]


def test_pros_calm_line_fires_in_drawdown():
    close = np.concatenate([np.full(40, 250.0), np.linspace(250, 200, 40)])  # -20% slide
    info = {"targetMeanPrice": 255.0, "numberOfAnalystOpinions": 30,
            "recommendationKey": "buy", "recommendationMean": 2.0}
    out = analysts.snapshot("X", _df(close), fetch_info=lambda t: info)
    assert out["calm_line"] and "volatility" in out["calm_line"]


def test_pros_missing_data_degrades():
    out = analysts.snapshot("X", _df(np.full(80, 100.0)), fetch_info=lambda t: {})
    assert out["available"] is False


def test_pros_fetch_error_degrades():
    def boom(t): raise RuntimeError("network")
    out = analysts.snapshot("X", _df(np.full(80, 100.0)), fetch_info=boom)
    assert out["available"] is False


def test_own_history_counts_breakouts():
    # Staircase: repeated consolidations then jumps -> many fresh 50d-high crosses.
    rng = np.random.default_rng(1)
    close = [100.0]
    for step in range(8):
        close += list(close[-1] + rng.normal(0, 0.2, 60))          # 60d flat base
        close += list(np.linspace(close[-1], close[-1] * 1.12, 15))  # breakout leg
    close = np.array(close)
    out = resistance._own_history(pd.Series(close), pd.Series(close * 1.004))
    assert out is not None and out["n"] >= 8
    assert out["pushed_higher_5d_pct"] is not None


def test_own_history_none_when_short():
    s = pd.Series(np.linspace(100, 110, 90))
    assert resistance._own_history(s, s * 1.004) is None
