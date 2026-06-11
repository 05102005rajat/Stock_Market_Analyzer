from services import signal


def _bull_ctx():
    return {
        "ticker": "BULL",
        "trend": {"direction": "uptrend", "r2": 0.8},
        "multiTimeframe": {
            "alignment": "Strong uptrend — every timeframe aligned",
            "horizons": [{"direction": "uptrend"}] * 5,
            "regime": {"cross": "golden", "above_sma200": True, "cross_label": "Golden cross"},
        },
        "latest": {"rsi": 55, "macd": 1.0, "macd_signal": 0.5},
        "levels": {}, "patterns": [], "volume": {"available": True, "obv_trend": "rising", "signals": []},
        "candlesticks": [], "backtest": {"horizons": [10], "patterns": []},
        "minervini": {"available": True, "score": 8, "stage": "Stage 2 — Advancing (uptrend)"},
    }


def _bear_ctx():
    return {
        "ticker": "BEAR",
        "trend": {"direction": "downtrend", "r2": 0.8},
        "multiTimeframe": {
            "alignment": "Strong downtrend — every timeframe aligned",
            "horizons": [{"direction": "downtrend"}] * 5,
            "regime": {"cross": "death", "above_sma200": False, "cross_label": "Death cross"},
        },
        "latest": {"rsi": 40, "macd": -1.0, "macd_signal": -0.5},
        "levels": {}, "patterns": [], "volume": {"available": True, "obv_trend": "falling", "signals": []},
        "candlesticks": [], "backtest": {"horizons": [10], "patterns": []},
        "minervini": {"available": True, "score": 0, "stage": "Stage 4 — Declining (downtrend)"},
    }


def test_strong_bull_is_buy():
    out = signal.score(_bull_ctx())
    assert out["verdict"] == "BUY"
    assert out["score"] > 40
    assert out["interval"]["low"] <= out["score"] <= out["interval"]["high"]
    assert 0 <= out["confidence"] <= 100


def test_strong_bear_is_sell():
    out = signal.score(_bear_ctx())
    assert out["verdict"] == "SELL"
    assert out["score"] < -40


def test_aligned_signals_have_higher_confidence_than_mixed():
    aligned = signal.score(_bull_ctx())
    mixed = _bull_ctx()
    mixed["latest"]["rsi"] = 78          # overbought, fights the uptrend
    mixed["multiTimeframe"]["regime"] = {"cross": "death", "above_sma200": False, "cross_label": "Death cross"}
    mixed_out = signal.score(mixed)
    assert aligned["confidence"] > mixed_out["confidence"]


def test_empty_context_is_neutral_hold():
    out = signal.score({})
    assert out["verdict"] == "HOLD"
    assert out["score"] == 0.0


def test_components_are_present_and_bounded():
    for c in signal.score(_bull_ctx())["components"]:
        assert -1.0 <= c["value"] <= 1.0
        assert c["weight"] > 0
