// The "this is the line" card: the key resistance level, where price stands
// vs it, and the HONEST historically-measured odds for the current situation
// (break-to-old-high rates by distance, retest/failure rates). Driven entirely
// by the backend resistance engine — no client-side guessing.
const STATE_META = {
  approaching: { label: "PRESSING RESISTANCE", cls: "neutral" },
  fresh_breakout: { label: "FRESH BREAKOUT", cls: "pos" },
  holding_above: { label: "HOLDING ABOVE", cls: "pos" },
  choppy_above: { label: "RETESTING THE LINE", cls: "neutral" },
  below: { label: "BELOW RESISTANCE", cls: "neg" },
};

export default function Resistance({ res, onFocus, focusKey }) {
  if (!res || !res.available) return null;
  const meta = STATE_META[res.state] || STATE_META.below;
  const key = "resistance-level";
  const p = res.ath_bucket?.p_reach_ath_63d;

  return (
    <section className="card">
      <div className="insights-head">
        <h3>The line that matters</h3>
        <span className={`bias-badge ${meta.cls}`}>{meta.label}</span>
      </div>

      <div
        className={`verdict ${meta.cls} clickable ${focusKey === key ? "focused" : ""}`}
        onClick={onFocus ? () => onFocus({ levels: [res.level], key }) : undefined}
        title="Click to draw this level on the chart"
      >
        ◎ {res.level}
      </div>

      <div className="kv">
        <span>Distance to it</span>
        <b>{res.pct_to_level > 0 ? `+${res.pct_to_level}%` : `${res.pct_to_level}%`}</b>
      </div>
      <div className="kv">
        <span>Prior rejections here</span>
        <b>{res.touches}</b>
      </div>
      <div className="kv">
        <span>Old all-time high</span>
        <b>
          {res.ath} ({res.dist_ath_pct > 0 ? `${res.dist_ath_pct}% above price` : "already cleared"})
        </b>
      </div>
      {p != null && (
        <div className="kv">
          <span>Breaks here → reached old high (3mo)</span>
          <b>{Math.round(p * 100)}% historically</b>
        </div>
      )}
      {res.volume_surge != null && (
        <div className="kv">
          <span>Volume today</span>
          <b>{res.volume_surge ? ">1.5x average (confirming)" : "normal"}</b>
        </div>
      )}

      {res.own && (
        <>
          <div className="kv">
            <span>
              THIS stock's own breakouts ({res.own.n} in history)
            </span>
            <b>
              {res.own.pushed_higher_5d_pct != null ? `${res.own.pushed_higher_5d_pct}% pushed higher` : "—"}
            </b>
          </div>
          <p className="rec-detail">
            {`Its own pattern: ${res.own.retest_21d_pct ?? "—"}% retested the broken line within a month, ` +
              `${res.own.decisive_fail_21d_pct ?? "—"}% failed decisively (>3% below), and ` +
              `${res.own.reached_prior_high_63d_pct ?? "—"}% went on to its prior high within 3 months. ` +
              `Small sample — read alongside the universe rates above.`}
          </p>
        </>
      )}

      <p className="situation">{res.headline}</p>
      {(res.odds || []).map((o, i) => (
        <p className="rec-detail" key={i}>
          {o}
        </p>
      ))}

      <span className="dim small">{res.caveat}</span>
    </section>
  );
}
