// Exit alerts — scans your holdings against your standing sell RULES (no
// prediction) and surfaces the ones that need a look right now: below the
// 200-day risk line, down a lot from cost (review), or up a lot (consider
// trimming/rebalancing). Computed live from the holdings you already see.
const DOWN = -12;   // % from cost -> "review"
const UP = 25;      // % from cost -> "consider trimming"

export default function ExitAlerts({ holdings, onPick }) {
  const owned = (holdings || []).filter((r) => r.value);
  if (!owned.length) return null;

  const alerts = [];
  for (const r of owned) {
    if (r.below_200dma && r.recovering) {
      // Below the 200-day but back above its faster 50-day = climbing out of a dip.
      // The 200-day just lags; this is healing, not a red flag.
      alerts.push({ t: r.ticker, kind: "recovering", icon: "🌤️",
        text: `is below its 200-day ($${r.sma200_price}) but RECOVERING — back above its 50-day line, so it's stopped being a falling knife. This is a safety/context note, NOT a buy signal: I backtested "buy the recovery" and it doesn't beat just holding.` });
    } else if (r.below_200dma) {
      alerts.push({ t: r.ticker, kind: "risk", icon: "⚖️",
        text: `is below BOTH its 200-day ($${r.sma200_price}) and its 50-day — still falling, not yet recovering. The higher-drawdown zone; consider reducing risk or holding to your stop.` });
    }
    if (r.gain_pct != null && r.gain_pct <= DOWN) {
      alerts.push({ t: r.ticker, kind: "loss", icon: "📉",
        text: `is down ${r.gain_pct}% from your cost — review whether to hold or cut at your stop.` });
    }
    if (r.gain_pct != null && r.gain_pct >= UP) {
      alerts.push({ t: r.ticker, kind: "gain", icon: "📈",
        text: `is up +${r.gain_pct}% — consider trimming some to lock gains / rebalance (not because it'll drop).` });
    }
  }

  return (
    <section className="card exit-alerts">
      <h3>⏰ Exit alerts — holdings hitting your rules</h3>
      {alerts.length === 0 ? (
        <p className="muted small">
          Nothing triggered — every holding is above its 200-day line and within a normal range of your cost. Sit tight.
        </p>
      ) : (
        alerts.map((a, i) => (
          <div key={i} className={`alert-row clickable ${a.kind === "gain" || a.kind === "recovering" ? "" : "fired"}`} onClick={() => onPick(a.t)}>
            <span className="alert-status">{a.icon}</span>
            <span className="alert-desc"><b>{a.t}</b> {a.text}</span>
          </div>
        ))
      )}
      <p className="muted small">Rules, not predictions. Click a name for its full breakdown.</p>
    </section>
  );
}
