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
import Ledger from "./components/Ledger";
import CommandPalette from "./components/CommandPalette";

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"];
const INTERVALS = [
  ["1h", "Hourly"],
  ["1d", "Daily"],
  ["1wk", "Weekly"],
  ["1mo", "Monthly"],
];
const INTERVAL_LABEL = Object.fromEntries(INTERVALS);
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
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [plainMode, setPlainMode] = useState(() => {
    try { return localStorage.getItem("plainMode") === "1"; } catch { return false; }
  });
  const [splitTf, setSplitTf] = useState(null); // second timeframe interval, e.g. "1wk"
  const [splitData, setSplitData] = useState(null);
  const togglePlain = () => setPlainMode((v) => {
    const nv = !v;
    try { localStorage.setItem("plainMode", nv ? "1" : "0"); } catch { /* ignore */ }
    return nv;
  });
  const [recentTickers, setRecentTickers] = useState(() => {
    try { return JSON.parse(localStorage.getItem("recentTickers") || "[]"); } catch { return []; }
  });
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

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    // Preload holdings once so owned tickers appear in the palette & quick-switch
    // even before the user opens the Portfolio tab.
    if (!portfolio && !pfLoading) loadPortfolio();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const run = async (e, tickerOverride, splitOverride) => {
    e?.preventDefault();
    const tk = (tickerOverride || ticker).trim();
    if (!tk) return;
    const effectiveSplit = splitOverride !== undefined ? splitOverride : splitTf;
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
      // Split timeframe: same ticker, a second interval, side-by-side.
      if (effectiveSplit) {
        try {
          const splitPeriod = DEFAULT_PERIOD_FOR_INTERVAL[effectiveSplit] || "2y";
          setSplitData(await analyze({ ticker: tk, period: splitPeriod, interval: effectiveSplit, horizon: safeHorizon }));
        } catch {
          setSplitData(null);
        }
      } else {
        setSplitData(null);
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
  const pushRecent = (t) => {
    setRecentTickers((prev) => {
      const next = [t, ...prev.filter((x) => x !== t)].slice(0, 10);
      try { localStorage.setItem("recentTickers", JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  };

  const pick = (t) => {
    const up = (t || "").toUpperCase();
    setTicker(up);
    setMode("analyze");
    pushRecent(up);
    run(null, up);
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

  const ownedTickers = (portfolio?.holdings || []).map((h) => h.ticker).filter(Boolean);

  return (
    <div className="app">
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onTicker={(t) => pick(t)}
        onPage={(p) => setMode(p)}
        owned={ownedTickers}
        recent={recentTickers}
      />
      <header className="topbar">
        <div className="brand">
          <h1>📈 Stock Pattern &amp; Trend Analyzer</h1>
          <div className="mode-toggle">
            <button className={`chip ${mode === "analyze" ? "on" : ""}`} onClick={() => setMode("analyze")}>Analyze</button>
            <button className={`chip ${mode === "portfolio" ? "on" : ""}`} onClick={() => setMode("portfolio")}>My Portfolio</button>
            <button className={`chip ${mode === "scan" ? "on" : ""}`} onClick={() => setMode("scan")}>Buy Zones</button>
            <button className={`chip ${mode === "strategies" ? "on" : ""}`} onClick={() => setMode("strategies")}>🧪 Strategy Lab</button>
            <button className={`chip ${mode === "ledger" ? "on" : ""}`} onClick={() => setMode("ledger")}>📒 Signal Ledger</button>
            <button className={`chip ${mode === "help" ? "on" : ""}`} onClick={() => setMode("help")}>❓ Help</button>
            <button className="chip cmdk-btn" onClick={() => setPaletteOpen(true)} title="Quick jump (Cmd/Ctrl+K)">⌘K Jump</button>
            <button className={`chip plain-toggle ${plainMode ? "on" : ""}`} onClick={togglePlain} title="Explain everything in plain English (no jargon)">
              {plainMode ? "🟢 Plain English" : "🔤 Plain English"}
            </button>
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

        {mode === "analyze" && (recentTickers.length > 0 || ownedTickers.length > 0) && (
          <div className="quick-switch">
            <span className="dim small">Quick:</span>
            {Array.from(new Set([...recentTickers, ...ownedTickers])).slice(0, 12).map((t) => (
              <button
                key={t}
                className={`chip mini-chip ${t === ticker ? "on" : ""}`}
                onClick={() => pick(t)}
                title={ownedTickers.includes(t) ? "You own this" : "Recently viewed"}
              >
                {ownedTickers.includes(t) ? "◆ " : ""}{t}
              </button>
            ))}
          </div>
        )}
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

      {mode === "ledger" && <Ledger />}
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
              <span className="split-sep" title="Show a second chart of the SAME stock at another timeframe, side by side">
                Split view:
              </span>
              {[["1d", "+Daily"], ["1wk", "+Weekly"], ["1mo", "+Monthly"]]
                .filter(([iv]) => iv !== interval)
                .map(([iv, label]) => (
                  <button
                    key={iv}
                    className={`chip mini-chip ${splitTf === iv ? "on" : ""}`}
                    onClick={() => {
                      const next = splitTf === iv ? null : iv;
                      setSplitTf(next);
                      if (!next) setSplitData(null);
                      else run(null, ticker, next);
                    }}
                    title={`Add a ${label.replace("+", "")} chart of ${ticker} beside the current one`}
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
          <div className={`layout ${splitData || compareData ? "layout-wide" : ""}`}>
            <main className="main">
              {splitData ? (
                <div className="dual-charts">
                  <div className="dual-chart-pane">
                    <div className="dual-chart-label">{data.ticker} · {INTERVAL_LABEL[interval] || interval}</div>
                    <PriceChart data={data} toggles={toggles} focus={focus} intraday={interval === "1h"} />
                  </div>
                  <div className="dual-chart-pane">
                    <div className="dual-chart-label">{splitData.ticker} · {INTERVAL_LABEL[splitTf] || splitTf}</div>
                    <PriceChart data={splitData} toggles={toggles} focus={null} intraday={splitTf === "1h"} />
                  </div>
                </div>
              ) : compareData ? (
                <div className="dual-charts">
                  <div className="dual-chart-pane">
                    <div className="dual-chart-label">{data.ticker}</div>
                    <PriceChart data={data} toggles={toggles} focus={focus} intraday={interval === "1h"} />
                  </div>
                  <div className="dual-chart-pane">
                    <div className="dual-chart-label">{compareData.ticker}</div>
                    <PriceChart data={compareData} toggles={toggles} focus={null} intraday={interval === "1h"} />
                  </div>
                </div>
              ) : (
                <PriceChart data={data} toggles={toggles} focus={focus} intraday={interval === "1h"} />
              )}
              <IndicatorPanel data={data} />
              <Alerts data={data} ticker={data.ticker} />
            </main>
            <Sidebar data={data} focus={focus} onFocus={setFocus} plainMode={plainMode} />
          </div>
        </>
      )}
    </div>
  );
}
