// Extension gauge — the "rubber band" vs the 50d MA, framed honestly as a
// turbulence/size gauge rather than a top-calling signal.
const STATE = {
  extended: { label: "EXTENDED 15%+", cls: "neutral" },
  blowoff: { label: "BLOW-OFF 25%+", cls: "neg" },
  ma_touch_after_run: { label: "BACK AT THE 50D MA", cls: "pos" },
  stretched_below: { label: "STRETCHED BELOW", cls: "neg" },
};

export default function ExtensionCard({ ext }) {
  if (!ext || !ext.available || ext.state === "normal") return null;
  const meta = STATE[ext.state] || { label: ext.state, cls: "neutral" };
  return (
    <section className="card">
      <div className="insights-head">
        <h3>Rubber band (vs 50d MA)</h3>
        <span className={`bias-badge ${meta.cls}`}>{meta.label}</span>
      </div>
      <div className="kv">
        <span>Distance from 50d MA</span>
        <b className={ext.ext_pct >= 0 ? "pos" : "neg"}>
          {ext.ext_pct >= 0 ? "+" : ""}
          {ext.ext_pct}%
        </b>
      </div>
      {ext.percentile_2y != null && (
        <div className="kv">
          <span>Vs its own last 2 years</span>
          <b>{ext.percentile_2y}th percentile</b>
        </div>
      )}
      {(ext.notes || []).map((n, i) => (
        <p className="rec-detail" key={i}>
          {n}
        </p>
      ))}
      <span className="dim small">{ext.caveat}</span>
    </section>
  );
}
