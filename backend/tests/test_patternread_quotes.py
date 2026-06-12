"""Tests for services/pattern_read.py and services/quotes.py."""
import numpy as np
import pandas as pd

from services import pattern_read, quotes


def _df(n=600, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0.05, 1.0, n))
    return pd.DataFrame({
        "open": close * (1 + rng.normal(0, 0.003, n)),
        "high": close * 1.01, "low": close * 0.99, "close": close,
        "volume": np.full(n, 1e6),
    }, index=pd.bdate_range("2023-01-02", periods=n))


def _stats(base_up=0.55, patterns=None):
    return {
        "available": True,
        "baseline": {"10": {"up_rate": base_up, "avg_return": 0.5}},
        "patterns": patterns or [],
    }


def _sig(df, name, bias, bars_ago):
    ts = int(df.index[-1 - bars_ago].timestamp())
    return {"name": name, "bias": bias, "time": ts, "strength": 0.8}


def _pat(name, bias, n, win, edge):
    return {"name": name, "bias": bias, "count": n,
            "stats": {"10": {"samples": n, "win_rate": win, "edge": edge, "avg_return": 1.0}}}


def test_bearish_tilt_from_strong_bearish_signal():
    df = _df()
    stats = _stats(patterns=[_pat("Three Black Crows", "bearish", 20, 0.70, 0.25)])
    sigs = [_sig(df, "Three Black Crows", "bearish", 2)]
    out = pattern_read.analyze(df, signals=sigs, stats_full=stats, stats_recent=stats)
    assert out["available"] and out["direction"] == "BEARISH"
    assert out["p_up_10bar"] < out["baseline_up"]
    assert "Three Black Crows" in out["verdict"]


def test_conflict_flagged_when_both_sides_weighty():
    df = _df()
    stats = _stats(patterns=[
        _pat("Bullish Harami", "bullish", 30, 0.65, 0.10),
        _pat("Bearish Harami", "bearish", 30, 0.62, 0.17),
    ])
    sigs = [_sig(df, "Bullish Harami", "bullish", 1), _sig(df, "Bearish Harami", "bearish", 3)]
    out = pattern_read.analyze(df, signals=sigs, stats_full=stats, stats_recent=stats)
    assert out["conflict"] is True
    assert "conflict" in out["verdict"].lower()


def test_small_samples_dropped_and_quiet_message():
    df = _df()
    stats = _stats(patterns=[_pat("Inverted Hammer", "bullish", 4, 0.9, 0.4)])  # n<10
    sigs = [_sig(df, "Inverted Hammer", "bullish", 1)]
    out = pattern_read.analyze(df, signals=sigs, stats_full=stats, stats_recent=stats)
    assert out["n_signals"] == 0
    assert "quiet" in out["verdict"].lower()


def test_regime_flip_flagged():
    df = _df()
    full = _stats(patterns=[_pat("Evening Star", "bearish", 30, 0.62, 0.15)])
    recent = _stats(patterns=[_pat("Evening Star", "bearish", 12, 0.40, -0.12)])  # edge flipped
    sigs = [_sig(df, "Evening Star", "bearish", 2)]
    out = pattern_read.analyze(df, signals=sigs, stats_full=full, stats_recent=recent)
    assert out["regime"] and not out["regime"]["stable"]
    assert "Evening Star" in out["regime"]["unstable_patterns"]
    assert "regime" in out["verdict"].lower() or "AI-era" in out["verdict"]


def test_stale_chart_pattern_marked():
    df = _df()
    cps = [{"name": "Double Top", "bias": "bearish", "end": str(df.index[-80].date())}]
    out = pattern_read.analyze(df, signals=[], stats_full=_stats(), chart_patterns=cps)
    assert out["chart_context"][0]["stale"] is True
    assert "STALE" in out["chart_context"][0]["note"]


def test_quote_fetch_and_cache():
    quotes._CACHE.clear()
    calls = {"n": 0}
    def fi(tk):
        calls["n"] += 1
        return {"last_price": 101.5, "previous_close": 100.0, "day_high": 102, "day_low": 99}
    out = quotes.fetch("MU", fetch_fast_info=fi)
    again = quotes.fetch("MU", fetch_fast_info=fi)
    assert out["available"] and out["change_pct"] == 1.5
    assert calls["n"] == 1  # second call served from cache


def test_quote_error_degrades():
    quotes._CACHE.clear()
    def boom(tk): raise RuntimeError("net")
    assert quotes.fetch("XX", fetch_fast_info=boom)["available"] is False
