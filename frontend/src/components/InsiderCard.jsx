// Insider read — recent Form 4 activity. The best evidence-backed free signal,
// shown honestly: filings != purchases, and the edge is modest post-2003.
export default function InsiderCard({ insider }) {
  if (!insider || !insider.available) return null;
  return (
    <section className="card">
      <div className="insights-head">
        <h3>Insider activity (Form 4)</h3>
        <span className={`bias-badge ${insider.cluster ? "pos" : "neutral"}`}>
          {insider.cluster ? "CLUSTER BUYING" : "ROUTINE"}
        </span>
      </div>
      <div className="kv">
        <span>Distinct insiders (last ~3 weeks)</span>
        <b>{insider.n_insiders_21d}</b>
      </div>
      {insider.csuite_filings > 0 && (
        <div className="kv">
          <span>C-suite filings</span>
          <b>{insider.csuite_filings}</b>
        </div>
      )}
      {insider.note && <p className="rec-detail">{insider.note}</p>}
      <span className="dim small">{insider.disclaimer}</span>
    </section>
  );
}
