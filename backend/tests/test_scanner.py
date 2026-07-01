"""Network-free tests for the scanner's pure scoring/gating logic."""
import numpy as np
import pandas as pd

from services import scanner


def _close(vals):
    return pd.Series(np.asarray(vals, float),
                     index=pd.bdate_range("2024-01-01", periods=len(vals)))


def test_breakout_detects_fresh_break_from_a_month_long_base():
    # ~month rangebound near 100 (ceiling ~101), then a fresh pop above it
    base = 100 + np.sin(np.linspace(0, 6, 25))      # oscillates ~99–101, rangebound
    last = [99.5, 100.0, 103.5]                     # prior bars below ceiling, final bar breaks
    close = _close(np.concatenate([np.full(10, 100.0), base, last]))
    price = float(close.iloc[-1])
    b = scanner._breakout(close, price, rsi=72, sma200=98.0)
    assert b and b["status"] == "broke" and b["fresh"] is True
    assert b["overbought"] is True                  # RSI 72
    assert b["overhead_200"] is False               # 200d below price -> no wall above


def test_breakout_coiling_under_resistance():
    base = 100 + np.sin(np.linspace(0, 6, 25))      # ceiling ~101
    close = _close(np.concatenate([np.full(10, 100.0), base, [100.2, 100.0, 99.8]]))
    price = float(close.iloc[-1])                   # ~2% under the ceiling, still capped
    b = scanner._breakout(close, price, rsi=55, sma200=110.0)
    assert b and b["status"] == "coiling"
    assert b["overhead_200"] is True                # 200d above price -> wall overhead


def test_breakout_none_for_steady_uptrend():
    # a steadily trending stock is NOT a rangebound base -> no watch entry
    close = _close(np.linspace(80, 140, 40))
    b = scanner._breakout(close, float(close.iloc[-1]), rsi=60, sma200=100.0)
    assert b is None


def test_dip_buckets_split_active_waiting_downtrend():
    rows = [
        {"ticker": "A", "dip_available": True, "dip_active": True, "dip_in_uptrend": True,
         "dip_win_pct": 80, "dip_rsi2": 5, "dip_plan": {"buy_near": 100}},
        {"ticker": "B", "dip_available": True, "dip_active": True, "dip_in_uptrend": True,
         "dip_win_pct": 90, "dip_rsi2": 8, "dip_plan": {"buy_near": 50}},
        {"ticker": "C", "dip_available": True, "dip_active": False, "dip_in_uptrend": True,
         "dip_win_pct": 70, "dip_rsi2": 40, "dip_plan": None},
        {"ticker": "D", "dip_available": True, "dip_active": False, "dip_in_uptrend": False,
         "dip_win_pct": None, "dip_rsi2": None, "dip_plan": None},
        {"ticker": "E", "dip_available": False},   # too little history -> excluded everywhere
    ]
    b = scanner._dip_buckets(rows)
    assert [r["ticker"] for r in b["active"]] == ["B", "A"]   # sorted by win-rate desc
    assert [r["ticker"] for r in b["waiting"]] == ["C"]
    assert b["downtrend"] == ["D"]
    assert "E" not in b["downtrend"] and all(r["ticker"] != "E" for r in b["active"])


def test_gate_requires_uptrend_and_outperformance():
    # below 200dma -> not a setup
    score, gated = scanner.setup_score(rsi=30, price=90, sma20=95, sma200=100, rs_excess=5, reversal=False)
    assert gated is False and score == 0.0
    # uptrend but underperforming SPY -> not a setup
    score, gated = scanner.setup_score(rsi=30, price=110, sma20=108, sma200=100, rs_excess=-2, reversal=False)
    assert gated is False and score == 0.0


def test_oversold_in_uptrend_scores_higher_than_overbought():
    lo, _ = scanner.setup_score(rsi=30, price=110, sma20=109, sma200=100, rs_excess=5, reversal=False)
    hi, _ = scanner.setup_score(rsi=65, price=110, sma20=109, sma200=100, rs_excess=5, reversal=False)
    assert lo > hi  # more oversold = better dip-buy score


def test_reversal_candle_adds_bonus_and_score_capped():
    base, _ = scanner.setup_score(rsi=35, price=110, sma20=109, sma200=100, rs_excess=5, reversal=False)
    withrev, _ = scanner.setup_score(rsi=35, price=110, sma20=109, sma200=100, rs_excess=5, reversal=True)
    assert withrev > base
    maxed, _ = scanner.setup_score(rsi=10, price=110, sma20=100, sma200=90, rs_excess=20, reversal=True)
    assert maxed <= 100.0


def test_universe_excludes_funds_and_dedupes():
    uni = scanner.universe()
    assert "VOO" not in uni and "SPY" not in uni and "QQQ" not in uni
    assert len(uni) == len(set(uni))
    assert "NVDA" in uni  # a real holding is present
