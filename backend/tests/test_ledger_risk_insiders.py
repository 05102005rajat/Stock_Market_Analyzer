"""Tests for services/ledger.py, services/risk.py, services/insiders.py."""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from services import insiders, ledger, risk


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(ledger, "DB", path)
    yield
    os.unlink(path)


def _prices(start="2026-01-02", n=120, drift=0.001):
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(100 * np.exp(np.cumsum(np.full(n, drift))), index=idx)


# ---------- ledger ----------
def test_ledger_log_and_dedup():
    assert ledger.log("MU", "dip_buy", "up", 100.0, ts="2026-03-01") is True
    assert ledger.log("MU", "dip_buy", "up", 100.0, ts="2026-03-01") is False  # dup same day
    assert len(ledger.recent()) == 1


def test_ledger_log_from_analysis_extracts_signals():
    payload = {
        "quote": {"available": True, "price": 200.0},
        "resistance": {"available": True, "state": "fresh_breakout",
                       "ath_bucket": {"p_reach_ath_63d": 0.62}, "headline": "h"},
        "dipSignal": {"available": True, "active": True},
        "patternRead": {"available": True, "direction": "BEARISH", "p_up_10bar": 0.42, "tilt_pp": -5},
        "earningsWatch": {"available": True, "hot_runup": True, "note": "hot"},
    }
    logged = ledger.log_from_analysis("NVDA", payload)
    assert set(logged) == {"resistance_breakout", "dip_buy", "pattern_tilt", "earnings_runup"}


def test_ledger_evaluate_and_calibration():
    ledger.log("AAA", "dip_buy", "up", None or 100.0, ts="2026-01-05")
    # inject a known upward price path
    up = _prices("2026-01-02", 120, drift=0.002)
    flat = _prices("2026-01-02", 120, drift=0.0)
    ledger.evaluate(lambda tk: up if tk == "AAA" else flat)
    cal = ledger.calibration(min_n=1)
    assert cal["available"]
    dip = next(t for t in cal["type_stats"] if t["signal_type"] == "dip_buy")
    assert dip["avg_dir_return_21d"] > 0  # upward path -> positive realized


def test_ledger_calibration_empty():
    cal = ledger.calibration()
    assert cal["available"] is False


# ---------- risk ----------
def _ohlc(n=60):
    c = np.linspace(100, 110, n)
    return pd.DataFrame({"high": c * 1.02, "low": c * 0.98, "close": c},
                        index=pd.bdate_range("2026-01-02", periods=n))


def test_atr_and_sizing():
    s = risk.size_position(5000, 110, _ohlc())
    assert s["available"]
    assert s["shares"] > 0 and s["stop_price"] < 110
    assert s["dollar_risk"] == pytest.approx(50.0)  # 1% of 5000


def test_kelly_positive_and_negative():
    pos = risk.kelly(0.6, 2.0, fraction=0.25)
    assert pos["full_kelly_pct"] > 0 and pos["fractional_pct"] == pytest.approx(pos["full_kelly_pct"] * 0.25, abs=0.1)
    neg = risk.kelly(0.3, 1.0)
    assert neg["full_kelly_pct"] < 0 and "ZERO" in neg["note"]


def test_portfolio_heat_flag():
    pos = [{"ticker": "A", "shares": 10, "entry": 100, "stop": 90},
           {"ticker": "B", "shares": 5, "entry": 200, "stop": 180}]
    h = risk.portfolio_heat(pos, 5000)
    assert h["heat_pct"] == pytest.approx((10 * 10 + 5 * 20) / 5000 * 100, abs=0.1)


def test_concentration_flags_single_and_theme():
    w = {"NVDA": 0.16, "AVGO": 0.10, "TSM": 0.18, "AAPL": 0.05}
    c = risk.concentration(w, {"AI/Semis": ["NVDA", "AVGO", "TSM"]})
    assert "NVDA" in c["over_single_name"] and "TSM" in c["over_single_name"]
    assert c["over_theme"]  # 0.16+0.10+0.18 = 0.44 > 0.40


# ---------- insiders ----------
def test_insider_detects_real_buys():
    def mock(tk):
        return [
            {"code": "P", "shares": 5000, "price": 185.0, "ad": "A", "owner": "Smith", "role": "CEO"},
            {"code": "P", "shares": 2000, "price": 186.0, "ad": "A", "owner": "Doe", "role": "CFO"},
            {"code": "P", "shares": 1000, "price": 184.0, "ad": "A", "owner": "Roe", "role": "Director"},
            {"code": "M", "shares": 9000, "price": 50.0, "ad": "A", "owner": "Smith", "role": "CEO"},
        ]
    insiders._CACHE.clear()
    out = insiders.analyze("BUY", fetch_transactions=mock)
    assert out["available"] and out["signal"] == "buying"
    assert out["cluster_buy"] is True and out["buy_csuite"] is True
    assert out["buy_shares"] == 8000  # option exercise excluded
    assert out["buy_avg_price"] == pytest.approx(185.0, abs=0.5)


def test_insider_detects_selling():
    def mock(tk):
        return [
            {"code": "S", "shares": 50000, "price": 290.0, "ad": "D", "owner": "A", "role": "SVP"},
            {"code": "F", "shares": 5000, "price": 290.0, "ad": "D", "owner": "A", "role": "SVP"},
        ]
    insiders._CACHE.clear()
    out = insiders.analyze("SELL", fetch_transactions=mock)
    assert out["signal"] == "selling" and out["sell_shares"] == 50000
    assert "SOLD" in out["badge"]


def test_insider_routine_only():
    def mock(tk):
        return [{"code": "A", "shares": 1000, "price": 0, "ad": "A", "owner": "X", "role": "Dir"},
                {"code": "M", "shares": 5000, "price": 50, "ad": "A", "owner": "Y", "role": "CEO"}]
    insiders._CACHE.clear()
    out = insiders.analyze("ROUT", fetch_transactions=mock)
    assert out["signal"] == "routine" and out["n_routine"] == 2


def test_insider_no_data_degrades():
    insiders._CACHE.clear()
    out = insiders.analyze("NONE", fetch_transactions=lambda tk: [])
    assert out["available"] is False


# ---------- forecast track record ----------
def test_track_record_scores_and_breaks_down():
    from services import forecast
    import numpy as np
    import pandas as pd
    # build a trending series with noise (enough history)
    n = 400
    idx = pd.bdate_range("2024-06-01", periods=n)
    rng = np.random.default_rng(0)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    df = pd.DataFrame({"high": close * 1.01, "low": close * 0.99, "close": close,
                       "open": close}, index=idx)
    r = forecast.track_record(df, horizon=10, n_tests=30)
    assert r["available"]
    assert 0 <= r["hit_rate"] <= 100
    assert r["tries"] > 0 and r["direction_hits"] <= r["tries"]
    assert "plain" in r and r["majority_baseline"] >= 50


def test_track_record_insufficient_history():
    from services import forecast
    import pandas as pd
    import numpy as np
    idx = pd.bdate_range("2026-01-01", periods=50)
    close = np.linspace(100, 110, 50)
    df = pd.DataFrame({"high": close, "low": close, "close": close, "open": close}, index=idx)
    r = forecast.track_record(df, horizon=10)
    assert r["available"] is False
