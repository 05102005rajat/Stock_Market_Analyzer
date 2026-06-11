import { useState } from "react";

// Technical-POSTURE meter (-100…+100): the score marker, a shaded
// agreement-interval band, the confidence %, and (expandable) the component
// contributions. NOTE: this describes current structure, not a forecast — a
// backtest caveat is shown so it's never mistaken for a buy/sell call.
const VERDICT_CLASS = { BUY: "pos", SELL: "neg", HOLD: "neutral" };

const pos = (v) => `${((v + 100) / 200) * 100}%`;

export default function SignalGauge({ signal }) {
  const [open, setOpen] = useState(false);
  const [why, setWhy] = useState(false);
  if (!signal) return null;
  const { score, posture, verdict, confidence, interval = {}, components = [], disclaimer, evidence } = signal;

  return (
    <section className="card gauge">
      <div className="insights-head">
        <h3>Technical posture</h3>
        <span className="dim small">agreement {confidence}%</span>
      </div>

      <div className={`verdict-big ${VERDICT_CLASS[verdict]}`}>{posture}</div>
      <div className="score-line">
        <b className={VERDICT_CLASS[verdict]}>{score > 0 ? "+" : ""}{score}</b>
        <span className="dim small">
          range {interval.low} … {interval.high}
        </span>
      </div>

      <div className="meter">
        <div className="meter-track" />
        {/* confidence-interval band */}
        <div
          className="meter-band"
          style={{ left: pos(interval.low), width: `${((interval.high - interval.low) / 200) * 100}%` }}
        />
        {/* zero line + score marker */}
        <div className="meter-zero" style={{ left: "50%" }} />
        <div className={`meter-marker ${VERDICT_CLASS[verdict]}`} style={{ left: pos(score) }} />
      </div>
      <div className="meter-scale">
        <span>Bearish</span><span>Neutral</span><span>Bullish</span>
      </div>

      {evidence && (
        <div className="evidence">
          <button className="link-btn" onClick={() => setWhy((w) => !w)}>
            ⚠ Not a forecast — what the backtest found {why ? "▴" : "▾"}
          </button>
          {why && <p className="small">{evidence.finding}</p>}
        </div>
      )}

      <button className="link-btn" onClick={() => setOpen((o) => !o)}>
        {open ? "Hide" : "Show"} the {components.length} factors ▾
      </button>
      {open && (
        <div className="factors">
          {components.map((c, i) => (
            <div key={i} className="factor">
              <div className="factor-head">
                <span>{c.name}</span>
                <b className={c.value > 0 ? "pos" : c.value < 0 ? "neg" : "dim"}>
                  {c.value > 0 ? "+" : ""}{c.value}
                </b>
              </div>
              <div className="factor-bar">
                <div
                  className={`factor-fill ${c.value >= 0 ? "pos" : "neg"}`}
                  style={{ left: c.value >= 0 ? "50%" : pos(c.value * 100), width: `${(Math.abs(c.value) / 2) * 100}%` }}
                />
                <div className="factor-zero" />
              </div>
              <span className="dim small">{c.detail}</span>
            </div>
          ))}
        </div>
      )}

      <p className="muted small">{disclaimer}</p>
    </section>
  );
}
