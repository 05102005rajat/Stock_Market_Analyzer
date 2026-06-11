// Expert-style multi-timeframe trend read: direction + % change across
// 1W…1Y, an alignment verdict, and the 50/200-day SMA regime.
const ARROWS = { uptrend: "▲", downtrend: "▼", sideways: "▬" };
const DIR_CLASS = { uptrend: "pos", downtrend: "neg", sideways: "neutral" };

export default function MultiTimeframe({ mtf }) {
  if (!mtf || !mtf.horizons?.length) return null;
  const { horizons, alignment, regime = {} } = mtf;

  const alignClass = alignment.includes("up")
    ? "pos"
    : alignment.includes("down") || alignment.includes("bearish")
    ? "neg"
    : "neutral";

  return (
    <section className="card">
      <h3>Multi-timeframe trend</h3>
      <div className={`align ${alignClass}`}>{alignment}</div>

      <div className="tf-grid">
        {horizons.map((h) => (
          <div key={h.label} className="tf-row">
            <span className="tf-label">{h.label}</span>
            <span className={`tf-dir ${DIR_CLASS[h.direction]}`}>
              {ARROWS[h.direction]} {h.direction}
            </span>
            <span className={`tf-chg ${h.change_pct >= 0 ? "pos" : "neg"}`}>
              {h.change_pct >= 0 ? "+" : ""}
              {h.change_pct}%
            </span>
          </div>
        ))}
      </div>

      {regime.cross && (
        <div className="regime">
          <div className={`kv ${regime.cross === "golden" ? "" : ""}`}>
            <span>vs 50-day SMA</span>
            <b className={regime.above_sma50 ? "pos" : "neg"}>
              {regime.above_sma50 ? "above" : "below"} ({regime.sma50})
            </b>
          </div>
          {regime.sma200 != null && (
            <div className="kv">
              <span>vs 200-day SMA</span>
              <b className={regime.above_sma200 ? "pos" : "neg"}>
                {regime.above_sma200 ? "above" : "below"} ({regime.sma200})
              </b>
            </div>
          )}
          <p className={`small ${regime.cross === "golden" ? "pos" : "neg"}`}>
            {regime.cross_label}
          </p>
        </div>
      )}
    </section>
  );
}
