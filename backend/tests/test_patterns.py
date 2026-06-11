import numpy as np
import pytest

from conftest import make_df
from services import patterns


def test_trend_single_row_does_not_crash():
    df = make_df([100.0])
    out = patterns.trend(df)
    assert out["direction"] == "sideways"  # no LinAlgError


def test_trend_directions():
    assert patterns.trend(make_df(np.linspace(50, 150, 60)))["direction"] == "uptrend"
    assert patterns.trend(make_df(np.linspace(150, 50, 60)))["direction"] == "downtrend"
    assert patterns.trend(make_df([100.0] * 60))["direction"] == "sideways"


def test_support_resistance_classified_by_current_price():
    # Sine wave so swings sit both above and below the final price.
    x = np.linspace(0, 6 * np.pi, 200)
    df = make_df(100 + 10 * np.sin(x))
    sr = patterns.support_resistance(df)
    current = float(df["close"].iloc[-1])
    assert all(r > current for r in sr["resistance"]), sr["resistance"]
    assert all(s < current for s in sr["support"]), sr["support"]


def test_support_resistance_uptrend_has_no_overhead_resistance():
    df = make_df(np.linspace(50, 150, 200))  # ends at the high
    sr = patterns.support_resistance(df)
    assert sr["resistance"] == []  # nothing above price
    assert all(s < 150 for s in sr["support"])


def test_extrema_no_index_is_both_max_and_min():
    vals = np.array([1.0, 2, 2, 2, 1, 3, 1, 4, 2, 5, 1, 6, 2], dtype=float)
    maxima, minima = patterns._extrema(vals, order=2)
    assert set(maxima).isdisjoint(set(minima))


def test_detect_ascending_triangle():
    close = np.full(120, 105.0)
    maxima = np.array([70, 80, 90, 100, 110])
    minima = np.array([75, 85, 95, 105, 115])
    close[maxima] = 110.0  # flat resistance
    for v, i in zip([100, 101, 102, 103, 104], minima):  # rising support
        close[i] = float(v)
    res = patterns._detect_triangles(make_df(close), maxima, minima)
    assert res and res[0]["name"] == "Ascending Triangle"
    assert res[0]["bias"] == "bullish"


def test_detect_descending_triangle():
    close = np.full(120, 105.0)
    maxima = np.array([70, 80, 90, 100, 110])
    minima = np.array([75, 85, 95, 105, 115])
    for v, i in zip([114, 113, 112, 111, 110], maxima):  # falling resistance
        close[i] = float(v)
    close[minima] = 100.0  # flat support
    res = patterns._detect_triangles(make_df(close), maxima, minima)
    assert res and res[0]["name"] == "Descending Triangle"
    assert res[0]["bias"] == "bearish"


def test_analyze_returns_expected_keys():
    df = make_df(100 + 10 * np.sin(np.linspace(0, 6 * np.pi, 150)))
    out = patterns.analyze(df)
    assert set(out) == {"trend", "levels", "patterns"}
    assert isinstance(out["patterns"], list)
