// Earnings watch: upcoming earnings date + the validated "hot run-up into
// earnings" flag (the one cross-sectional idea that tested with |t|>2).
export default function EarningsWatch({ watch }) {
  if (!watch || !watch.available || watch.days_to_earnings == null) return null;
  if (watch.days_to_earnings > 14) return null; // only show when it matters

  const hot = watch.hot_runup;
  return (
    <section className="card">
      <div className="insights-head">
        <h3>Earnings watch</h3>
        <span className={`bias-badge ${hot ? "neg" : "neutral"}`}>
          {hot ? "EXPECTATIONS PRE-PAID" : `IN ${watch.days_to_earnings}D`}
        </span>
      </div>
      <div className="kv">
        <span>Next earnings</span>
        <b>{watch.next_earnings}</b>
      </div>
      {watch.runup_10d_pct != null && (
        <div className="kv">
          <span>Run-up last 10 sessions</span>
          <b className={watch.runup_10d_pct >= 0 ? "pos" : "neg"}>
            {watch.runup_10d_pct >= 0 ? "+" : ""}
            {watch.runup_10d_pct}%
          </b>
        </div>
      )}
      {watch.note && <p className="rec-detail">{watch.note}</p>}
      <span className="dim small">{watch.caveat}</span>
    </section>
  );
}
