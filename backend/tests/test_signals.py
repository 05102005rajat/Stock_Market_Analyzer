"""Tests for candlesticks, volume, Minervini, and the insight engine."""
import numpy as np
import pandas as pd

from conftest import make_df
from services import candlesticks, volume, minervini, insights


# ---------------- Candlesticks ----------------
def _candle_df(rows):
    """rows: list of (open, high, low, close)."""
    idx = pd.bdate_range("2023-01-02", periods=len(rows))
    arr = np.array(rows, dtype=float)
    return pd.DataFrame(
        {"open": arr[:, 0], "high": arr[:, 1], "low": arr[:, 2],
         "close": arr[:, 3], "volume": 1_000_000},
        index=idx,
    )


def test_bullish_engulfing_detected():
    rows = [(50, 50.2, 47, 47.5)] * 6  # downtrend filler
    rows += [(46, 46.2, 44, 44.5)]     # prior down bar
    rows += [(44, 49.5, 43.8, 49)]     # big up bar engulfing it
    names = [s["name"] for s in candlesticks.detect(_candle_df(rows))]
    assert "Bullish Engulfing" in names


def test_doji_detected_and_neutral():
    rows = [(50, 51, 49, 50.4)] * 8
    rows += [(50, 51.5, 48.5, 50.02)]  # tiny body = doji
    sigs = candlesticks.detect(_candle_df(rows))
    doji = [s for s in sigs if s["name"] == "Doji"]
    assert doji and doji[0]["bias"] == "neutral"


def test_candlestick_schema_json_safe():
    import json
    rows = [(50, 52, 49, 51)] * 10
    for s in candlesticks.detect(_candle_df(rows)):
        assert set(s) == {"category", "name", "bias", "time", "date", "strength", "description"}
        assert 0.0 <= s["strength"] <= 1.0
    json.dumps(candlesticks.detect(_candle_df(rows)))  # must not raise


# ---------------- Volume ----------------
def test_volume_spike_and_breakout():
    closes = list(np.linspace(50, 60, 60))
    closes[-1] = 65  # new high
    df = make_df(closes)
    vols = np.full(60, 1_000_000.0)
    vols[-1] = 3_000_000.0  # spike on the breakout bar
    df["volume"] = vols
    out = volume.analyze(df)
    names = [s["name"] for s in out["signals"]]
    assert out["available"] is True
    assert "Volume Spike" in names
    assert "Breakout on Volume" in names


def test_volume_unavailable_when_zero():
    df = make_df(np.linspace(50, 60, 60))
    df["volume"] = 0
    out = volume.analyze(df)
    assert out["available"] is False
    assert out["signals"] == []


# ---------------- Minervini ----------------
def test_minervini_uptrend_passes():
    out = minervini.trend_template(make_df(np.linspace(50, 150, 300)))
    assert out["available"] and out["passes"] and out["score"] == 8
    assert "Stage 2" in out["stage"]


def test_minervini_downtrend_stage4():
    out = minervini.trend_template(make_df(np.linspace(150, 50, 300)))
    assert out["available"] and not out["passes"]
    assert "Stage 4" in out["stage"]


def test_minervini_short_history_unavailable():
    out = minervini.trend_template(make_df(np.linspace(50, 60, 100)))
    assert out["available"] is False


# ---------------- Insights ----------------
def _bull_ctx():
    return {
        "ticker": "BULL",
        "trend": {"direction": "uptrend"},
        "multiTimeframe": {
            "alignment": "Strong uptrend — every timeframe aligned",
            "regime": {"cross": "golden", "above_sma200": True},
        },
        "latest": {"close": 100, "rsi": 55, "macd": 1.2, "macd_signal": 0.8, "sma50": 95},
        "levels": {"resistance": [105], "support": [98]},
        "candlesticks": [{"name": "Hammer", "bias": "bullish", "date": "2024-01-10"}],
        "patterns": [],
        "volume": {"available": True, "signals": []},
        "minervini": {"available": True, "passes": True, "stage": "Stage 2 — Advancing (uptrend)"},
    }


def _bear_ctx():
    return {
        "ticker": "BEAR",
        "trend": {"direction": "downtrend"},
        "multiTimeframe": {
            "alignment": "Strong downtrend — every timeframe aligned",
            "regime": {"cross": "death", "above_sma200": False},
        },
        "latest": {"close": 50, "rsi": 35, "macd": -1.0, "macd_signal": -0.5, "sma50": 60},
        "levels": {"resistance": [58], "support": [45]},
        "candlesticks": [{"name": "Shooting Star", "bias": "bearish", "date": "2024-01-10"}],
        "patterns": [],
        "volume": {"available": True, "signals": []},
        "minervini": {"available": True, "passes": False, "stage": "Stage 4 — Declining (downtrend)"},
    }


def test_insights_bullish_situation():
    out = insights.generate(_bull_ctx())
    assert out["bias"] == "bullish"
    titles = [r["title"] for r in out["recommendations"]]
    assert any("Stage 2" in t for t in titles)
    assert out["watch"]


def test_insights_bearish_fires_downtrend_rec():
    out = insights.generate(_bear_ctx())
    assert out["bias"] == "bearish"
    titles = " ".join(r["title"] for r in out["recommendations"])
    assert "Downtrend regime" in titles


def test_insights_robust_to_empty_context():
    out = insights.generate({})  # nothing should crash
    assert "situation" in out and "recommendations" in out
