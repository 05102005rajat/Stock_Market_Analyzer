import numpy as np

from conftest import make_df
from services import backtest


def test_backtest_runs_and_reports_baseline():
    # Noisy uptrend so candlestick patterns actually fire.
    rng = np.random.default_rng(1)
    close = 100 * np.exp(rng.normal(0.0004, 0.012, 600).cumsum())
    out = backtest.run(make_df(close), horizons=(5, 10, 20))
    assert out["available"] is True
    for h in ("5", "10", "20"):
        assert 0.0 <= out["baseline"][h]["up_rate"] <= 1.0
    # Patterns table is sorted by edge at the middle horizon (descending).
    edges = [p["stats"]["10"]["edge"] for p in out["patterns"] if p["stats"].get("10")]
    assert edges == sorted(edges, reverse=True)


def test_backtest_filters_small_samples():
    rng = np.random.default_rng(2)
    close = 100 * np.exp(rng.normal(0, 0.01, 600).cumsum())
    out = backtest.run(make_df(close), min_samples=5)
    assert all(p["count"] >= 5 for p in out["patterns"])


def test_backtest_unavailable_on_short_history():
    out = backtest.run(make_df(np.linspace(50, 60, 20)))
    assert out["available"] is False
    assert out["patterns"] == []


def test_backtest_edge_is_winrate_minus_baseline():
    rng = np.random.default_rng(3)
    close = 100 * np.exp(rng.normal(0.0003, 0.011, 700).cumsum())
    out = backtest.run(make_df(close), horizons=(10,))
    for p in out["patterns"]:
        s = p["stats"]["10"]
        base = out["baseline"]["10"]["up_rate"]
        expected = round(s["win_rate"] - (base if p["bias"] != "bearish" else 1 - base), 3)
        assert abs(s["edge"] - expected) < 1e-6
