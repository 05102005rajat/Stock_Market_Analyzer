import numpy as np

from conftest import make_df
from services import relative


def test_outperformer_has_positive_excess():
    stock = make_df(np.linspace(100, 160, 200))   # +60%
    bench = make_df(np.linspace(100, 120, 200))   # +20%
    rs = relative.relative_strength(stock, bench, lookback=126)
    assert rs is not None
    assert rs["outperforming"] is True
    assert rs["excess_pct"] > 0
    assert 0 < rs["value"] <= 1.0


def test_underperformer_has_negative_excess():
    stock = make_df(np.linspace(100, 105, 200))   # +5%
    bench = make_df(np.linspace(100, 140, 200))   # +40%
    rs = relative.relative_strength(stock, bench, lookback=126)
    assert rs["outperforming"] is False
    assert rs["value"] < 0


def test_returns_none_on_short_history():
    stock = make_df(np.linspace(100, 110, 50))
    bench = make_df(np.linspace(100, 110, 50))
    assert relative.relative_strength(stock, bench, lookback=126) is None


def test_values_are_native_floats():
    stock = make_df(np.linspace(100, 130, 200))
    bench = make_df(np.linspace(100, 120, 200))
    rs = relative.relative_strength(stock, bench)
    for k in ("excess_pct", "stock_ret_pct", "bench_ret_pct", "value"):
        assert isinstance(rs[k], float)
