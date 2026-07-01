// Two honest, behavior-shaping cards: (1) a "brace check" — the worst drop your
// current mix would have had, in dollars, so you don't panic-sell at the bottom;
// (2) what fees cost you. Both pure measurement, no prediction.
const money = (v) => `$${(v ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

export function DrawdownCard({ risk, drawdown: d }) {
  if (!d?.available) return null;
  return (
    <section className="card">
      <h3>How much could it drop? (brace check)</h3>
      {risk?.available && (
        <p className="recent-line">
          In a normal week your whole portfolio moves about <b>±{risk.typical_week_range_pct}%</b>.
        </p>
      )}
      <p className="recent-line">
        The worst your <i>current mix</i> would have dropped (last {d.years} years) was{" "}
        <b className="neg">{d.max_drawdown_pct}%</b> — {d.peak_date} → {d.trough_date}, and it took about{" "}
        <b>{d.recovery_months ?? "—"} months</b> to recover.
      </p>
      <p className="brace">
        A drop like that today: your stocks <b>{money(d.stocks_now)}</b> →{" "}
        <b className="neg">{money(d.stocks_at_trough)}</b>.
      </p>
      <p className="muted small">
        Knowing this <i>now</i> is how you avoid the #1 beginner mistake — panic-selling at the bottom.
        It has always recovered; the only question is whether you hold on. (History, not a forecast.)
      </p>
    </section>
  );
}

export function FeeCard({ fees: f }) {
  if (!f?.available) return null;
  return (
    <section className="card">
      <h3>What are fees costing you?</h3>
      <p className="recent-line">
        Your blended fund fee is just <b className="pos">{f.blended_fee_pct}%</b> — about{" "}
        <b>{money(f.annual_cost)}/year</b>, roughly <b>{money(f.drag_30y)}</b> over 30 years.{" "}
        {f.blended_fee_pct < 0.15 ? "Excellent — you're barely paying anything." : "Worth keeping an eye on."}
      </p>
      <p className="muted small">
        For comparison, a typical <b>1% fund</b> would have cost you <b className="neg">{money(f.vs_1pct_30y)}</b> over
        30 years on today's balance. Cheap index funds (your VOO is 0.03%) are one of investing's few guaranteed wins.
        {f.funds?.length > 0 && <> Your funds: {f.funds.map((x) => `${x.ticker} ${x.fee_pct}%`).join(", ")}.</>}
      </p>
      <p className="muted small">{f.assumption}</p>
    </section>
  );
}
