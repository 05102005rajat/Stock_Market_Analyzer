import { Plain } from "./Plain";

// Position sizing — ATR stop + share count for a 1%-risk bite on a $5k account.
// Risk management, not a signal. Flags when conviction would breach 10% sizing.
export default function SizingCard({ sizing, ticker, plainMode = false }) {
  if (!sizing || !sizing.available) return null;
  const big = (sizing.position_pct_of_account ?? 0) > 10;
  return (
    <section className="card">
      <div className="insights-head">
        <h3>If you sized this (1% risk)</h3>
        {big && <span className="bias-badge neg">&gt;10% OF ACCOUNT</span>}
      </div>
      <Plain on={plainMode}>
        A sensible "only lose 1% if I'm wrong" position here would be about {sizing.shares} shares
        (${sizing.position_value}), with an automatic sell-to-cap-losses order at ${sizing.stop_price}.
        {big
          ? ` That's ${sizing.position_pct_of_account}% of a $5,000 account — bigger than the 10% one-stock limit, so consider buying less.`
          : ` That's a reasonable slice of a $5,000 account.`}
      </Plain>
      <div className="kv">
        <span>ATR stop</span>
        <b>
          {sizing.stop_price} ({sizing.stop_pct}%)
        </b>
      </div>
      <div className="kv">
        <span>Shares for $50 risk (1% of $5k)</span>
        <b>{sizing.shares}</b>
      </div>
      <div className="kv">
        <span>Position value</span>
        <b>
          ${sizing.position_value} ({sizing.position_pct_of_account}% of account)
        </b>
      </div>
      <p className="rec-detail">{sizing.note}</p>
      <span className="dim small">
        Assumes a $5,000 account and a 2x-ATR stop. Descriptive risk math, not a recommendation to buy {ticker}.
      </span>
    </section>
  );
}
