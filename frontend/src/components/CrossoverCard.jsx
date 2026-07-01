// EMA-ribbon (55/89/204) + MACD (13/34/9) crossover signal — the user-specified
// trend system. Shows the BUY/SELL/NEUTRAL state, the 3-condition checklist, the
// most recent crossover events, and — prominently — the honest caveat that this
// is a LATE trend-follower (not a predictor) whose real accuracy is being scored
// forward in the Signal Ledger. Trust the ledger, not the arrow.
import { Plain } from "./Plain";

export default function CrossoverCard({ crossover, ticker, plainMode = false }) {
  if (!crossover?.available) return null;
  const c = crossover;
  const v = c.values;
  const state = c.state; // buy | sell | neutral

  const head =
    state === "buy" ? "🟢 EMA + MACD crossover — BUY signal"
    : state === "sell" ? "🔴 EMA + MACD crossover — SELL signal"
    : "⚪ EMA + MACD crossover — no clean signal";

  // Extension read: how far price sits above the slow EMA. The trend-follower
  // trap is that it's MOST confident exactly when a name is MOST extended.
  const extPct = v.ema204 ? ((v.price / v.ema204 - 1) * 100) : 0;
  const veryExtended = state === "buy" && extPct >= 40;

  const evt = c.events || {};
  const evtRows = [
    ["EMA89 × EMA204", evt.ema89_x_ema204],
    ["EMA55 × EMA89", evt.ema55_x_ema89],
    ["MACD × zero line", evt.macd_zero_line],
    ["MACD × signal", evt.macd_x_signal],
  ].filter(([, e]) => e);

  return (
    <section className={`card crossover crossover-${state}`}>
      <h3>{head}</h3>

      <Plain on={plainMode}>
        This is a trend-following signal: it turns {state === "buy" ? "green" : state === "sell" ? "red" : "neutral"} only
        after a move is already underway. It is good at confirming a trend and useless at calling a turn. It is NOT a
        prediction — the app logs it and keeps score against the market so you can see how often it's actually right.
      </Plain>

      <p className="recent-line">
        <b>{c.label}</b>
      </p>

      <div className="cross-checklist">
        {c.components.map((comp) => (
          <div key={comp.name} className={`cross-cond ${comp.ok ? "ok" : "no"}`}>
            <span className="cross-mark">{comp.ok ? "✓" : "✕"}</span>
            <span className="cross-name">{comp.name}</span>
            <span className="dim small">{comp.detail}</span>
          </div>
        ))}
      </div>

      <p className="recent-line small">
        EMA55 <b>${v.ema55}</b> · EMA89 <b>${v.ema89}</b> · EMA204 <b>${v.ema204}</b> ·
        MACD <b>{v.macd}</b>{v.macd_signal != null ? <> (signal {v.macd_signal})</> : null}
      </p>

      {evtRows.length > 0 && (
        <div className="cross-events small">
          <span className="dim">Recent crosses: </span>
          {evtRows.map(([name, e]) => (
            <span key={name} className="cross-evt">
              {name} <b className={e.direction === "up" ? "pos" : "neg"}>{e.direction}</b>{" "}
              <span className="dim">{e.bars_ago}d ago ({e.date})</span>
            </span>
          ))}
        </div>
      )}

      {veryExtended && (
        <p className="recent-line small warn">
          ⚠️ Heads-up: {ticker} sits <b>{extPct.toFixed(0)}% above its EMA204</b>. A pure trend signal is
          loudest exactly when a stock is most stretched — which is also when pullback risk is highest. The
          signal can't see that; it only sees that price is rising.
        </p>
      )}

      <p className="muted small">
        Trend-following crossovers historically show little-to-no edge after costs and data-snooping, and they
        whipsaw in choppy markets. This signal is logged to the <b>Signal Ledger</b> and scored forward vs SPY at
        5/21/63 days — read its real out-of-sample accuracy there before trusting the arrow. Not a recommendation.
      </p>
    </section>
  );
}
