// Weekly trade plan: probabilities + volatility-scaled targets (calibrated from
// the stock's own recent path), since day-to-day direction isn't predictable but
// the WEEKLY range is. Backtested hit rates are shown so it stays honest.
export default function TradePlan({ plan }) {
  if (!plan) return null;
  if (!plan.available) {
    return (
      <section className="card">
        <h3>Weekly trade plan</h3>
        <p className="muted small">{plan.reason || "Not enough history."}</p>
      </section>
    );
  }

  const { entry, horizon, prob_profit_intraweek, prob_profit_at_close,
          take_profit, stretch_target, stop, sample_weeks, disclaimer, vol_regime } = plan;
  const pct = (x) => `${Math.round(x * 100)}%`;
  const regimeClass = vol_regime?.label === "elevated" ? "neg" : vol_regime?.label === "calm" ? "pos" : "dim";

  return (
    <section className="card">
      <div className="insights-head">
        <h3>Weekly trade plan</h3>
        {vol_regime && (
          <span className={`dim small ${regimeClass}`} title="Targets scale with the current volatility regime">
            vol {vol_regime.ratio}× · {vol_regime.label}
          </span>
        )}
      </div>
      <p className="dim small">If you buy at the last close ({entry}), over the next {horizon} trading days:</p>

      <div className="kv">
        <span>Green exit available</span>
        <b className="pos">{pct(prob_profit_intraweek)}</b>
      </div>
      <div className="kv">
        <span>Up at week's close</span>
        <b className={prob_profit_at_close >= 0.5 ? "pos" : ""}>{pct(prob_profit_at_close)}</b>
      </div>

      <div className="plan-targets">
        <div className="plan-row pos">
          <span className="plan-label">Take-profit</span>
          <b>{take_profit.price}</b>
          <span className="plan-meta">+{take_profit.ret_pct}% · hit ~{pct(take_profit.hist_hit_rate)} of weeks</span>
        </div>
        <div className="plan-row dim">
          <span className="plan-label">Stretch</span>
          <b>{stretch_target.price}</b>
          <span className="plan-meta">+{stretch_target.ret_pct}% · ~{pct(stretch_target.hist_hit_rate)}</span>
        </div>
        <div className="plan-row neg">
          <span className="plan-label">Stop</span>
          <b>{stop.price}</b>
          <span className="plan-meta">{stop.ret_pct}% · breached ~{pct(stop.hist_breach_rate)}</span>
        </div>
      </div>

      <p className="muted small">{disclaimer} ({sample_weeks} past weeks)</p>
    </section>
  );
}
