// The headline "what's going on and what to watch" panel, driven by the
// backend insight engine. Recommendations are pre-sorted by priority.
const BIAS_CLASS = { bullish: "pos", bearish: "neg", neutral: "neutral" };
const PRIO_LABEL = { 1: "High", 2: "Medium", 3: "FYI" };

export default function Insights({ insights, onFocus, focusKey }) {
  if (!insights) return null;
  const { situation, bias, recommendations = [], watch = [], disclaimer } = insights;

  return (
    <section className="card insights">
      <div className="insights-head">
        <h3>What to watch</h3>
        <span className={`bias-badge ${BIAS_CLASS[bias]}`}>{bias}</span>
      </div>
      <p className="situation">{situation}</p>

      <div className="recs">
        {recommendations.map((r, i) => {
          const key = `rec-${i}`;
          const clickable = !!r.anchor;
          return (
            <div
              key={i}
              className={`rec ${BIAS_CLASS[r.bias]} ${clickable ? "clickable" : ""} ${
                focusKey === key ? "focused" : ""
              }`}
              onClick={clickable ? () => onFocus({ ...r.anchor, key }) : undefined}
              title={clickable ? "Click to highlight on the chart" : undefined}
            >
              <div className="rec-head">
                <span className="rec-title">
                  {clickable && <span className="why">◎</span>} {r.title}
                </span>
                <span className={`prio prio-${r.priority}`}>{PRIO_LABEL[r.priority]}</span>
              </div>
              <p className="rec-detail">{r.detail}</p>
            </div>
          );
        })}
      </div>

      {watch.length > 0 && (
        <ul className="watch">
          {watch.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      )}

      <p className="muted small">{disclaimer}</p>
    </section>
  );
}
