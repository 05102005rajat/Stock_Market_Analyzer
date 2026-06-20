// Conviction Stack — the evidence-backed "best combo". Shows each independent
// signal with an EVIDENCE-STRENGTH badge so you can see that momentum + insider
// buying (Strong) carry the weight, while the chart crossover (Weak) is shown
// but counted zero. The pre-earnings run-up appears as an honest CAUTION.
import { Plain } from "./Plain";

const STRENGTH_BADGE = {
  strong: { label: "STRONG", cls: "ev-strong" },
  moderate: { label: "MODERATE", cls: "ev-moderate" },
  weak: { label: "WEAK", cls: "ev-weak" },
};
const STATE_MARK = {
  bullish: { mark: "▲", cls: "pos" },
  bearish: { mark: "▼", cls: "neg" },
  caution: { mark: "⚠️", cls: "warn" },
  neutral: { mark: "•", cls: "dim" },
};

export default function ConvictionCard({ conviction, ticker, plainMode = false }) {
  if (!conviction?.available) return null;
  const c = conviction;

  const head =
    c.verdict === "high_bull" ? "🟢 Conviction stack — signals align"
    : c.verdict === "bear" ? "🔴 Conviction stack — leans bearish"
    : c.verdict === "mixed" ? "🟡 Conviction stack — signals disagree"
    : "⚪ Conviction stack — nothing firing";

  return (
    <section className={`card conviction conviction-${c.verdict}`}>
      <h3>{head}</h3>

      <Plain on={plainMode}>
        Instead of stacking chart indicators (which all read the same price line), this combines signals from
        different, independent sources that each have real research behind them — momentum, insider buying, and trend.
        The more of these that agree, the stronger the case. It's still scored against the market so you see if it works.
      </Plain>

      <p className="recent-line"><b>{c.headline}</b></p>

      <div className="conv-stack">
        {c.components.map((comp) => {
          const b = STRENGTH_BADGE[comp.strength] || STRENGTH_BADGE.weak;
          const m = STATE_MARK[comp.state] || STATE_MARK.neutral;
          return (
            <div key={comp.name} className={`conv-row conv-${comp.state}`}>
              <span className={`conv-mark ${m.cls}`}>{m.mark}</span>
              <span className="conv-name">{comp.name}</span>
              <span className={`ev-badge ${b.cls}`}>{b.label}</span>
              <div className="conv-detail dim small">{comp.detail}</div>
            </div>
          );
        })}
      </div>

      <p className="muted small">{c.note}</p>
      <p className="muted small">
        Counts only momentum, insider buying, and trend (the signals that replicate out-of-sample). The chart
        crossover is shown but weighted zero. Logged to the <b>Signal Ledger</b> and scored forward vs SPY — read
        its real accuracy there. Evidence-backed ≠ certain; momentum can crash and edges decay. Not a recommendation.
      </p>
    </section>
  );
}
