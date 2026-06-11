import { useEffect, useState } from "react";
import { analyze, getPortfolio, savePortfolio, getScan } from "./api";
import PriceChart from "./components/PriceChart";
import IndicatorPanel from "./components/IndicatorPanel";
import Sidebar from "./components/Sidebar";
import Compare from "./components/Compare";
import Alerts from "./components/Alerts";
import Portfolio from "./components/Portfolio";
import Scan from "./components/Scan";
import Help from "./components/Help";
import StrategyLab from "./components/StrategyLab";

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"];
const INTERVALS = [
  ["1h", "Hourly"],
  ["1d", "Daily"],
  ["1wk", "Weekly"],
  ["1mo", "Monthly"],
];
// Sensible default span when switching to a coarser candle interval.
const DEFAULT_PERIOD_FOR_INTERVAL = { "1h": "1mo", "1d": "1y", "1wk": "2y", "1mo": "max" };
const TOGGLE_DEFS = [
  ["ma", "Moving Avgs"],
  ["bollinger", "Bollinger"],
  ["trend", "Trend line"],
  ["levels", "S/R levels"],
  ["patterns", "Chart patterns"],
  ["candles", "Candlesticks"],
  ["forecast", "Forecast"],
];

export default function App() {
  const [ticker, setTicker] = useState("AAPL");
  const [compareTicker, setCompareTicker] = useState("");
  const [period, setPeriod] = useState("1y");
  const [interval, setIntervalSel] = useState("1d");
  const [horizon, setHorizon] = useState(10);
  const [data, setData] = useState(null);
  const [compareData, setCompareData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [mode, setMode] = useState("analyze"); // "analyze" | "portfolio"
  const [portfolio, setPortfolio] = useState(null);
  const [pfLoading, setPfLoading] = useState(false);
  const [pfError, setPfError] = useState(null);
  const [scanData, setScanData] = useState(null);
  const [scanLoading, setScanLoading] = useState(false);
  const [scanError, setScanError] = useState(null);
  const [scanHorizon, setScanHorizon] = useState("1m");
  // {times:[], levels:[], key} — the bars/levels a clicked signal is based on.
  const [focus, setFocus] = useState(null);
  // Start the chart clean (just price + moving-average lines). The user can
  // switch on trend/levels/forecast/patterns from the chips when they want them.
  const [toggles, setToggles] = useState({
    ma: true,
    bollinger: false,
    trend: false,
    levels: false,
    patterns: false,
    candles: false,
    forecast: false,
  });

  const run = async (e, tickerOverride) => {
    e?.preventDefault();
    const tk = (tickerOverride || ticker).trim();
    if (!tk) return;
    setLoading(true);
    setError(null);
    const safeHorizon = Math.min(60, Math.max(1, Number.isFinite(horizon) ? horizon : 10));
    const params = { period, interval, horizon: safeHorizon };
    try {
      const result = await analyze({ ticker: tk, ...params });
      setData(result);
      setFocus(null);
      if (compareTicker.trim()) {
        try {
          setCompareData(await analyze({ ticker: compareTicker.trim(), ...params }));
        } catch {
          setCompareData(null);
        }
      } else {
        setCompareData(null);
      }
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh: re-analyze ~60s after each completed load while enabled.
  useEffect(() => {
    if (!autoRefresh || !data) return;
    const id = window.setInterval(() => run(), 60000);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, data, ticker, compareTicker, period, interval, horizon]);

  const toggle = (key) => setToggles((t) => ({ ...t, [key]: !t[key] }));

  const loadPortfolio = async () => {
    setPfLoading(true);
    setPfError(null);
    try {
      // Use the user's saved edits if present, otherwise the server default.
      const saved = JSON.parse(localStorage.getItem("pf.config") || "null");
      const result = saved ? await savePortfolio(saved.holdings, saved.cash) : await getPortfolio();
      setPortfolio(result);
    } catch (err) {
      setPfError(err.message);
    } finally {
      setPfLoading(false);
    }
  };

  // Save edited holdings/cash → persist + recompute.
  const savePf = async (holdings, cash) => {
    localStorage.setItem("pf.config", JSON.stringify({ holdings, cash }));
    setPfLoading(true);
    setPfError(null);
    try {
      setPortfolio(await savePortfolio(holdings, cash));
    } catch (err) {
      setPfError(err.message);
    } finally {
      setPfLoading(false);
    }
  };

  // Click a holding → jump to its full single-stock analysis.
  const pick = (t) => {
    setTicker(t);
    setMode("analyze");
    run(null, t);
  };

  const loadScan = async (horizon = scanHorizon) => {
    setScanHorizon(horizon);
    setScanLoading(true);
    setScanError(null);
    try {
      setScanData(await getScan(horizon));
    } catch (err) {
      setScanError(err.message);
    } finally {
      setScanLoading(false);
    }
  };

  useEffect(() => {
    if (mode === "portfolio" && !portfolio && !pfLoading) loadPortfolio();
    if (mode === "scan" && !scanData && !scanLoading) loadScan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>📈 Stock Pattern &amp; Trend Analyzer</h1>
          <div className="mode-toggle">
            <button className={`chip ${mode === "analyze" ? "on" : ""}`} onClick={() => setMode("analyze")}>Analyze</button>
            <button className={`chip ${mode === "portfolio" ? "on" : ""}`} onClick={() => setMode("portfolio")}>My Portfolio</button>
            <button className={`chip ${mode === "scan" ? "on" : ""}`} onClick={() => setMode("scan")}>Buy Zones</button>
            <button className={`chip ${mode === "strategies" ? "on" : ""}`} onClick={() => setMode("strategies")}>🧪 Strategy Lab</button>
            <button className={`chip ${mode === "help" ? "on" : ""}`} onClick={() => setMode("help")}>❓ Help</button>
          </div>
        </div>
        <form className="search" onSubmit={run} style={{ display: mode === "analyze" ? "flex" : "none" }}>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="Ticker e.g. AAPL"
            spellCheck={false}
          />
          <input
            className="cmp-input"
            value={compareTicker}
            onChange={(e) => setCompareTicker(e.target.value.toUpperCase())}
            placeholder="vs (compare)"
            spellCheck={false}
            title="Optional second ticker to compare"
          />
          <select
            value={interval}
            onChange={(e) => {
              const iv = e.target.value;
              setIntervalSel(iv);
              setPeriod(DEFAULT_PERIOD_FOR_INTERVAL[iv] || period);
            }}
            title="Candle interval"
          >
            {INTERVALS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
          <select value={period} onChange={(e) => setPeriod(e.target.value)} title="History length">
            {PERIODS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <label className="horizon">
            Forecast
            <input
              type="number"
              min="1"
              max="60"
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
            />
            bars
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Analyzing…" : "Analyze"}
          </button>
        </form>
      </header>

      {mode === "portfolio" && (
        <Portfolio
          data={portfolio}
          loading={pfLoading}
          error={pfError}
          onPick={pick}
          onSave={savePf}
          onReload={() => { localStorage.removeItem("pf.config"); setPortfolio(null); loadPortfolio(); }}
        />
      )}

      {mode === "help" && <Help />}

      {mode === "strategies" && <StrategyLab onPick={pick} />}

      {mode === "scan" && (
        <Scan
          data={scanData}
          loading={scanLoading}
          error={scanError}
          horizon={scanHorizon}
          onHorizon={(h) => loadScan(h)}
          onPick={pick}
          onReload={() => { setScanData(null); loadScan(); }}
        />
      )}

      {mode === "analyze" && error && <div className="error">⚠ {error}</div>}

      {mode === "analyze" && !data && !error && (
        <div className="empty">
          Enter a ticker and hit <b>Analyze</b> for a technical posture with confidence, indicators,
          detected chart &amp; candlestick patterns, a backtest, and a calibrated forecast — or open
          <b> My Portfolio</b> to see your holdings and true look-through exposure.
        </div>
      )}

      {mode === "analyze" && data && (
        <>
          <div className="toolbar">
            <div className="title">
              <b>{data.ticker}</b>
              <span className="dim">{data.meta.name}</span>
            </div>
            <div className="toggles">
              <label className="auto" title="Re-analyze every 60s">
                <input type="checkbox" checked={autoRefresh} onChange={(e) => setAutoRefresh(e.target.checked)} />
                Auto-refresh
              </label>
              {TOGGLE_DEFS.map(([key, label]) => (
                <button
                  key={key}
                  className={`chip ${toggles[key] ? "on" : ""}`}
                  onClick={() => toggle(key)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {compareData && <Compare a={data} b={compareData} onClose={() => { setCompareData(null); setCompareTicker(""); }} />}

          {focus && (
            <div className="focus-bar">
              <span>◎ Highlighting what this signal is based on</span>
              <button className="chip" onClick={() => setFocus(null)}>Clear highlight</button>
            </div>
          )}
          <div className="layout">
            <main className="main">
              <PriceChart data={data} toggles={toggles} focus={focus} intraday={interval === "1h"} />
              <IndicatorPanel data={data} />
              <Alerts data={data} ticker={data.ticker} />
            </main>
            <Sidebar data={data} focus={focus} onFocus={setFocus} />
          </div>
        </>
      )}
    </div>
  );
}
