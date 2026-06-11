import numpy as np
import pandas as pd

from conftest import make_df
from services import target


def _ohlc(closes, vol=0.01, seed=0):
    """Build OHLC with realistic intrabar highs/lows around each close."""
    rng = np.random.default_rng(seed)
    closes = np.asarray(closes, float)
    idx = pd.bdate_range("2022-01-03", periods=len(closes))
    span = closes * vol
    high = closes + np.abs(rng.normal(0, 1, len(closes))) * span
    low = closes - np.abs(rng.normal(0, 1, len(closes))) * span
    return pd.DataFrame({"open": closes, "high": high, "low": low,
                         "close": closes, "volume": 1_000_000}, index=idx)


def test_plan_unavailable_on_short_history():
    out = target.plan(_ohlc(np.linspace(100, 110, 40)))
    assert out["available"] is False


def test_plan_structure_and_ordering():
    rng = np.random.default_rng(1)
    closes = 100 * np.exp(rng.normal(0.0003, 0.012, 400).cumsum())
    out = target.plan(_ohlc(closes), horizon=5)
    assert out["available"] is True
    # Take-profit above entry, stop below entry.
    assert out["take_profit"]["price"] > out["entry"]
    assert out["stop"]["price"] < out["entry"]
    # Stretch target is more ambitious than the safe take-profit.
    assert out["stretch_target"]["ret_pct"] >= out["take_profit"]["ret_pct"]
    # Probabilities are valid.
    assert 0 <= out["prob_profit_intraweek"] <= 1
    assert 0 <= out["prob_profit_at_close"] <= 1


def test_higher_volatility_gives_wider_targets():
    rng = np.random.default_rng(2)
    calm = 100 * np.exp(rng.normal(0, 0.005, 400).cumsum())
    wild = 100 * np.exp(rng.normal(0, 0.03, 400).cumsum())
    tp_calm = target.plan(_ohlc(calm, vol=0.004))["take_profit"]["ret_pct"]
    tp_wild = target.plan(_ohlc(wild, vol=0.03))["take_profit"]["ret_pct"]
    assert tp_wild > tp_calm
