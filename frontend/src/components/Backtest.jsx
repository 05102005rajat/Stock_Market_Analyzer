// Historical edge of each candlestick pattern for THIS stock: how often price
// moved in the pattern's favor N bars later, vs the unconditional baseline.
export default function Backtest({ backtest }) {
  if (!backtest) return null;
  if (!backtest.available) {
    return (
      <section className="card">
        <h3>Pattern edge (backtested)</h3>
        <p className="muted small">{backtest.reason || "Not enough history to backtest."}</p>
      </section>
    );
  }

  const { horizons = [], baseline = {}, patterns = [], note } = backtest;
  const h = horizons[Math.floor(horizons.length / 2)]; // middle horizon, e.g. 10
  const base = baseline[String(h)] || {};
  const top = patterns.slice(0, 8);

  return (
    <section className="card">
      <h3>Pattern edge · {h}-bar</h3>
      <p className="dim small">
        Baseline: price is up {Math.round((base.up_rate ?? 0) * 100)}% of the time after {h} bars.
        Edge = win-rate above that baseline.
      </p>
      <table className="bt">
        <thead>
          <tr>
            <th>Pattern</th>
            <th>n</th>
            <th>Win</th>
            <th>Edge</th>
            <th>Avg</th>
          </tr>
        </thead>
        <tbody>
          {top.map((p, i) => {
            const s = p.stats?.[String(h)];
            if (!s) return null;
            return (
              <tr key={i}>
                <td>
                  <span className={`dot ${p.bias === "bullish" ? "pos" : p.bias === "bearish" ? "neg" : "neutral"}`} />
                  {p.name}
                </td>
                <td className="num">{s.samples}</td>
                <td className="num">{Math.round(s.win_rate * 100)}%</td>
                <td className={`num ${s.edge > 0 ? "pos" : s.edge < 0 ? "neg" : ""}`}>
                  {s.edge > 0 ? "+" : ""}
                  {Math.round(s.edge * 100)}
                </td>
                <td className={`num ${s.avg_return >= 0 ? "pos" : "neg"}`}>
                  {s.avg_return >= 0 ? "+" : ""}
                  {s.avg_return}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="muted small">{note}</p>
    </section>
  );
}
