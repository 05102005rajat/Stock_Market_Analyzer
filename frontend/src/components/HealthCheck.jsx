// One-glance "is anything ACTUALLY wrong?" banner. Stays GREEN through normal red
// days — it only flags a holding that truly breaks its 200-day trend or hits the
// -8% stop. The whole point: a wiggle is not a reason to act, so a wiggle stays
// green. Designed to reassure and say "close the app," not to feed tick-watching.
export default function HealthCheck({ holdings }) {
  const owned = (holdings || []).filter((h) => h.value);
  if (!owned.length) return null;
  const total = owned.reduce((s, h) => s + h.value, 0);

  const statusOf = (h) => {
    if (h.gain_pct != null && h.gain_pct <= -8) return "stop";   // at/below your -8% stop
    if (h.stage === "stage4") return "broken";                   // 🔴 Declining (falling knife) — basing/recovering are fine
    return "ok";
  };
  const rows = owned.map((h) => ({ ...h, st: statusOf(h), big: h.value >= 0.03 * total }));
  const flaggedBig = rows.filter((r) => r.st !== "ok" && r.big);
  const flaggedDust = rows.filter((r) => r.st !== "ok" && !r.big);
  const allClear = flaggedBig.length === 0;

  return (
    <section className={`card healthcheck ${allClear ? "clear" : "alert"}`}>
      {allClear ? (
        <>
          <h3>✅ All clear — nothing needs you today</h3>
          <p className="muted small">
            Every meaningful holding is healthy: above its trend line and within range of your cost.
            Today's red is <b>normal noise, not a reason to act.</b> Glance here once a day, then close the app and go live your life.
          </p>
        </>
      ) : (
        <>
          <h3>⚠️ {flaggedBig.length} holding{flaggedBig.length > 1 ? "s" : ""} worth a look</h3>
          <p className="muted small">These actually broke a rule (not just a red day) — everything else is fine.</p>
          <div className="hc-list">
            {flaggedBig.map((r) => (
              <div key={r.ticker} className="hc-row">
                <b className="neg">🔴 {r.ticker}</b>
                <span className="dim small">
                  {r.st === "stop"
                    ? `down ${r.gain_pct}% from cost — at your stop, decide hold-or-cut`
                    : "below its 200-day and still falling — review or hold to your stop"}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
      {flaggedDust.length > 0 && (
        <p className="dim small">
          Minor: {flaggedDust.map((r) => r.ticker).join(", ")} {flaggedDust.length > 1 ? "are" : "is"} weak,
          but tiny dust (&lt;3% each) — ignore, or clean up later. Not worth a worry.
        </p>
      )}
    </section>
  );
}
