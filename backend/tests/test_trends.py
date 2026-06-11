import numpy as np

from conftest import make_df
from services import trends


def test_multi_timeframe_uptrend_all_aligned():
    df = make_df(np.linspace(50, 150, 300))
    mtf = trends.multi_timeframe(df)
    labels = {h["label"] for h in mtf["horizons"]}
    assert {"1W", "1M", "3M", "6M", "1Y"} <= labels
    assert all(h["direction"] == "uptrend" for h in mtf["horizons"])
    assert all(h["change_pct"] > 0 for h in mtf["horizons"])
    assert "uptrend" in mtf["alignment"].lower()


def test_multi_timeframe_regime_golden_cross_in_uptrend():
    df = make_df(np.linspace(50, 150, 300))
    regime = trends.multi_timeframe(df)["regime"]
    assert regime["cross"] == "golden"
    assert regime["above_sma200"] is True


def test_multi_timeframe_death_cross_in_downtrend():
    df = make_df(np.linspace(150, 50, 300))
    regime = trends.multi_timeframe(df)["regime"]
    assert regime["cross"] == "death"
    assert regime["above_sma200"] is False


def test_multi_timeframe_short_history_drops_long_horizons():
    df = make_df(np.linspace(50, 60, 30))
    mtf = trends.multi_timeframe(df)
    labels = {h["label"] for h in mtf["horizons"]}
    assert "1Y" not in labels  # 252 bars unavailable
    assert mtf["regime"]["sma200"] is None
