import numpy as np
import pandas as pd
import pytest

from conftest import make_df
from services import indicators


def test_rsi_pure_uptrend_is_100():
    s = pd.Series(np.linspace(10, 30, 40))
    assert indicators.rsi(s).iloc[-1] == pytest.approx(100.0)


def test_rsi_pure_downtrend_is_0():
    s = pd.Series(np.linspace(30, 10, 40))
    assert indicators.rsi(s).iloc[-1] == pytest.approx(0.0)


def test_rsi_flat_is_50_after_warmup():
    s = pd.Series([100.0] * 40)
    assert indicators.rsi(s).iloc[-1] == pytest.approx(50.0)


def test_rsi_warmup_is_nan():
    s = pd.Series(np.linspace(10, 30, 40))
    # First `period` values have no defined average yet.
    assert indicators.rsi(s, period=14).iloc[:14].isna().all()


def test_compute_all_shape():
    df = make_df(np.linspace(50, 150, 120))
    out = indicators.compute_all(df)
    for key in ["sma20", "sma50", "rsi", "macd", "bb_upper"]:
        assert key in out["indicators"]
    assert out["latest"]["close"] == pytest.approx(150.0, rel=1e-3)
    # Line series carry epoch-second time keys and finite values.
    for pt in out["indicators"]["sma20"]:
        assert isinstance(pt["time"], int)
        assert np.isfinite(pt["value"])
