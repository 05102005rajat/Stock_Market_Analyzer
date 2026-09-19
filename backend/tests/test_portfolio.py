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


def test_concentration_ignores_cash_and_residual_in_denominator(monkeypatch):
    # A cash-heavy account with one small stock position must NOT explode
    # effective_n — HHI should be computed over the resolved single-name
    # exposure only, not diluted by cash/residual sitting in `total`.
    monkeypatch.setattr(portfolio, "_fund_holdings", lambda t: None)
    monkeypatch.setattr(portfolio, "_stock_sector", lambda t: "Technology")
    rows = [{"ticker": "AAPL", "value": 180.0}]
    c = portfolio.look_through(rows, cash=100000.0)["concentration"]
    assert abs(c["hhi"] - 1.0) < 1e-9        # one identified bet -> maximally concentrated
    assert abs(c["effective_n"] - 1.0) < 1e-9


def test_concentration_none_when_nothing_resolved():
    # All-cash account (or nothing identifiable): no division by zero, no crash.
    lt = portfolio.look_through([], cash=500.0)
    assert lt["concentration"]["hhi"] is None
    assert lt["concentration"]["effective_n"] is None


def test_failed_ticker_row_is_identifiable_via_error(monkeypatch):
    # A holding whose price fetch fails must still carry an 'error' flag so
    # callers (analyze_portfolio's failed_tickers) can warn instead of just
    # silently dropping it from every total.
    def fake_fetch(ticker, **kw):
        if ticker == "BADTICKER":
            raise RuntimeError("no data")
        return pd.DataFrame({"close": _series(np.linspace(100, 110, 60))})
    monkeypatch.setattr(portfolio.data, "fetch_ohlcv", fake_fetch)
    monkeypatch.setattr(portfolio, "_fund_holdings", lambda t: None)
    rows = portfolio.value_holdings(
        [{"ticker": "AAPL", "shares": 1, "avg_cost": 100}, {"ticker": "BADTICKER", "shares": 5, "avg_cost": 100}],
        analyze=False,
    )
    failed = [r["ticker"] for r in rows if r.get("error")]
    assert failed == ["BADTICKER"]
    bad = next(r for r in rows if r["ticker"] == "BADTICKER")
    assert "value" not in bad


def test_hhi_counts_etf_residual_as_diversified(monkeypatch):
    # A fund reporting only its top holdings leaves a residual that IS invested,
    # spread across the names it doesn't list. Excluding it from the denominator
    # made a pure index-fund account read as ~7 effective bets.
    monkeypatch.setattr(
        portfolio, "_fund_holdings",
        lambda t: {"AAPL": 0.07, "MSFT": 0.06, "NVDA": 0.06} if t == "VOO" else None,
    )
    monkeypatch.setattr(portfolio, "_fund_sectors", lambda t: None)
    monkeypatch.setattr(portfolio, "_stock_sector", lambda t: "Tech")
    lt = portfolio.look_through([{"ticker": "VOO", "value": 1000.0}], cash=0.0)
    # 19% resolves to three names; the other 81% is the diversified residual.
    assert lt["residual_diversified_pct"] == 81.0
    # Weights are over everything invested, so effective_n reflects the residual.
    assert lt["concentration"]["effective_n"] > 20


def test_hhi_ignores_cash_but_not_residual(monkeypatch):
    # Cash must stay out of the denominator: adding it may not change how
    # concentrated the equity sleeve is.
    monkeypatch.setattr(portfolio, "_fund_holdings", lambda t: None)
    monkeypatch.setattr(portfolio, "_fund_sectors", lambda t: None)
    monkeypatch.setattr(portfolio, "_stock_sector", lambda t: "Tech")
    rows = [{"ticker": "AAPL", "value": 500.0}, {"ticker": "MSFT", "value": 500.0}]
    no_cash = portfolio.look_through(rows, cash=0.0)["concentration"]
    with_cash = portfolio.look_through(rows, cash=9000.0)["concentration"]
    assert no_cash["effective_n"] == with_cash["effective_n"] == 2.0


def test_single_name_is_maximally_concentrated(monkeypatch):
    monkeypatch.setattr(portfolio, "_fund_holdings", lambda t: None)
    monkeypatch.setattr(portfolio, "_fund_sectors", lambda t: None)
    monkeypatch.setattr(portfolio, "_stock_sector", lambda t: "Tech")
    lt = portfolio.look_through([{"ticker": "AAPL", "value": 1000.0}], cash=0.0)
    assert lt["concentration"]["hhi"] == 1.0
    assert lt["concentration"]["effective_n"] == 1.0
