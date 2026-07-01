"""Network-free tests for the portfolio look-through math (funds mocked)."""
import numpy as np
import pandas as pd

from services import portfolio


def _series(closes):
    return pd.Series(np.asarray(closes, float),
                     index=pd.bdate_range("2021-01-04", periods=len(closes)))


def test_trend_stage_uptrend_is_stage2():
    s = portfolio._trend_stage(_series(np.linspace(100, 300, 400)))
    assert s["stage"] == "stage2"               # above a rising 200-day


def test_trend_stage_downtrend_is_declining():
    s = portfolio._trend_stage(_series(np.linspace(300, 100, 400)))
    assert s["stage"] == "stage4"               # below a falling 200-day & 50-day


def test_trend_stage_below_200_but_above_50_is_recovering():
    # long decline then a modest uptick: price ends below the 200-day but above the 50-day
    closes = np.concatenate([np.linspace(200, 95, 340), np.linspace(95, 110, 60)])
    s = portfolio._trend_stage(_series(closes))
    assert s["stage"] == "recovering"


def test_trend_stage_has_honest_non_buy_framing():
    s = portfolio._trend_stage(_series(np.linspace(100, 300, 400)))
    assert {"stage", "stage_label", "stage_emoji", "stage_note"} <= s.keys()
    assert "not" in s["stage_note"].lower() or "context" in s["stage_note"].lower()


def test_look_through_expands_etf_and_merges_share_classes(monkeypatch):
    def fake_fh(t):
        return {"AAPL": 0.5, "GOOG": 0.2} if t == "ETFX" else None
    monkeypatch.setattr(portfolio, "_fund_holdings", fake_fh)
    rows = [{"ticker": "ETFX", "value": 1000.0}, {"ticker": "GOOGL", "value": 500.0}]
    lt = portfolio.look_through(rows)
    eff = {e["ticker"]: e["value"] for e in lt["effective"]}
    assert abs(eff["AAPL"] - 500.0) < 1e-6           # 0.5 * 1000
    assert abs(eff["GOOGL"] - (500.0 + 200.0)) < 1e-6  # direct + GOOG(0.2*1000) merged
    # residual = 1000 * (1 - 0.7) = 300; /1500 = 20%
    assert abs(lt["residual_diversified_pct"] - 20.0) < 0.1


def test_concentration_metrics(monkeypatch):
    monkeypatch.setattr(portfolio, "_fund_holdings", lambda t: None)
    rows = [{"ticker": "A", "value": 600.0}, {"ticker": "B", "value": 300.0}, {"ticker": "C", "value": 100.0}]
    c = portfolio.look_through(rows)["concentration"]
    assert abs(c["hhi"] - 0.46) < 0.01           # 0.6²+0.3²+0.1²
    assert abs(c["effective_n"] - 2.2) < 0.1     # 1/0.46
    assert abs(c["top3_pct"] - 100.0) < 0.1


def test_empty_portfolio_unavailable():
    assert portfolio.look_through([])["available"] is False
