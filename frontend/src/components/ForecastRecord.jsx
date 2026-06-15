// Forecast track record — "how many times has it actually been right?"
// Fetches a walk-forward backtest ON DEMAND (it retrains models, so it's slow
// and shouldn't run on every page load). Shows hit-rate vs a simple baseline,
// plus the honest up-call / down-call split.
import { useState } from "react";
import { getForecastRecord } from "../api";

export default function ForecastRecord({ ticker, horizon }) {
  const [rec, setRec] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  const check = async () => {
    setLoading(true);
    setErr(null);
    try {
      setRec(await getForecastRecord(ticker, horizon));
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  if (!rec && !loading) {
    return (
      <button className="chip fc-record-btn" onClick={check} title="Backtest how often this forecast called direction correctly">
        📊 How often has this been right?
      </button>
    );
  }
  if (loading) return <p className="muted small">Backtesting the forecast… (a few seconds)</p>;
  if (err) return <p className="muted small">Couldn't backtest: {err}</p>;
  if (!rec.available) return <p className="muted small">{rec.reason || "Not enough history to score."}</p>;

  const beats = /beats/.test(rec.verdict);
  const worse = /worse/.test(rec.verdict);
  return (
    <div className="fc-record">
      <div className="fc-record-headline">
        <span className={`fc-bignum ${beats ? "pos" : worse ? "neg" : ""}`}>{rec.hit_rate}%</span>
        <span className="dim small">
          right {rec.direction_hits} of {rec.tries} tries · {rec.horizon}-day calls
        </span>
      </div>
      <div className="kv">
        <span>vs. always guessing the usual direction</span>
        <b className={beats ? "pos" : worse ? "neg" : ""}>{rec.majority_baseline}%</b>
      </div>
      {rec.up_accuracy != null && (
        <div className="kv">
          <span>When it said UP ({rec.up_calls}×)</span>
          <b>{rec.up_accuracy}% right</b>
        </div>
      )}
      {rec.down_accuracy != null && (
        <div className="kv">
          <span>When it said DOWN ({rec.down_calls}×)</span>
          <b className={rec.down_accuracy < 40 ? "neg" : ""}>{rec.down_accuracy}% right</b>
        </div>
      )}
      <p className="plain-note">💡 {rec.plain}</p>
      <span className="dim small">{rec.disclaimer}</span>
    </div>
  );
}
