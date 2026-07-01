// Mark Minervini's Trend Template scorecard: an 8-point checklist with the
// overall score and Weinstein-style stage.
export default function Minervini({ minervini }) {
  if (!minervini) return null;
  if (!minervini.available) {
    return (
      <section className="card">
        <h3>Minervini Trend Template</h3>
        <p className="muted small">{minervini.reason || "Not enough history."}</p>
      </section>
    );
  }

  const { score, passes, stage, summary, criteria = [] } = minervini;
  const pct = (score / 8) * 100;

  return (
    <section className="card">
      <div className="insights-head">
        <h3>Minervini Trend Template</h3>
        <span className={`bias-badge ${passes ? "pos" : score >= 5 ? "neutral" : "neg"}`}>
          {score}/8
        </span>
      </div>
      <div className="score-bar">
        <div className={`score-fill ${passes ? "pos" : "neutral"}`} style={{ width: `${pct}%` }} />
      </div>
      <div className={`stage ${stage.includes("Stage 2") ? "pos" : stage.includes("Stage 4") ? "neg" : "neutral"}`}>
        {stage}
      </div>
      <p className="muted small">{summary}</p>

      <ul className="checklist">
        {criteria.map((c, i) => (
          <li key={i} title={c.detail}>
            <span className={c.passed ? "check pos" : "check neg"}>{c.passed ? "✓" : "✗"}</span>
            <span className="check-name">{c.name}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
