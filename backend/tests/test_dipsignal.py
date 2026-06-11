import numpy as np
from conftest import make_df
from services import dipsignal


def _ohlc(closes):
    import pandas as pd
    c = np.asarray(closes, float)
    idx = pd.bdate_range("2021-01-04", periods=len(c))
    return pd.DataFrame({"open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1}, index=idx)


def test_unavailable_on_short_history():
    assert dipsignal.verdict(_ohlc(np.linspace(100, 110, 100)))["available"] is False


def test_downtrend_is_not_a_dip_buy():
    # steadily falling -> below 200dma -> not in uptrend -> not active
    out = dipsignal.verdict(_ohlc(np.linspace(200, 100, 400)))
    if out["available"]:
        assert out["in_uptrend"] is False
        assert out["active"] is False


def test_history_fields_present_when_available():
    rng = np.random.default_rng(0)
    closes = 100 * np.exp(rng.normal(0.0004, 0.015, 600).cumsum())
    out = dipsignal.verdict(_ohlc(closes))
    if out["available"]:
        h = out["history"]
        assert 0 <= h["win_rate"] <= 1 and h["n_trades"] >= 15
        assert isinstance(out["active"], bool)
