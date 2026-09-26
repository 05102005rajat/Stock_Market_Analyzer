"""Producer/consumer contract tests.

Four shipped bugs survived a green suite because the unit tests hand-built the
shape each consumer *expected* rather than the shape its producer actually
emits (e.g. test_conviction passed {"passed": True} when minervini emits
"passes"). These tests assert on the real producer output instead.
"""
import numpy as np
import pandas as pd
import pytest

from services import conviction, insiders, minervini, patterns, pattern_read


def _trending_df(n=260, start=50.0, step=0.25):
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = np.array([start + step * i for i in range(n)], dtype=float)
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99,
         "close": close, "volume": np.full(n, 1_000_000.0)},
        index=idx,
    )


def test_minervini_emits_the_key_conviction_reads():
    out = minervini.trend_template(_trending_df())
    assert "passes" in out, "producer contract changed"
    # The consumer must read a key the producer actually emits.
    assert conviction.assess({"minervini": out})["components"] or out["passes"] is False


def test_conviction_scores_a_real_minervini_payload():
    out = minervini.trend_template(_trending_df())
    if not out.get("passes"):
        pytest.skip("synthetic series did not pass the trend template")
    comps = conviction.assess({"minervini": out})["components"]
    names = [c["name"] for c in comps]
    assert any("Trend stage" in n for n in names), names


def test_conviction_reads_the_insider_signal_key():
    # insiders.analyze() emits signal=..., not buying=/selling= booleans.
    buy = {"available": True, "signal": "buying", "cluster_buy": False,
           "buy_value": 250_000, "buy_people": 1}
    sell = {"available": True, "signal": "selling", "cluster_buy": False}
    buy_names = [c["name"] for c in conviction.assess({"insider": buy})["components"]]
    sell_names = [c["name"] for c in conviction.assess({"insider": sell})["components"]]
    assert any("Insider buying" in n for n in buy_names), buy_names
    assert any("Insider activity" in n for n in sell_names), sell_names


def test_conviction_can_reach_high_bull_and_set_direction_up():
    # direction="up" is what makes ledger.log_from_analysis record the stack;
    # with the old key names it was unreachable.
    ctx = {
        "minervini": {"available": True, "passes": True, "stage": "Stage 2", "score": "8/8"},
        "insider": {"available": True, "signal": "buying", "cluster_buy": False,
                    "buy_value": 250_000, "buy_people": 1},
    }
    out = conviction.assess(ctx)
    assert out["verdict"] == "high_bull", out
    assert out["direction"] == "up", out


def _noisy_df(n=200, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(rng.normal(0, 1.2, n))
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99,
         "close": close, "volume": np.full(n, 1_000_000.0)},
        index=idx,
    )


def test_detected_patterns_carry_the_dated_points_consumers_need():
    # patterns emits {name, bias, description, points} — no "end"/"end_date".
    for seed in range(12):
        found = patterns.detect_patterns(_noisy_df(seed=seed))
        if found:
            break
    assert found, "no pattern detected across 12 seeds"
    p = found[0]
    assert "points" in p and p["points"], p.keys()
    assert "date" in p["points"][-1], p["points"][-1]


def test_pattern_age_is_computed_not_always_none():
    for seed in range(12):
        df = _noisy_df(seed=seed)
        found = patterns.detect_patterns(df)
        if found:
            break
    assert found, "no pattern detected across 12 seeds"
    read = pattern_read.analyze(df, chart_patterns=found)
    ctx = read.get("chart_context") or read.get("patterns") or []
    ages = [x.get("age_days") for x in ctx if isinstance(x, dict)]
    assert ages, f"no chart context returned: {list(read)}"
    assert any(a is not None for a in ages), "every pattern age was None -> all STALE"
