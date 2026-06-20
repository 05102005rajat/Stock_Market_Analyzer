# Evidence-Based Stock Analysis

A personal stock-analysis web app that does something most stock tools refuse to do: **it tells you honestly how much each signal is actually worth.** Every indicator is labeled by how well it holds up in rigorous, out-of-sample testing — and the app keeps a live scoreboard (the Signal Ledger) that scores its own calls forward against the market, so you can see what works instead of trusting a confident-looking arrow.

> **Not financial advice.** This is an educational tool. It describes price history and surfaces research-backed signals; it does not predict the future, and no signal here is a recommendation to buy or sell. Individual-stock outcomes over short horizons are dominated by noise.

---

## The one idea behind the whole app

Most charting tools present every indicator with equal confidence — a MACD cross looks as authoritative as an insider buying $2M of stock. The research says they are nowhere near equal. So this app sorts everything into two buckets and never lets you forget which is which:

- **Descriptive** signals summarize what price has *already* done (moving averages, MACD, RSI, Bollinger Bands, support/resistance, candlesticks). They are accurate descriptions and weak-to-useless predictors.
- **Predictive** signals have a real, replicated, out-of-sample edge with an economic mechanism behind them (momentum/relative strength, opportunistic insider buying, post-earnings drift, value, quality).

The flagship feature, the **Signal Ledger**, logs every directional call the app makes and scores it forward versus SPY at 5/21/63 days. Trust the scoreboard, not the label.

### Evidence hierarchy (what the app believes, and why)

| Signal | Descriptive or Predictive | Evidence | Where in the app |
|---|---|---|---|
| Momentum / relative strength | Predictive | **Strong** (Jegadeesh-Titman 1993; replicated 40+ markets) | Conviction Stack, Relative Strength |
| Opportunistic insider buying | Predictive | **Strong** (Cohen-Malloy-Pomorski 2012, ~82 bps/mo) | Insider card, Conviction Stack |
| Post-earnings-announcement drift | Predictive | **Strong** (Bernard-Thomas) | Earnings posture |
| Short-term mean reversion (oversold dip in uptrend) | Predictive | **Moderate** (regime-dependent) | Dip-buy card |
| Trend stage (Minervini template) | Predictive-ish | **Moderate** (a momentum read) | Conviction Stack, Minervini |
| ATR / volatility (for stops & sizing) | Descriptive | **Strong for its job** (no direction claim) | Sizing, Risk |
| Moving averages, golden/death cross | Descriptive | **Weak** as predictor | Chart, Trends |
| EMA/MACD crossover | Descriptive | **Weak** (~coin-flip after costs) | Crossover card |
| RSI, Bollinger Bands | Descriptive | **Weak** | Indicator panel |
| Support/Resistance, breakouts | Claimed predictive | **Weak** (high false-breakout rate) | Resistance card |
| Chart patterns (H&S, double top, cup&handle) | Claimed predictive | **Weak** (success rates overstated) | Pattern read |
| Candlestick patterns | Claimed predictive | **None demonstrated** | Candlesticks |

Key sources: Sullivan-Timmermann-White (1999), Park-Irwin (2007), Lo-Mamaysky-Wang (2000), Jegadeesh-Titman (1993), Cohen-Malloy-Pomorski (2012), McLean-Pontiff (2016).

---

## Quick start

```bash
bash start.sh        # macOS / Linux
```

This launches the Flask backend on `http://127.0.0.1:5001` and the Vite dev server on `http://localhost:5173`. First run creates a Python venv, installs `backend/requirements.txt`, and runs `npm install` for the frontend.

**Manual start** (or on Windows, where `start.sh` does not run):

```bash
# backend
cd backend
python -m venv venv
venv/Scripts/pip install -r requirements.txt      # Windows
venv/Scripts/python app.py                         # serves :5001

# frontend (second terminal)
cd frontend
npm install
npm run dev                                        # serves :5173
```

Open `http://localhost:5173`, type a ticker, and press Enter.

### Optional API keys (the app works fully without them)

| Variable | Enables | Without it |
|---|---|---|
| `FINNHUB_API_KEY` | Real next-earnings dates + the earnings run-up flag | Earnings card shows a proxy/caveat |
| `SEC_USER_AGENT` (`"Name email@example.com"`) | Live SEC EDGAR Form 4 insider data | Insider card unavailable |

Set them in your shell before `start.sh`, e.g. `export FINNHUB_API_KEY=...`.

---

## Features

### Evidence-backed signals (the ones that count)

- **Conviction Stack** *(new)* — the "best combo." Aggregates the *independent, evidence-backed* signals (momentum, insider buying, trend stage) into one read, each tagged with its evidence strength. Chart signals are shown but **weighted zero** so you can see the gap. A hot pre-earnings run-up appears as an honest **caution** that lowers conviction (the "priced-in / sell-the-news" risk — the Broadcom/Palo-Alto/Micron pattern). Combining *independent* signals is the only kind of "combo" with academic support; stacking correlated chart indicators just overfits.
- **Relative Strength / Momentum** — the stock vs SPY over a lookback. The single best-supported price-based effect (winners tend to persist), with crash-risk caveats noted.
- **Insider (Form 4)** — parses *actual* open-market purchases (transaction code P) vs sells and routine trades, with share counts and dollar values; flags C-suite and cluster buying. The cleanest free "smart money" signal.
- **Dip-buy** — the one mean-reversion signal with a measured edge: buy an oversold pullback *in an uptrend*. Shows the stock's own historical bounce rate, a buy/target/stop, and refuses to fire in a downtrend (no catching falling knives).
- **Earnings posture** — days to next earnings and a "hot run-up into earnings" caution (expectations may be priced in).

### Descriptive context (useful to see, weak to bet on)

- **EMA/MACD Crossover** *(new)* — your custom EMA ribbon (55/89/204) + MACD (13/34/9) with the zero-line and signal-line crosses and a combined BUY/SELL state. Clearly labeled as a **late trend-follower**: a point-in-time backtest in `backend/crossover_breakout_test.py` found it would have missed 8 of 10 of a sample portfolio's biggest surges and showed *negative* lift over the base rate for catching breakouts. Logged to the ledger so its real accuracy is measured forward.
- **Resistance / base rates**, **Gaps**, **Extension** (stretched vs the mean), **Sector Pulse**, **Pattern Read**, **Multi-timeframe Trends**, **Candlesticks**, **Volume** — each with honest "no edge found / descriptive only" disclosures.

### Risk & sizing (where a small account gains the most)

- **Position Sizing** — ATR-based stop distance and fixed-fractional sizing, so each trade risks a set % of the account. Returns "unavailable" on flat/illiquid data rather than dividing by zero.
- **Portfolio X-ray** — ETF look-through and AI/semiconductor concentration flags.

### The Signal Ledger (flagship honesty feature)

Every directional call (resistance breakout, dip-buy, pattern tilt, earnings run-up, EMA/MACD crossover, **and the conviction stack**) is logged on the day it fires, de-duplicated, then scored forward vs SPY at 5/21/63 days. The ledger tab shows the running calibration so you can judge each signal's *real* out-of-sample accuracy on your own tickers — the honest answer to "does this actually work?"

### Charting & UX

Pro candlestick chart (TradingView lightweight-charts) with a volume pane, live OHLC crosshair readout, and magnet crosshair; **drawing tools** (horizontal/trend lines, Fibonacci retracement, persisted per-ticker); split view and two-ticker compare; ⌘K command palette; quick-switch chip row; **Plain English** mode with glossary tooltips; on-demand forecast track record.

---

## Architecture

```
backend/                Flask API (Python)
  app.py                /api/analyze assembles every engine into one payload
  services/             one engine per signal, each self-contained:
    conviction.py         evidence-backed signal aggregator   (NEW)
    crossover.py          EMA ribbon + MACD crossover system  (NEW)
    relative.py           relative strength / momentum
    insiders.py           SEC Form 4 buy/sell parser
    dipsignal.py          oversold-in-uptrend mean reversion
    earnings.py           next-earnings + hot run-up flag
    ledger.py             the Signal Ledger (log + forward-score)
    minervini.py, trends.py, resistance.py, gaps.py, extension.py,
    sector.py, patterns.py, candlesticks.py, volume.py, indicators.py,
    risk.py, portfolio.py, forecast.py, signal.py, quotes.py, ...
  *_test.py             research/backtest scripts (point-in-time, no lookahead)
  tests/                pytest suite (134 tests)

frontend/               React + Vite
  src/components/        one card per engine:
    ConvictionCard.jsx    evidence-backed stack with strength badges (NEW)
    CrossoverCard.jsx     EMA/MACD signal + honest caveat (NEW)
    DipSignal.jsx, InsiderCard.jsx, Resistance.jsx, Ledger.jsx,
    PriceChart.jsx, Sidebar.jsx, Plain.jsx, CommandPalette.jsx, ...
```

**Request flow:** the frontend calls `/api/analyze?ticker=XYZ`; `app.py` fetches OHLCV, runs every engine, assembles a single JSON payload, logs any directional signals to the ledger, and returns it; `Sidebar.jsx` renders one card per engine.

### Data & caching

Price data comes from Yahoo (via `yfinance`), ~15-minute delayed, with an in-process TTL cache. Several research scripts read a frozen point-in-time snapshot (`.resistance_cache.pkl`, ~80 large-caps, 10y daily) so base-rate cards are reproducible. Live quotes fall back to the cache if Yahoo throttles. `node_modules`, `venv`, `dist`, `*.pkl`, and the ledger DB are excluded from the zip — restore them with `npm install` + `pip install -r requirements.txt`.

---

## Testing

```bash
cd backend
python -m pytest -q          # 134 tests
```

Backtests are point-in-time (causal indicators, forward returns from the future bar) to avoid lookahead bias. Run the crossover breakout study directly:

```bash
python crossover_breakout_test.py
```

---

## Honest limitations

- No indicator here reliably predicts breakouts or short-term moves in advance — confirmed breakouts still fail often, and "it broke resistance so it will run" is one of the least reliable rules in retail trading.
- Even the predictive signals decay after publication (McLean-Pontiff 2016) and momentum suffers occasional violent crashes.
- The strongest edge for a small account is **risk management and diversification**, not entry timing.
- This is educational software, not financial advice.
