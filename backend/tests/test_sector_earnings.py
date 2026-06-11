"""Tests for services/sector.py and services/earnings.py."""
from datetime import date, timedelta

import numpy as np
import pandas as pd

from services import earnings, sector


def _series(vals):
    return pd.Series(np.asarray(vals, dtype=float),
                     index=pd.bdate_range("2024-01-02", periods=len(vals)))


def _peer_fetcher(last_day_ret: dict[str, float], n=60):
    base = {tk: _series(np.full(n, 100.0)) for tk in last_day_ret}
    for tk, r in last_day_ret.items():
        base[tk].iloc[-1] = 100.0 * (1 + r)
    def fetch(tk):
        if tk not in base:
            raise ValueError("no data")
        return base[tk]
    return fetch


def test_sector_unknown_ticker():
    out = sector.analyze("ZZZZ", lambda tk: _series(np.full(60, 100.0)))
    assert out["available"] is False


def test_broad_selloff_detected_and_survivor_flagged():
    peers = sector.SECTORS["Semiconductors"]
    rets = {tk: -0.02 for tk in peers}
    rets["NVDA"] = 0.005  # the green survivor
    out = sector.analyze("NVDA", _peer_fetcher(rets))
    assert out["available"] and out["event"] == "broad_selloff"
    assert out["survivor"] is True
    text = " ".join(out["notes"]).lower()
    assert "did not" in text  # the honest no-contagion message is present


def test_normal_day_no_event():
    peers = sector.SECTORS["Energy"] + sector.SECTORS["Telecom"]
    rets = {tk: 0.001 * (i - 2) for i, tk in enumerate(peers)}
    out = sector.analyze("XOM", _peer_fetcher({tk: rets.get(tk, 0) for tk in sector.SECTORS["Energy"]}))
    # Energy has only 2 members -> not enough peers, gracefully unavailable
    assert out["available"] is False


def test_earnings_no_key_degrades(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)
    earnings._CACHE.clear()
    df = pd.DataFrame({"close": np.linspace(100, 120, 60)})
    out = earnings.analyze("AAPL", df)
    assert out["available"] is False


def test_hot_runup_flag(monkeypatch):
    earnings._CACHE.clear()
    monkeypatch.setattr(earnings, "next_earnings_date",
                        lambda tk: date.today() + timedelta(days=3))
    close = np.full(60, 100.0)
    close[-11:] = np.linspace(100, 112, 11)  # +12% in 10 sessions
    out = earnings.analyze("NVDA", pd.DataFrame({"close": close}))
    assert out["available"] and out["hot_runup"] is True
    assert "pre-paid" in (out["note"] or "").lower() or "flat" in (out["note"] or "").lower()


def test_calm_runup_no_flag(monkeypatch):
    earnings._CACHE.clear()
    monkeypatch.setattr(earnings, "next_earnings_date",
                        lambda tk: date.today() + timedelta(days=3))
    out = earnings.analyze("KO", pd.DataFrame({"close": np.full(60, 100.0)}))
    assert out["available"] and out["hot_runup"] is False
