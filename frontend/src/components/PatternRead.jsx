// What the patterns ACTUALLY say — one synthesized verdict instead of a
// name dump. Net directional tilt from measured per-stock pattern stats,
// conflict detection, and the AI-era regime check.
import { Plain } from "./Plain";

export default function PatternRead({ read, plainMode = false }) {
  if (!read || !read.available) return null;
  const dirCls =
    read.direction === "BULLISH" ? "pos" : read.direction === "BEARISH" ? "neg" : "neutral";
  return (
    <section className="card">
      <div className="insights-head">
        <h3>What the patterns actually say</h3>
        {read.n_signals > 0 && (
          <span className={`bias-badge ${dirCls}`}>
            {read.direction === "FLAT"
              ? "NO EDGE"
              : `${read.direction} ${read.tilt_pp > 0 ? "+" : ""}${read.tilt_pp}pp`}
          </span>
        )}
      </div>
      <Plain on={plainMode}>
        {read.n_signals === 0
          ? "The chart shapes are quiet right now — nothing worth acting on."
          : read.direction === "FLAT"
          ? "The bullish and bearish chart signals roughly cancel out. Honest read: no clear direction, don't act on these."
          : `The recent chart shapes lean ${read.direction.toLowerCase()}, but only mildly. These are weak hints, not predictions.`}
      </Plain>

      {read.n_signals > 0 && (
        <div className="kv">
          <span>P(higher in 10 bars) vs baseline</span>
          <b>
            {Math.round(read.p_up_10bar * 100)}% vs {Math.round(read.baseline_up * 100)}%
          </b>
        </div>
      )}
      {read.conflict && (
        <div className="kv">
          <span>Signal agreement</span>
          <b className="neg">conflicting</b>
        </div>
      )}
      {read.regime && (
        <div className="kv">
          <span>AI-era (2y) consistency</span>
          <b className={read.regime.stable ? "pos" : "neg"}>
            {read.regime.stable ? "consistent" : "regime-unstable"}
          </b>
        </div>
      )}

      <p className="rec-detail">{read.verdict}</p>

      {(read.chart_context || []).length > 0 && (
        <>
          {read.chart_context.map((c, i) => (
            <p className="rec-detail dim" key={i}>
              {c.note}
            </p>
          ))}
        </>
      )}
      <span className="dim small">{read.caveat}</span>
    </section>
  );
}
