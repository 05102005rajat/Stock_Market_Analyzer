// Side-by-side comparison of two analyzed tickers, led by the composite signal.
const VC = { BUY: "pos", SELL: "neg", HOLD: "neutral" };

function oneYear(d) {
  const h = (d.multiTimeframe?.horizons || []).find((x) => x.label === "1Y");
  return h ? h.change_pct : null;
}

export default function Compare({ a, b, onClose }) {
  if (!a || !b) return null;

  const rows = [
    ["Posture", (d) => d.signal?.posture, (d) => VC[d.signal?.verdict]],
    ["Structure score", (d) => `${d.signal?.score > 0 ? "+" : ""}${d.signal?.score}`, (d) => VC[d.signal?.verdict]],
    ["Agreement", (d) => `${d.signal?.confidence}%`, () => ""],
    ["Trend (window)", (d) => d.trend?.direction, (d) => (d.trend?.direction === "uptrend" ? "pos" : d.trend?.direction === "downtrend" ? "neg" : "")],
    ["RSI (14)", (d) => d.latest?.rsi?.toFixed?.(0) ?? "—", (d) => (d.latest?.rsi > 70 ? "neg" : d.latest?.rsi < 30 ? "pos" : "")],
    ["1-year change", (d) => { const v = oneYear(d); return v == null ? "—" : `${v >= 0 ? "+" : ""}${v}%`; }, (d) => ((oneYear(d) ?? 0) >= 0 ? "pos" : "neg")],
    ["Minervini", (d) => (d.minervini?.available ? `${d.minervini.score}/8` : "—"), (d) => (d.minervini?.passes ? "pos" : "")],
    ["vs 200-day MA", (d) => (d.multiTimeframe?.regime?.above_sma200 == null ? "—" : d.multiTimeframe.regime.above_sma200 ? "above" : "below"), (d) => (d.multiTimeframe?.regime?.above_sma200 ? "pos" : d.multiTimeframe?.regime?.above_sma200 === false ? "neg" : "")],
  ];

  return (
    <section className="card compare">
      <div className="insights-head">
        <h3>Compare</h3>
        <button className="chip" onClick={onClose}>Close</button>
      </div>
      <table className="cmp">
        <thead>
          <tr>
            <th></th>
            <th>{a.ticker}</th>
            <th>{b.ticker}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, val, cls], i) => (
            <tr key={i}>
              <td className="dim">{label}</td>
              <td className={cls(a)}>{val(a)}</td>
              <td className={cls(b)}>{val(b)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
