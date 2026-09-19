// The "you're not as diversified as you think" X-ray — your TRUE per-company
// and per-sector exposure once ETFs are unpacked, with double-counting and
// concentration flags. Pure measurement, the #1 honest risk for this portfolio.
export default function ExposureXray({ lt }) {
  if (!lt?.available) return null;
  const { effective = [], sectors = [], flags = [], concentration: c = {}, cash_pct, note } = lt;
  const stacked = effective.filter((e) => e.stacked);
  const maxW = Math.max(...effective.map((e) => e.weight), 1);
  const maxS = Math.max(...sectors.map((s) => s.weight), 1);

  return (
    <section className="card xray">
      <h3>What you really own (X-ray)</h3>
      <p className="situation">
        After unpacking your ETFs, <b>{c.top3_pct}% of your money is really in just 3 companies</b>
        {stacked.length > 0 && (
          <> — and you own <b>{stacked.slice(0, 3).map((e) => `${e.ticker} (${e.places}x)`).join(", ")}</b>{" "}
          in multiple places (directly <i>and</i> inside your funds, so the real bet is bigger than it looks).</>
        )}
      </p>

      <div className="xray-block">
        <span className="xray-label">Your real top holdings</span>
        {effective.slice(0, 8).map((e) => (
          <div key={e.ticker} className="xray-row">
            <span className="xray-name">{e.ticker} {e.stacked && <span className="stack-tag" title={`owned in ${e.places} places`}>🔁×{e.places}</span>}</span>
            <div className="xray-bar"><div className={`xray-fill ${e.stacked ? "stacked" : ""}`} style={{ width: `${(e.weight / maxW) * 100}%` }} /></div>
            <span className="xray-wt">{e.weight}%</span>
          </div>
        ))}
      </div>

      <div className="xray-block">
        <span className="xray-label">By sector (incl. what's inside your ETFs)</span>
        {sectors.slice(0, 6).map((s) => (
          <div key={s.sector} className="xray-row">
            <span className="xray-name sec">{s.sector}</span>
            <div className="xray-bar"><div className="xray-fill sector" style={{ width: `${(s.weight / maxS) * 100}%` }} /></div>
            <span className="xray-wt">{s.weight}%</span>
          </div>
        ))}
      </div>

      {flags.map((f, i) => <div key={i} className="risk-flag">⚠ {f}</div>)}

      <div className="xray-foot">
        <span>Top-3 names: <b>{c.top3_pct == null ? "\u2014" : `${c.top3_pct}%`}</b></span>
        <span>Mega-cap tech: <b>{c.megacap8_pct == null ? "\u2014" : `${c.megacap8_pct}%`}</b></span>
        <span>Cash: <b>{cash_pct}%</b></span>
        <span title="Measured on your invested money only — cash is not an equity bet, so it can't make the stock sleeve look more diversified. The other percentages here are of the whole account, cash included.">
          Effective # of bets: <b>{c.effective_n ?? "\u2014"}</b>
        </span>
      </div>
      <p className="muted small">🔁 = owned both directly and inside a fund (counts twice toward your real exposure). {note}</p>
    </section>
  );
}
