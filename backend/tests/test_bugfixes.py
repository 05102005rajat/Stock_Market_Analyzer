"""Regression tests for bugs found in the codebase review (keep them fixed)."""
import numpy as np
import pandas as pd

from conftest import make_df
from services import forecast, insights, patterns, relative


def _df(closes):
    idx = pd.bdate_range("2022-01-03", periods=len(closes))
    c = np.asarray(closes, float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1}, index=idx)


def test_relative_guards_zero_stock_close():
    # A zero/NaN stock close at the lookback bar must return None, not inf/NaN
    # (which would corrupt the whole /analyze JSON via Flask jsonify).
    stock = np.linspace(100, 150, 200)
    stock[200 - 126] = 0.0
    rs = relative.relative_strength(_df(stock), _df(np.linspace(100, 120, 200)))
    assert rs is None
    stock2 = np.linspace(100, 150, 200)
    stock2[-1] = np.nan
    assert relative.relative_strength(_df(stock2), _df(np.linspace(100, 120, 200))) is None


def test_insights_absent_macd_does_not_vote_bearish():
    # Empty / MACD-less context should be NEUTRAL, not biased bearish by absent data.
    out = insights.generate({})
    assert out["bias"] == "neutral"
    # And no fabricated MACD footnote when MACD is missing.
    assert not any("MACD" in r["title"] for r in out["recommendations"])


def test_patterns_handle_empty_dataframe():
    empty = _df([])
    assert patterns.trend(empty)["direction"] == "sideways"   # no IndexError
    assert patterns.detect_patterns(empty) == []              # no ValueError


def test_future_dates_no_off_by_one_for_nonbusiness_last():
    # Last index a Sunday: the first real forecast day (Mon) must NOT be dropped.
    idx = pd.DatetimeIndex([pd.Timestamp("2023-06-16"), pd.Timestamp("2023-06-18")])
    fd = forecast._future_dates(idx, 3, "1d")
    assert fd[0] == pd.Timestamp("2023-06-19")  # Monday, not skipped
    assert len(fd) == 3 and all(d.weekday() < 5 for d in fd)
