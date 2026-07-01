"""Tests for the conviction-stack engine (evidence-backed signal aggregation)."""
from services import conviction


def test_aligned_strong_signals_high_conviction():
    r = conviction.assess({
        "relativeStrength": {"outperforming": True, "excess_pct": 18.0, "lookback": "6mo"},
        "minervini": {"available": True, "passed": True, "stage": "Stage 2", "score": "8/8"},
        "insider": {"available": True, "cluster_buy": True, "buying": True,
                    "buy_people": 4, "buy_value": 1_000_000},
        "crossover": {"available": True, "state": "buy"},
    })
    assert r["available"] is True
    assert r["verdict"] == "high_bull"
    assert r["direction"] == "up"
    assert r["aligned_bullish"] >= 2


def test_chart_signal_has_zero_weight():
    # only the weak chart crossover fires (bullish) but momentum is negative ->
    # must NOT be bullish, because the chart signal is weighted zero.
    r = conviction.assess({
        "relativeStrength": {"outperforming": False, "excess_pct": -6.0, "lookback": "6mo"},
        "crossover": {"available": True, "state": "buy"},
    })
    assert r["direction"] != "up"
    # the crossover component is present but weak/zero-weight
    cross = [c for c in r["components"] if "crossover" in c["name"].lower()][0]
    assert cross["strength"] == "weak"
    assert cross["weight"] == 0


def test_earnings_runup_is_a_caution():
    r = conviction.assess({
        "relativeStrength": {"outperforming": True, "excess_pct": 20.0, "lookback": "6mo"},
        "minervini": {"available": True, "passed": True, "stage": "Stage 2", "score": "8/8"},
        "earningsWatch": {"available": True, "hot_runup": True, "days_to_earnings": 5},
    })
    cautions = [c for c in r["components"] if c["state"] == "caution"]
    assert len(cautions) == 1
    assert "earnings" in cautions[0]["name"].lower()
    # with 2 aligned bullish signals it's high-conviction, and the caution
    # is surfaced in the headline.
    assert r["verdict"] == "high_bull"
    assert "earnings run-up" in r["headline"].lower()


def test_empty_context_unavailable():
    r = conviction.assess({})
    assert r["available"] is False
