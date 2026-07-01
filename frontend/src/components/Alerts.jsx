import { useEffect, useState } from "react";

// User-defined alert rules evaluated against the latest analysis snapshot.
// Rules persist in localStorage; pair with the toolbar "Auto-refresh" toggle to
// have them re-checked on an interval.
const RULE_TYPES = [
  { id: "rsi_below", label: "RSI below", numeric: true, default: 30 },
  { id: "rsi_above", label: "RSI above", numeric: true, default: 70 },
  { id: "price_below", label: "Price below", numeric: true, default: 0 },
  { id: "price_above", label: "Price above", numeric: true, default: 0 },
  { id: "confidence_above", label: "Confidence above", numeric: true, default: 60 },
  { id: "verdict_buy", label: "Posture turns bullish", numeric: false },
  { id: "verdict_sell", label: "Posture turns bearish", numeric: false },
  { id: "stage2", label: "Passes Minervini (Stage 2)", numeric: false },
  { id: "golden", label: "Golden cross", numeric: false },
  { id: "death", label: "Death cross", numeric: false },
];

function evaluate(rule, data) {
  const latest = data.latest || {};
  const sig = data.signal || {};
  const regime = data.multiTimeframe?.regime || {};
  const mino = data.minervini || {};
  const v = Number(rule.value);
  switch (rule.type) {
    case "rsi_below": return latest.rsi != null && latest.rsi < v;
    case "rsi_above": return latest.rsi != null && latest.rsi > v;
    case "price_below": return latest.close != null && latest.close < v;
    case "price_above": return latest.close != null && latest.close > v;
    case "confidence_above": return sig.confidence != null && sig.confidence > v;
    case "verdict_buy": return sig.verdict === "BUY";
    case "verdict_sell": return sig.verdict === "SELL";
    case "stage2": return !!mino.passes || (mino.stage || "").includes("Stage 2");
    case "golden": return regime.cross === "golden";
    case "death": return regime.cross === "death";
    default: return false;
  }
}

function describe(rule) {
  const t = RULE_TYPES.find((x) => x.id === rule.type);
  return t?.numeric ? `${t.label} ${rule.value}` : t?.label || rule.type;
}

const KEY = "stockapp.alerts";

export default function Alerts({ data, ticker }) {
  const [rules, setRules] = useState(() => {
    try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; }
  });
  const [type, setType] = useState("rsi_below");
  const [value, setValue] = useState(30);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(rules));
  }, [rules]);

  const def = RULE_TYPES.find((x) => x.id === type);

  const add = () => {
    setRules((rs) => [...rs, { id: Date.now(), type, value: def?.numeric ? Number(value) : null }]);
  };
  const remove = (id) => setRules((rs) => rs.filter((r) => r.id !== id));

  return (
    <section className="card">
      <h3>Alerts</h3>
      <div className="alert-builder">
        <select
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            const d = RULE_TYPES.find((x) => x.id === e.target.value);
            if (d?.numeric) setValue(d.default);
          }}
        >
          {RULE_TYPES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
        {def?.numeric && (
          <input type="number" value={value} onChange={(e) => setValue(e.target.value)} />
        )}
        <button className="chip" onClick={add}>Add</button>
      </div>

      {rules.length === 0 && <p className="muted small">No alerts yet. Add a condition to watch.</p>}
      {rules.map((r) => {
        const triggered = data ? evaluate(r, data) : false;
        return (
          <div key={r.id} className={`alert-row ${triggered ? "fired" : ""}`}>
            <span className="alert-status">{triggered ? "🔔" : "○"}</span>
            <span className="alert-desc">{describe(r)}</span>
            {triggered && <span className="badge pos">{ticker}</span>}
            <button className="alert-x" onClick={() => remove(r.id)}>✕</button>
          </div>
        );
      })}
    </section>
  );
}
