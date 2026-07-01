// Today's gap card — appears only when the stock actually gapped >=0.5% at
// the open. Shows this stock's OWN measured odds of continuation vs fade for
// gaps of today's direction and size.
export default function GapCard({ gap }) {
  if (!gap || !gap.available || !gap.gapped_today) return null;
  const up = gap.direction === "up";
  const r = gap.today_rates;
  return (
    <section className="card">
      <div className="insights-head">
        <h3>Today's open gap</h3>
        <span className={`bias-badge ${up ? "pos" : "neg"}`}>
          {gap.bucket === "big" ? "BIG " : ""}GAP {gap.direction.toUpperCase()} {gap.today_gap_pct > 0 ? "+" : ""}
          {gap.today_gap_pct}%
        </span>
      </div>
      {r && (
        <>
          <div className="kv">
            <span>Its own gaps like this (n={r.n}): continued</span>
            <b>{r.continued_pct}%</b>
          </div>
          <div className="kv">
            <span>Faded back to yesterday's close intraday</span>
            <b>{r.faded_to_prior_close_pct}%</b>
          </div>
          <div className="kv">
            <span>Avg open-to-close after such gaps</span>
            <b className={r.avg_open_to_close_pct >= 0 ? "pos" : "neg"}>
              {r.avg_open_to_close_pct >= 0 ? "+" : ""}
              {r.avg_open_to_close_pct}%
            </b>
          </div>
        </>
      )}
      {gap.note && <p className="rec-detail">{gap.note}</p>}
      <span className="dim small">{gap.caveat}</span>
    </section>
  );
}
