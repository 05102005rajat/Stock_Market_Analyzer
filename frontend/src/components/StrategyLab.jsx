import { useState } from "react";
import { getStrategies } from "../api";

// Strategy Lab: type a ticker, see famous rule-based strategies backtested vs
// just buying and holding it. Honest — usually trend filters cut drawdowns more
// than they raise returns, and steady stocks get hurt by timing.
const verdictClass = (v) =>
  v.includes("BOTH") ? "pos" : v.includes("better risk") ? "pos"
    : v.includes("loses") ? "neg" : v.includes("higher return") ? "pos" : "dim";

const PERIODS = [["1y", "1 year"], ["2y", "2 years"], ["5y", "5 years"]];

export default function StrategyLab({ onPick }) {
  const [ticker, setTicker] = useState("NVDA");
  const [period, setPeriod] = useState("1y");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const run = async (e, p = period) => {
    e?.preventDefault();
    if (!ticker.trim()) return;
    setPeriod(p);
    setLoading(true);
    setError(null);
    try {
      setData(await getStrategies(ticker.trim(), p));
    } catch (err) {
      setError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="portfolio">
      <section className="card">
        <div className="insights-head">
          <h3>Strategy Lab — do famous strategies beat just holding?</h3>
          <form className="search" onSubmit={run}>
            <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())}
              placeholder="Ticker e.g. NVDA" spellCheck={false} style={{ width: 130 }} />
            {PERIODS.map(([k, label]) => (
              <button type="button" key={k} className={`chip ${period === k ? "on" : ""}`}
                onClick={() => run(null, k)}>{label}</button>
            ))}
            <button type="submit" disabled={loading}>{loading ? "Testing…" : "Test"}</button>
          </form>
        </div>
        <p className="dim small">
          Backtests each strategy over the chosen window vs buy-and-hold. <b>Return</b> = total gain.
          <b> Max drawdown</b> = worst peak-to-trough drop (smaller is safer). <b>Sharpe</b> = return per unit of risk
          (higher is better). <b>Invested</b> = % of time in the market (rest in cash).
        </p>
      </section>

      {error && <div className="error">⚠ {error}</div>}

      {data?.available && (
        <section className="card">
          <div className="insights-head">
            <h3>{data.ticker} — last {data.years} years</h3>
            <button className="chip" onClick={() => onPick(data.ticker)}>Full analysis →</button>
          </div>
          <table className="bt">
            <thead>
              <tr><th>Strategy</th><th className="num">Return</th><th className="num">Max drawdown</th>
                <th className="num">Sharpe</th><th className="num">Invested</th><th>vs buy & hold</th></tr>
            </thead>
            <tbody>
              {data.strategies.map((r) => (
                <tr key={r.name} className={r.name === "Buy & Hold" ? "bh-row" : ""}>
                  <td><b>{r.name}</b></td>
                  <td className="num pos">+{r.total_return}%</td>
                  <td className="num neg">{r.max_drawdown}%</td>
                  <td className="num">{r.sharpe}</td>
                  <td className="num dim">{r.exposure}%</td>
                  <td className={verdictClass(r.verdict)}>{r.verdict}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted small">{data.note}</p>
        </section>
      )}

      {!data && !error && !loading && (
        <div className="empty">Enter a ticker and hit <b>Test</b> — try a wild one (NVDA, TSLA) vs a steady one (KO, JNJ) to see how differently timing strategies behave.</div>
      )}
    </div>
  );
}
