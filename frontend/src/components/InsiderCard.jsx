import { Plain } from "./Plain";

// Insider buying/selling — now shows what insiders ACTUALLY did: bought or sold,
// how many shares, and at what price. Far clearer than counting "filings."
export default function InsiderCard({ insider, plainMode = false }) {
  if (!insider || !insider.available) return null;
  const sig = insider.signal;
  const badgeClass = sig === "buying" ? "pos" : sig === "selling" ? "neg" : "neutral";

  return (
    <section className="card">
      <div className="insights-head">
        <h3>Insider buying &amp; selling</h3>
        <span className={`bias-badge ${badgeClass}`}>{insider.badge}</span>
      </div>

      {/* Plain-language headline always shown — this is the human-readable answer */}
      <p className="rec-detail">{insider.plain}</p>

      {/* Concrete numbers when there were real open-market trades */}
      {insider.buy_value > 0 && (
        <div className="kv">
          <span>Bought</span>
          <b className="pos">
            {insider.buy_shares.toLocaleString()} sh · ${insider.buy_value.toLocaleString()}
            {insider.buy_avg_price ? ` · ~$${insider.buy_avg_price}` : ""}
          </b>
        </div>
      )}
      {insider.sell_value > 0 && (
        <div className="kv">
          <span>Sold</span>
          <b className="neg">
            {insider.sell_shares.toLocaleString()} sh · ${insider.sell_value.toLocaleString()}
          </b>
        </div>
      )}
      {insider.n_routine > 0 && (
        <div className="kv">
          <span>Routine (grants/options/taxes)</span>
          <b className="dim">{insider.n_routine} — ignored</b>
        </div>
      )}

      <Plain on={plainMode}>
        "Bought" means insiders spent their own money on shares — the signal worth watching. "Sold" is
        weaker (people sell for taxes or to diversify). "Routine" filings are pay-related, not a market view.
      </Plain>

      <span className="dim small">
        Source: SEC Form 4 filings, last {insider.lookback_days} days. One input, not a recommendation.
      </span>
    </section>
  );
}
