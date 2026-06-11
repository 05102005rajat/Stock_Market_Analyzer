// Sector Pulse: what the stock's whole sector is doing today/this month, and
// the honest evidence on sector-event days (they price news; they don't start
// sector-only slides). Built to prevent panic, not to predict.
export default function SectorPulse({ pulse }) {
  if (!pulse || !pulse.available) return null;

  const evt = pulse.event;
  const badge =
    evt === "broad_selloff"
      ? { label: "SECTOR-WIDE SELLOFF", cls: "neg" }
      : evt === "broad_rally"
      ? { label: "SECTOR-WIDE RALLY", cls: "pos" }
      : { label: "NORMAL DISPERSION", cls: "neutral" };

  return (
    <section className="card">
      <div className="insights-head">
        <h3>Sector pulse — {pulse.sector}</h3>
        <span className={`bias-badge ${badge.cls}`}>{badge.label}</span>
      </div>

      <div className="kv">
        <span>Sector today (avg of {pulse.n_members})</span>
        <b className={pulse.sector_today_pct >= 0 ? "pos" : "neg"}>
          {pulse.sector_today_pct >= 0 ? "+" : ""}
          {pulse.sector_today_pct}%
        </b>
      </div>
      <div className="kv">
        <span>Sector 1-month</span>
        <b className={pulse.sector_r21_pct >= 0 ? "pos" : "neg"}>
          {pulse.sector_r21_pct >= 0 ? "+" : ""}
          {pulse.sector_r21_pct}%
        </b>
      </div>
      {pulse.ticker_gap21_pct != null && (
        <div className="kv">
          <span>This stock vs sector (1mo)</span>
          <b className={pulse.ticker_gap21_pct >= 0 ? "pos" : "neg"}>
            {pulse.ticker_gap21_pct >= 0 ? "+" : ""}
            {pulse.ticker_gap21_pct}%
          </b>
        </div>
      )}

      <div className="sector-members">
        {pulse.members.map((m) => (
          <span
            key={m.ticker}
            className={`chip ${m.today_pct == null ? "" : m.today_pct >= 0 ? "pos" : "neg"}`}
            title={m.r21_pct != null ? `1mo: ${m.r21_pct > 0 ? "+" : ""}${m.r21_pct}%` : ""}
          >
            {m.ticker} {m.today_pct != null ? `${m.today_pct > 0 ? "+" : ""}${m.today_pct}%` : "—"}
          </span>
        ))}
      </div>

      {(pulse.notes || []).map((n, i) => (
        <p className="rec-detail" key={i}>
          {n}
        </p>
      ))}
      <span className="dim small">{pulse.caveat}</span>
    </section>
  );
}
