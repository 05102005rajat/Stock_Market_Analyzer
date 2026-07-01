"""Tests for services/gaps.py."""
import numpy as np
import pandas as pd

from services import gaps


def _ohlc(n=300, seed=0, gap_today=0.0):
    """Synthetic daily OHLC with engineered gaps sprinkled through history and
    an optional gap on the final bar."""
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.03, 0.8, n))
    open_ = np.empty(n)
    open_[0] = close[0]
    open_[1:] = close[:-1] * (1 + rng.normal(0, 0.004, n - 1))
    # engineer ~40 clear gap-ups (+1%) that FADE (low touches prior close, close < open)
    idx = rng.choice(np.arange(60, n - 2), 40, replace=False)
    for i in idx:
        open_[i] = close[i - 1] * 1.01
        close[i] = open_[i] * 0.997          # fades a bit
    open_[-1] = close[-2] * (1 + gap_today)
    if gap_today:
        close[-1] = open_[-1] * 1.001
    high = np.maximum(open_, close) * 1.003
    low = np.minimum(open_, close) * 0.997
    # ensure engineered fades actually touch prior close
    for i in idx:
        low[i] = min(low[i], close[i - 1] * 0.999)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": np.full(n, 1e6)},
                        index=pd.bdate_range("2023-01-02", periods=n))


def test_requires_open_column():
    df = _ohlc().drop(columns=["open"])
    assert gaps.analyze(df)["available"] is False


def test_no_gap_today_card_hidden():
    out = gaps.analyze(_ohlc(gap_today=0.0))
    assert out["available"] and out["gapped_today"] is False
    assert "up_small" in out["own"]  # history stats still computed


def test_gap_up_today_uses_own_rates():
    out = gaps.analyze(_ohlc(gap_today=0.012))
    assert out["gapped_today"] and out["direction"] == "up" and out["bucket"] == "small"
    r = out["today_rates"]
    assert r and r["n"] >= 10
    # engineered gaps mostly fade -> fade rate should be high
    assert r["faded_to_prior_close_pct"] >= 50
    assert "fade" in out["note"].lower() or "faded" in out["note"].lower()


def test_big_gap_down_bucket():
    out = gaps.analyze(_ohlc(seed=3, gap_today=-0.03))
    assert out["gapped_today"] and out["direction"] == "down" and out["bucket"] == "big"
