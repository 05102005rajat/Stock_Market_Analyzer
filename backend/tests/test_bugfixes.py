"""Regression tests for bugs found in the codebase review (keep them fixed)."""
import numpy as np
import pandas as pd

from conftest import make_df
from services import forecast, insights, patterns, relative


def _df(closes):
    idx = pd.bdate_range("2022-01-03", periods=len(closes))
    c = np.asarray(closes, float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1}, index=idx)


def test_relative_guards_zero_stock_close():
    # A zero/NaN stock close at the lookback bar must return None, not inf/NaN
    # (which would corrupt the whole /analyze JSON via Flask jsonify).
    stock = np.linspace(100, 150, 200)
    stock[200 - 126] = 0.0
    rs = relative.relative_strength(_df(stock), _df(np.linspace(100, 120, 200)))
    assert rs is None
    stock2 = np.linspace(100, 150, 200)
    stock2[-1] = np.nan
    assert relative.relative_strength(_df(stock2), _df(np.linspace(100, 120, 200))) is None


def test_insights_absent_macd_does_not_vote_bearish():
    # Empty / MACD-less context should be NEUTRAL, not biased bearish by absent data.
    out = insights.generate({})
    assert out["bias"] == "neutral"
    # And no fabricated MACD footnote when MACD is missing.
    assert not any("MACD" in r["title"] for r in out["recommendations"])


def test_patterns_handle_empty_dataframe():
    empty = _df([])
    assert patterns.trend(empty)["direction"] == "sideways"   # no IndexError
    assert patterns.detect_patterns(empty) == []              # no ValueError


def test_future_dates_no_off_by_one_for_nonbusiness_last():
    # Last index a Sunday: the first real forecast day (Mon) must NOT be dropped.
    idx = pd.DatetimeIndex([pd.Timestamp("2023-06-16"), pd.Timestamp("2023-06-18")])
    fd = forecast._future_dates(idx, 3, "1d")
    assert fd[0] == pd.Timestamp("2023-06-19")  # Monday, not skipped
    assert len(fd) == 3 and all(d.weekday() < 5 for d in fd)


def _post(client, body):
    return client.post("/api/portfolio?analyze=0", json=body)


def test_validator_coerces_numeric_strings(monkeypatch):
    # JSON may legitimately carry "10" rather than 10. Testing float() without
    # keeping the result let the string reach `shares * price` and 500.
    import app as flask_app
    from services import data, portfolio

    holdings = [{"ticker": "AAPL", "shares": "10", "avg_cost": "180"}]
    assert flask_app._validate_holdings(holdings) is None
    assert holdings[0]["shares"] == 10.0 and holdings[0]["avg_cost"] == 180.0
    # ...and the coerced payload must survive the arithmetic that used to raise.
    monkeypatch.setattr(data, "fetch_ohlcv", lambda t, **kw: make_df([100.0] * 30))
    monkeypatch.setattr(portfolio, "_fund_holdings", lambda t: None)
    row = portfolio.value_holdings(holdings, analyze=False)[0]
    assert row["value"] == 1000.0 and row["cost"] == 1800.0


def test_validator_rejects_non_finite_and_negative_shares():
    import app as flask_app
    c = flask_app.app.test_client()
    for bad in (float("nan"), float("inf")):
        r = _post(c, {"holdings": [{"ticker": "AAPL", "shares": bad}]})
        assert r.status_code == 400 and "non-finite" in r.get_json()["error"]
    r = _post(c, {"holdings": [{"ticker": "AAPL", "shares": -5}]})
    assert r.status_code == 400 and "negative" in r.get_json()["error"]


def test_bad_cash_is_a_400_not_a_500_or_nan():
    # 'cash' went straight to float() inside the service: a string raised
    # (reported as a 500) and a NaN reached jsonify as a bare NaN token.
    import app as flask_app
    c = flask_app.app.test_client()
    for bad in ("abc", float("nan"), float("inf")):
        r = _post(c, {"holdings": [], "cash": bad})
        assert r.status_code == 400, bad
        assert "'cash'" in r.get_json()["error"]


def test_negative_cash_is_allowed_for_margin_accounts():
    # A margin account carries a debit balance; rejecting it would block a
    # real account shape. Negative SHARES are still refused.
    import app as flask_app
    c = flask_app.app.test_client()
    r = _post(c, {"holdings": [], "cash": -250.0})
    assert r.status_code == 200


def test_non_object_body_is_a_400_not_an_html_500():
    import app as flask_app
    c = flask_app.app.test_client()
    r = _post(c, [{"ticker": "AAPL", "shares": 1}])
    assert r.status_code == 400 and r.is_json
