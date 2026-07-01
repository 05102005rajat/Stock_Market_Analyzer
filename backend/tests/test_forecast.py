import numpy as np
import pandas as pd

from conftest import make_df
from services import forecast


def _series(n=300, seed=0):
    rng = np.random.default_rng(seed)
    steps = rng.normal(0.0005, 0.01, n).cumsum()
    return 100 * np.exp(steps)


def test_forecast_dates_are_business_days():
    df = make_df(_series())
    fc = forecast.forecast(df, horizon=10, interval="1d")
    assert fc["available"] is True
    assert len(fc["points"]) == 10
    dates = [pd.Timestamp(p["date"]) for p in fc["points"]]
    assert all(d.weekday() < 5 for d in dates), [d.strftime("%a") for d in dates]


def test_forecast_times_strictly_increasing_after_last_bar():
    df = make_df(_series())
    fc = forecast.forecast(df, horizon=15, interval="1d")
    last_bar = int(df.index[-1].timestamp())
    times = [p["time"] for p in fc["points"]]
    assert times[0] > last_bar
    assert all(b > a for a, b in zip(times, times[1:]))


def test_forecast_reports_baseline_metric():
    df = make_df(_series())
    m = forecast.forecast(df, horizon=10)["metrics"]
    assert m["baseline_accuracy"] is not None
    assert 0.0 <= m["directional_accuracy"] <= 1.0


def test_forecast_unavailable_on_short_history():
    fc = forecast.forecast(make_df(_series(n=30)), horizon=10)
    assert fc["available"] is False
    assert fc["points"] == []


def test_forecast_band_is_json_safe():
    df = make_df(_series())
    for p in forecast.forecast(df, horizon=5)["points"]:
        assert isinstance(p["lower"], float) and isinstance(p["upper"], float)
        assert p["lower"] <= p["value"] <= p["upper"]
