"""Tests for the EMA-ribbon + MACD crossover engine."""
import numpy as np
import pandas as pd

from services import crossover


def _frame(close):
    idx = pd.date_range("2022-01-01", periods=len(close), freq="B")
    s = pd.Series(close, index=idx, dtype=float)
    return pd.DataFrame({"open": s, "high": s, "low": s, "close": s,
                         "volume": pd.Series(1e6, index=idx)})


def test_short_history_unavailable():
    r = crossover.analyze(_frame(np.linspace(10, 12, 50)))
    assert r["available"] is False
    assert "evidence" in r  # honest disclosure always present


def test_clean_uptrend_is_buy():
    # steadily rising series → bullish stack, MACD>0, price>EMA55 → BUY
    close = np.linspace(50, 150, 400)
    r = crossover.analyze(_frame(close))
    assert r["available"] is True
    assert r["state"] == "buy"
    assert r["direction"] == "up"
    assert r["conditions_met"] == 3
    # structure
    assert set(["values", "components", "events", "params", "evidence"]).issubset(r)
    assert r["values"]["ema55"] > r["values"]["ema204"]  # stacked up


def test_clean_downtrend_is_sell():
    close = np.linspace(150, 50, 400)
    r = crossover.analyze(_frame(close))
    assert r["state"] == "sell"
    assert r["direction"] == "down"
    assert r["values"]["ema55"] < r["values"]["ema204"]  # stacked down


def test_contrarian_flag_inverts(monkeypatch):
    close = np.linspace(50, 150, 400)
    base = crossover.analyze(_frame(close))
    monkeypatch.setattr(crossover, "CONTRARIAN", True)
    flipped = crossover.analyze(_frame(close))
    assert base["state"] == "buy"
    assert flipped["state"] == "sell"  # same data, inverted reading


def test_macd_params_are_fibonacci_signal_nine():
    # the requested 13/34, with signal corrected from 81 -> 9
    assert crossover.MACD_FAST == 13
    assert crossover.MACD_SLOW == 34
    assert crossover.MACD_SIGNAL == 9
    assert crossover.EMA_FAST, crossover.EMA_MID == (55, 89)
    assert crossover.EMA_SLOW == 204
