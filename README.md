# 📈 Stock Pattern & Trend Analyzer

Enter a ticker → get live price data, technical indicators, automatically
detected chart patterns, trend classification, support/resistance levels, and a
short-horizon machine-learning price forecast — all on one interactive chart.

> ⚠️ Educational tool only. Nothing here is investment advice.

## Stack

| Layer    | Tech |
|----------|------|
| Data     | [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance) |
| Backend  | Flask + pandas / numpy / scipy / scikit-learn |
| Frontend | React + Vite + TradingView [lightweight-charts](https://github.com/tradingview/lightweight-charts) |

## Buy Zones (entry scanner, NOT a winner picker)

A **Buy Zones** mode ranks a fixed universe (your holdings + watchlist + curated
liquid names) by a transparent "buy-the-dip-in-an-uptrend" rule — oversold RSI
*gated* behind a 200-DMA uptrend + positive relative strength — and attaches a
calibrated buy zone / take-profit / stop / green-exit odds to each.

**It does not predict winners, and the app says so loudly.** Backtested
point-in-time (`scanner_backtest.py`, 28 names, 5y): the top-5 by setup score beat
buy-and-hold by only +0.43%/pick at 21d (t = 1.41, *not* significant), and at 5d
the bottom-5 beat the top-5. So it's an **entry-discipline / position-timing**
tool for names you already want — never a "5 stocks that will go up" oracle,
because direction is a coin flip.

## My Portfolio (look-through X-ray)

A **Portfolio** mode (toggle in the header) reads your holdings from
`backend/holdings.json` (ticker, shares, average cost) and shows what you own,
cost vs current value and P/L, a light per-holding read (trend + the weekly
vol-scaled target), and — the headline — an **ETF look-through X-ray**: it
resolves VOO/QQQ/SPYM into their constituents so you see your *true* single-name
exposure. (On the sample book: direct weights suggest ~36% in individual stocks,
but look-through reveals the true top-3 — GOOGL/AAPL/NVDA — is **~47%** of the
account and mega-cap tech **~57%**.) Plus portfolio volatility (correlation-aware).
Click any holding to jump to its full single-stock analysis. Purely descriptive —
concentration and risk *measurement*, never return predictions.

## Headline: technical posture (honestly measured)

A composite **posture** score on −100…+100 (Strongly Bearish … Strongly Bullish)
that blends every read below (trend, multi-timeframe alignment, 50/200 regime,
RSI, MACD, Minervini stage, candlesticks, volume, chart patterns, **real relative
strength vs SPY**) with a confidence interval and a full factor breakdown.

**It describes current structure — it does NOT predict returns, and the app says so.**
A walk-forward study (`backend/signal_study.py`, 15 large-caps, 5y incl. the 2022
bear, 4,680 point-in-time samples) found **no forward-return edge**: 20-day returns
after a bullish posture (+2.1%) were actually *lower* than after a bearish one
(+2.8%), and a fitted model scored no better than the base rate out-of-sample. That
finding is surfaced right in the gauge, so posture is never mistaken for a forecast.
This is the honest result for price-derived signals on liquid large-caps — and the
tool is built to tell you the truth rather than sell a confident lie.

The **forecast** is likewise framed as a *calibrated range* (the band covers ~95%
out-of-sample; the centre line does not beat naive on direction — use the cone).

### Weekly trade plan (the part that actually works)

Direction is a coin flip, but the weekly *range* is stable and estimable. The
**Weekly Trade Plan** asks the better question — "if you buy today, how likely is
a profitable exit within a week, and at what target?" — from the empirical
distribution of the 5-day maximum favorable/adverse excursion. Backtested
point-in-time (`backend/target_backtest.py`, 2,536 samples, 8 tickers):

- a **volatility-scaled take-profit is hit ~64%** of weeks across *every* ticker
  (SPY's target is +0.9%, NVDA's is +3.2%, yet both hit ~64% — the probability is
  portable even though the level adapts),
- a **fixed +3% target is not portable** (67% on NVDA, 15% on SPY),
- a **profitable exit was available in ~94%** of weeks.

So the app gives a calibrated take-profit / stretch / stop with their historical
hit rates — a risk/reward framework, not a prediction.

Plus: **compare two tickers** side-by-side, and **alerts** (RSI/price/posture/
Stage-2/cross conditions) re-checked on an optional 60-second auto-refresh.

> None of this is investment advice — it's a transparent, self-auditing technical study.

### Volatility model (the part that's genuinely predictable)

Direction is a coin flip, but volatility clusters and is forecastable. A blended
estimator — **50/50 Yang-Zhang(OHLC range) + RiskMetrics EWMA** (`services/volatility.py`)
— feeds both the forecast bands and the trade plan. Backtested point-in-time
(`vol_backtest.py`, 8 tickers/5y): **QLIKE 0.41 vs 0.49** for close-to-close
(~15% better), coverage 94% vs 92.7%.

**Per-stock tail adaptation (not hard-coded categories).** A category study
(`category_study.py`) showed vol *level* differs 3× across categories (already
auto-scaled by the blend) and *tail fatness* differs too (kurtosis 0.6 for indices
→ 3.0 for high-vol growth). So the band multiplier **adapts to each stock's own
measured 95th-percentile move** (indices ~1.96, fat-tailed names ~2.1+), which
lands coverage on **95.2%** vs 92.7% — more robust than discrete categories since
a stock that changes character adapts automatically.

### Evaluation harnesses
- `backend/validate_week.py` — train-through-Wednesday, test Thu/Fri out-of-sample.
- `backend/walkforward.py` — point-in-time forecast & signal eval vs naive baselines.
- `backend/multi_week.py` — rolls the weekly test across N weeks; charts Monday hit rate.
- `backend/signal_study.py` — multi-ticker, multi-regime component edge diagnosis + walk-forward fit.
- `backend/target_backtest.py` — weekly trade-plan target calibration.
- `backend/vol_backtest.py` / `band_backtest.py` / `category_study.py` — volatility model selection, band coverage/sharpness, and per-category tail analysis.

## What it computes

- **Indicators** — SMA 20/50, EMA 12/26, RSI(14), MACD(12,26,9), Bollinger Bands.
- **Trend** — linear-regression slope of close → uptrend / downtrend / sideways, with an R² confidence.
- **Multi-timeframe trend** (the "read it like an expert" view) — direction + % change over **1W / 1M / 3M / 6M / 1Y**, an alignment verdict ("every timeframe aligned" vs "choppy"), and the long-term regime via the **50/200-day SMAs** (golden/death cross). Computed from a consistent daily history regardless of the chart's zoom.
- **Daily / Weekly / Monthly candles** — switch the interval to view anything from a few months to decades of price action.
- **Support / Resistance** — swing highs/lows clustered into price levels, ranked by how often they were touched.
- **Chart patterns** — Double Top / Double Bottom, Head & Shoulders, Inverse Head & Shoulders, and Ascending / Descending / Symmetrical Triangles (from local extrema + swing trend-lines).
- **Candlestick patterns** — 17 classics: Doji, Hammer, Inverted Hammer, Hanging Man, Shooting Star, Bullish/Bearish Marubozu, Bullish/Bearish Engulfing, Bullish/Bearish Harami, Piercing Line, Dark Cloud Cover, Morning/Evening Star, Three White Soldiers, Three Black Crows.
- **Minervini Trend Template** — Mark Minervini's 8-point stage-analysis screen with a pass/fail scorecard and a Weinstein-style stage (1–4).
- **Volume signals** — volume spikes, dry-ups, volume-confirmed breakouts/breakdowns, and OBV trend.
- **Insight engine** — a situation-aware "what to watch" panel: reads the trend/regime/momentum/levels/candles/volume together and emits prioritized, plain-English recommendations tailored to whether the stock is going up, down, or chopping. Click any recommendation or signal to **highlight the exact bars/levels it's based on** and zoom the chart there.
- **Pattern backtester** — for THIS stock, measures how often each candlestick pattern was followed by a favorable move (5/10/20 bars) vs the unconditional baseline, so you can see which signals actually carried an edge.
- **Forecast** — a `GradientBoostingRegressor` trained on lagged log-returns, rolled forward recursively over **business days**, with a confidence band and honest out-of-sample metrics: directional accuracy, a **majority-class baseline to compare against**, and RMSE.

> On daily price data the forecast's directional accuracy typically sits near
> the baseline (~0.5) — that's expected; daily moves are close to unpredictable.
> The baseline column is there precisely so you can see whether the model beats
> a coin flip. Treat it as a teaching tool, not a signal.

## Project layout

```
backend/
  app.py                 Flask API — GET /api/analyze
  services/
    data.py              yfinance fetch + OHLCV serialization
    indicators.py        SMA/EMA/RSI/MACD/Bollinger
    patterns.py          chart patterns: triangles, double tops, H&S
    candlesticks.py      17 candlestick patterns
    minervini.py         Minervini Trend Template scorecard
    volume.py            volume spikes, dry-ups, breakouts, OBV
    trends.py            multi-timeframe trend + 50/200 SMA regime
    forecast.py          ML forecast
    insights.py          situation-aware recommendation engine (+ chart anchors)
    backtest.py          historical edge of each candlestick pattern
    signal.py            composite technical-posture score + confidence interval
    relative.py          relative strength vs SPY benchmark
    target.py            weekly trade plan: calibrated targets + probabilities
    volatility.py        blended OHLC/EWMA vol + per-stock tail-adaptive bands
  tests/                 pytest suite (network-free)
  requirements.txt
frontend/
  src/
    App.jsx              layout, controls, overlay toggles
    api.js               fetch client
    components/
      PriceChart.jsx     candles + all overlays
      IndicatorPanel.jsx RSI + MACD oscillators
      Sidebar.jsx        analytics summary
```

## Run it

### 1. Backend (terminal 1)

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py          # serves http://127.0.0.1:5001
```

### 2. Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev                        # serves http://localhost:5173
```

Open **http://localhost:5173**, type a ticker (e.g. `AAPL`), and click **Analyze**.

Or just run `./start.sh` from the project root to launch both.

## API

```
GET /api/analyze?ticker=AAPL&period=1y&interval=1d&horizon=10
```

| param    | values | default |
|----------|--------|---------|
| ticker   | any Yahoo symbol | — (required) |
| period   | 1mo 3mo 6mo 1y 2y 5y 10y max | 1y |
| interval | 1d 1wk 1mo | 1d |
| horizon  | forecast bars (1–60) | 10 |

The response also includes a `multiTimeframe` block (`horizons`, `alignment`,
`regime`) for the long-term trend view.

## Tests

```bash
cd backend
./venv/bin/python -m pytest tests/ -q     # 22 tests, no network needed
```

Returns one JSON payload with `candles`, `indicators`, `trend`, `levels`,
`patterns`, and `forecast`.

## Ideas to extend

- Swap the forecast model for an LSTM (TensorFlow/PyTorch) and compare metrics.
- Add more patterns (triangles, flags, cup-and-handle, wedges).
- Backtest pattern signals to measure historical edge.
- Cache yfinance responses (Redis) to avoid rate limits.
