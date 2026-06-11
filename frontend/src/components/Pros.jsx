// What the pros are saying — one calm line of analyst consensus.
// Exists for the panic moments: rating + target + count, plus a single
// reassurance line when the stock is in drawdown but the street hasn't moved.
export default function Pros({ pros }) {
  if (!pros || !pros.available) return null;
  return (
    <section className="card">
      <div className="insights-head">
        <h3>What the pros say</h3>
        <span
          className={`bias-badge ${
            /buy/i.test(pros.rating) ? "pos" : /sell|under/i.test(pros.rating) ? "neg" : "neutral"
          }`}
        >
          {pros.rating.toUpperCase()}
        </span>
      </div>
      <div className="kv">
        <span>Avg 12-mo target ({pros.n_analysts} analysts)</span>
        <b className={pros.upside_pct >= 0 ? "pos" : "neg"}>
          {pros.target_mean} ({pros.upside_pct >= 0 ? "+" : ""}
          {pros.upside_pct}%)
        </b>
      </div>
      {pros.calm_line && <p className="rec-detail">{pros.calm_line}</p>}
      <span className="dim small">{pros.caveat}</span>
    </section>
  );
}
