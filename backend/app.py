"""Flask API for the stock analysis app.

Single primary endpoint, /api/analyze, returns candles, indicators, detected
patterns, trend, support/resistance, and an ML forecast in one payload so the
frontend can render everything from a single request.
"""
from __future__ import annotations

from flask import Flask, jsonify, request
from flask_cors import CORS

from services import (
    analysts as analysts_engine,
    backtest,
    candlesticks,
    checklist as checklist_engine,
    data,
    dipsignal,
    earnings as earnings_engine,
    extension as extension_engine,
    forecast,
    gaps as gaps_engine,
    indicators,
    insights,
    minervini,
    news as news_engine,
    patterns,
    pattern_read as pattern_read_engine,
    portfolio as portfolio_svc,
    quotes as quotes_engine,
    relative,
    resistance as resistance_engine,
    scanner as scanner_svc,
    sector as sector_engine,
    strategies as strategies_svc,
    signal as signal_engine,
    target as target_planner,
    trends,
    volume,
)

app = Flask(__name__)
CORS(app)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/portfolio", methods=["GET", "POST"])
def portfolio_view():
    analyze = request.args.get("analyze", "1") != "0"
    holdings, cash = None, None
    if request.method == "POST":
        body = request.get_json(silent=True) or {}
        holdings = body.get("holdings")  # [{ticker, shares, avg_cost}, ...]
        cash = body.get("cash")
    try:
        return jsonify(portfolio_svc.analyze_portfolio(holdings=holdings, cash=cash, analyze=analyze))
    except Exception as e:
        return jsonify({"error": f"Portfolio failed: {e}"}), 500


@app.get("/api/strategies")
def strategies_view():
    ticker = request.args.get("ticker", "").strip()
    period = request.args.get("period", "1y")
    if not ticker:
        return jsonify({"error": "Query param 'ticker' is required"}), 400
    try:
        return jsonify(strategies_svc.backtest_ticker(ticker, period=period))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Strategy test failed: {e}"}), 500


@app.get("/api/scan")
def scan_view():
    top_n = request.args.get("top", default=5, type=int)
    horizon_key = request.args.get("horizon", default="1m")
    try:
        return jsonify(scanner_svc.scan(top_n=max(1, min(top_n, 15)), horizon_key=horizon_key))
    except Exception as e:
        return jsonify({"error": f"Scan failed: {e}"}), 500


@app.get("/api/quote/<ticker>")
def api_quote(ticker):
    """Lightweight near-live quote for header polling (no full re-analyze)."""
    return jsonify(quotes_engine.fetch(ticker))


@app.get("/api/analyze")
def analyze():
    ticker = request.args.get("ticker", "").strip()
    period = request.args.get("period", "1y")
    interval = request.args.get("interval", "1d")
    horizon = request.args.get("horizon", default=10, type=int)
    order = request.args.get("order", default=5, type=int)

    if not ticker:
        return jsonify({"error": "Query param 'ticker' is required"}), 400

    try:
        df = data.fetch_ohlcv(ticker, period=period, interval=interval)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:  # network / yfinance failures
        return jsonify({"error": f"Failed to fetch data: {e}"}), 502

    # Long daily history (5y) for the multi-timeframe view, Minervini, and the
    # backtest — independent of the chart's period/interval. Cached, so repeated
    # requests don't re-hit Yahoo.
    try:
        daily = data.fetch_ohlcv(ticker, period="5y", interval="1d")
    except Exception:
        daily = df

    # Benchmark (SPY) for real relative strength. Skip if the ticker IS SPY.
    rs = None
    if ticker.upper() not in ("SPY", "^GSPC"):
        try:
            bench = data.fetch_ohlcv("SPY", period="5y", interval="1d")
            rs = relative.relative_strength(daily, bench)
        except Exception:
            rs = None

    try:
        ind = indicators.compute_all(df)
        pat = patterns.analyze(df, order=max(2, order))
        fc = forecast.forecast(df, horizon=horizon, interval=interval)
        mtf = trends.multi_timeframe(daily)
        candles_found = candlesticks.detect(df)
        vol = volume.analyze(df)
        mino = minervini.trend_template(daily, rs_excess=(rs["excess_pct"] if rs else None))
        bt = backtest.run(daily)
        ctx = {
            "ticker": ticker.upper(),
            "trend": pat["trend"],
            "multiTimeframe": mtf,
            "latest": ind["latest"],
            "levels": pat["levels"],
            "candlesticks": candles_found,
            "patterns": pat["patterns"],
            "volume": vol,
            "minervini": mino,
            "backtest": bt,
            "relativeStrength": rs,
        }
        sig = signal_engine.score(ctx)
        rec = insights.generate(ctx)
        plan = target_planner.plan(daily, horizon=5)
        dip = dipsignal.verdict(daily)
        res = resistance_engine.analyze(daily)
        sec = sector_engine.analyze(
            ticker, lambda tk: data.fetch_ohlcv(tk, period="3mo", interval="1d")["close"]
        )
        earn = earnings_engine.analyze(ticker, daily)
        pros = analysts_engine.snapshot(ticker, daily)
        gap = gaps_engine.analyze(daily)
        ext = extension_engine.analyze(daily)
        heads = news_engine.headlines(ticker)
        pread = pattern_read_engine.analyze(daily, chart_patterns=pat["patterns"])
        quote = quotes_engine.fetch(ticker)
        checklist = checklist_engine.build(
            dip=dip, resistance=res, sector=sec, ext=ext,
            earnings=earn, pros=pros, gap=gap, news=heads,
        )
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {e}"}), 500

    return jsonify(
        {
            "ticker": ticker.upper(),
            "meta": data.get_meta(ticker),
            "period": period,
            "interval": interval,
            "candles": data.to_candles(df),
            "indicators": ind["indicators"],
            "latest": ind["latest"],
            "trend": pat["trend"],
            "levels": pat["levels"],
            "patterns": pat["patterns"],
            "candlesticks": candles_found,
            "volume": vol,
            "minervini": mino,
            "forecast": fc,
            "multiTimeframe": mtf,
            "insights": rec,
            "backtest": bt,
            "signal": sig,
            "relativeStrength": rs,
            "tradePlan": plan,
            "dipSignal": dip,
            "resistance": res,
            "sectorPulse": sec,
            "earningsWatch": earn,
            "pros": pros,
            "gap": gap,
            "extension": ext,
            "headlines": heads,
            "checklist": checklist,
            "patternRead": pread,
            "quote": quote,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
