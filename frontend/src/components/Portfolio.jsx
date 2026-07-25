import { useState } from "react";
import ExposureXray from "./ExposureXray";
import ExitAlerts from "./ExitAlerts";
import HealthCheck from "./HealthCheck";
import { DrawdownCard, FeeCard } from "./RiskCost";
import { parseHoldingsCSV } from "../utils/parseHoldingsCSV";

// Beginner-friendly portfolio: holdings GROUPED into action buckets (on-a-dip /
// extended / steady / weak) by each stock's CURRENT STATE — not predictions.
// Details (look-through, risk, glossary) tucked behind toggles to reduce clutter.

const BUCKETS = [
  { key: "dip", label: "On a dip — could add", emoji: "🟡",
    meaning: "Uptrend but pulled back (on sale). A reasonable spot to ADD if you want more — this times an entry, it does NOT predict it'll rise." },
  { key: "trim", label: "Extended — up a lot", emoji: "🟢",
    meaning: "Run up fast (overbought). Backtested: overbought does NOT mean it will fall — these often keep rising, so don't sell just because it looks high. Only trim to lock in some profit or rebalance, by your pre-set target — not because you expect a drop." },
  { key: "review", label: "Weak — review", emoji: "🔴",
    meaning: "Falling over recent months. Decide whether to hold through it or cut losses at your stop." },
  { key: "hold", label: "Steady — hold", emoji: "🔵",
    meaning: "Doing its thing in an uptrend. Usually nothing to do." },
];

const GLOSSARY = [
  ["Trend stage", "Where the stock is in its cycle: 🟢 Uptrend (above a rising 200-day, healthy) · 🟡 Topping (above 200-day but flattening) · 🌤️ Recovering (below 200-day but back above its 50-day) · 🔴 Declining (below a falling 200-day, higher-risk) · ⚪ Basing (below a flat 200-day, building a base). It's risk CONTEXT, not a buy signal — tested, a stage doesn't predict above-average returns."],
  ["Sell target 🎯", "A realistic price to take some profit — historically reached about 2 of 3 weeks. Odds, not a promise."],
  ["Stop 🛡️", "A price to sell at if it falls, to limit losses."],
  ["On a dip", "The stock is in an uptrend but has pulled back — 'on sale'. Good for timing an entry; it does NOT mean it will go up."],
  ["Extended / overbought", "It's run up fast (RSI over 70). Often pauses or pulls back."],
  ["Look-through", "Your TRUE bet on each company once ETFs (VOO, QQQ) are split into the stocks they hold."],
  ["Volatility", "How much it normally moves. Higher = bigger swings = riskier."],
];

function Money({ v }) {
  return <>${(v ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}</>;
}

function Mini({ r, onPick }) {
  const up = (r.gain_pct ?? 0) >= 0;
  return (
    <div className="hmini clickable" onClick={() => onPick(r.ticker)} title="Click for full analysis">
      <div className="hmini-top">
        <b>{r.ticker}</b>
        <span className="dim small"><Money v={r.value} /> · {r.weight}%</span>
      </div>
      {r.stage_label && (
        <div className={`stage-chip stage-${r.stage}`} title={r.stage_note}>
          {r.stage_emoji} {r.stage_label}
        </div>
      )}
      <div className="hmini-sub small">
        own {r.shares} · <span className={up ? "pos" : "neg"}>{up ? "+" : ""}{r.gain_pct}%</span>
      </div>
      {(r.take_profit_price || r.sma200_price) && (
        <div className="hmini-exit small" title="Your pre-set sell RULES (no prediction): take profit, cut losses, reduce risk if it breaks the 200-day line.">
          <span className="exit-label">Exit plan</span>
          {r.take_profit_price && <span className="pos">🎯 ${r.take_profit_price}</span>}
          {r.stop_price && <> · <span className="neg">🛡️ ${r.stop_price}</span></>}
          {r.sma200_price && (
            <> · <span className={r.below_200dma && !r.recovering ? "neg" : "dim"}>⚖️ ${r.sma200_price}</span></>
          )}
          {r.young_for_200d && <span className="dim"> · 🌱 too young for a 200-day read</span>}
        </div>
      )}
      {r.below_200dma && (
        r.recovering ? (
          <div className="risk-flag recovering small" title="Below its 200-day, but back above its faster 50-day line. The 200-day just lags a past dip, so this is a safety/context note (it's stopped being a falling knife) — NOT a buy signal. Backtested: 'recovering' doesn't beat just holding.">
            🌤️ below 200-day but recovering ({r.dist_200dma_pct}%)
          </div>
        ) : (
          <div className="risk-flag small" title="Below BOTH its 200-day and 50-day — still falling, not yet recovering. The higher-drawdown zone; consider reducing risk.">
            ⚠ below 200-day &amp; still weak ({r.dist_200dma_pct}%)
          </div>
        )
      )}
    </div>
  );
}

function EditTable({ holdings, cash, onSave, onCancel }) {
  const [rows, setRows] = useState(holdings.map((h) => ({ ticker: h.ticker, shares: h.shares, avg_cost: h.avg_cost ?? "" })));
  const [cashVal, setCashVal] = useState(cash ?? 0);
  const set = (i, k, v) => setRows((rs) => rs.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const add = () => setRows((rs) => [...rs, { ticker: "", shares: "", avg_cost: "" }]);
  const remove = (i) => setRows((rs) => rs.filter((_, j) => j !== i));
  const save = () => onSave(
    rows.filter((r) => r.ticker.trim() && Number(r.shares) > 0)
      .map((r) => ({ ticker: r.ticker.trim().toUpperCase(), shares: Number(r.shares), avg_cost: Number(r.avg_cost) || null })),
    Number(cashVal) || 0);

  return (
    <section className="card">
      <h3>Edit holdings &amp; cash</h3>
      <p className="muted small">Match your broker: fix shares / buy price, add the leftover cash, then Save.</p>
      <table className="bt holdings-table">
        <thead><tr><th>Ticker</th><th className="num">Shares</th><th className="num">Avg cost</th><th></th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td><input className="edit-in" value={r.ticker} onChange={(e) => set(i, "ticker", e.target.value)} /></td>
              <td className="num"><input className="edit-in num" value={r.shares} onChange={(e) => set(i, "shares", e.target.value)} /></td>
              <td className="num"><input className="edit-in num" value={r.avg_cost} onChange={(e) => set(i, "avg_cost", e.target.value)} /></td>
              <td><button className="alert-x" onClick={() => remove(i)}>✕</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="edit-actions">
        <button className="chip" onClick={add}>+ Add ticker</button>
        <label className="dim small">Cash $ <input className="edit-in num" value={cashVal} onChange={(e) => setCashVal(e.target.value)} /></label>
        <button className="chip on" onClick={save}>Save</button>
        <button className="chip" onClick={onCancel}>Cancel</button>
      </div>
    </section>
  );
}

function ImportPanel({ onParsed, onCancel }) {
  const [text, setText] = useState("");
  const [error, setError] = useState("");
  const doParse = (raw) => {
    const res = parseHoldingsCSV(raw);
    if (res.error) { setError(res.error); return; }
    onParsed(res.rows);
  };
  const onFile = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => doParse(String(reader.result));
    reader.readAsText(f);
  };
  return (
    <section className="card">
      <h3>📥 Import your holdings from a CSV</h3>
      <p className="muted small">
        Export your positions from Robinhood (Account → statements/reports), then upload the file or paste it below.
        We read only <b>Symbol</b>, <b>Quantity</b>, and <b>Average Cost</b>. You'll review everything before it saves.
      </p>
      <input type="file" accept=".csv,text/csv,text/plain" onChange={onFile} className="edit-in" />
      <p className="dim small" style={{ margin: "8px 0 4px" }}>…or paste the CSV text:</p>
      <textarea
        className="edit-in" rows={6} style={{ width: "100%", fontFamily: "monospace" }}
        value={text} onChange={(e) => setText(e.target.value)}
        placeholder={"Symbol,Quantity,Average Cost\nAAPL,5,180.20\nWMT,10,114.24"}
      />
      {error && <p className="error small">⚠ {error}</p>}
      <div className="edit-actions">
        <button className="chip on" onClick={() => doParse(text)} disabled={!text.trim()}>Parse &amp; review</button>
        <button className="chip" onClick={onCancel}>Cancel</button>
      </div>
      <p className="muted small">
        🔒 Safe by design: this reads only a file you choose, entirely on your computer. It has <b>no</b> connection to
        your Robinhood account and <b>cannot place trades</b>.
      </p>
    </section>
  );
}

export default function Portfolio({ data, loading, error, onPick, onSave, onReload }) {
  const [editing, setEditing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importRows, setImportRows] = useState(null);
  const [showGloss, setShowGloss] = useState(false);

  if (loading) return <div className="empty">Loading your portfolio… (~10s)</div>;
  if (error) return <div className="error">⚠ {error}</div>;
  if (!data) return null;

  const { summary, look_through: lt, risk, holdings, cash } = data;
  const c = lt?.concentration || {};

  if (importing) {
    return <ImportPanel onParsed={(rows) => { setImportRows(rows); setImporting(false); }} onCancel={() => setImporting(false)} />;
  }
  if (editing || importRows) {
    return (
      <EditTable
        holdings={importRows || holdings.map((h) => ({ ticker: h.ticker, shares: h.shares, avg_cost: h.avg_cost }))}
        cash={cash}
        onSave={(h, csh) => { onSave(h, csh); setEditing(false); setImportRows(null); }}
        onCancel={() => { setEditing(false); setImportRows(null); }}
      />
    );
  }

  const owned = holdings.filter((r) => r.value);
  const grouped = BUCKETS.map((b) => ({
    ...b,
    items: owned.filter((r) => (r.bucket || "hold") === b.key).sort((a, z) => z.value - a.value),
  })).filter((g) => g.items.length);

  return (
    <div className="portfolio">
      <HealthCheck holdings={holdings} />

      {summary.failed_tickers?.length > 0 && (
        <p className="error small">
          ⚠ Couldn't fetch data for <b>{summary.failed_tickers.join(", ")}</b> — excluded from every total and
          view below (check the ticker is correct, or the market may be closed for it).
        </p>
      )}

      {/* Top summary bar */}
      <section className="card pf-top">
        <div>
          <span className="dim small">Total value</span>
          <div className="verdict-big"><Money v={summary.total_value} /></div>
        </div>
        <div className="pf-top-stats">
          <div className="kv"><span>Gain/Loss</span><b className={summary.total_gain >= 0 ? "pos" : "neg"}>
            {summary.total_gain >= 0 ? "+" : ""}<Money v={summary.total_gain} /> ({summary.total_gain_pct}%)</b></div>
          <div className="kv"><span>Invested</span><b><Money v={summary.invested} /></b></div>
          <div className="kv"><span>Cash</span><b><Money v={summary.cash} /></b></div>
        </div>
        <div className="pf-top-actions">
          <button className="chip" onClick={() => setImporting(true)}>📥 Import CSV</button>
          <button className="chip" onClick={() => setEditing(true)}>Edit</button>
        </div>
      </section>

      <ExposureXray lt={lt} />

      <ExitAlerts holdings={holdings} onPick={onPick} />

      <p className="dim small" style={{ margin: "-4px 2px 0" }}>
        Below: your holdings grouped by current state — <b>not</b> a prediction of which way they'll go. Click any stock for the full breakdown.
        <br />Each shows a <b>trend stage</b> (🟢 Uptrend · 🟡 Topping · 🌤️ Recovering · 🔴 Declining · ⚪ Basing) — this is <b>risk context</b> (is it healthy or broken?), <b>not</b> a buy signal: I backtested "buy the uptrend / buy the recovery" and neither beat just holding.
        <br />And an <b>Exit plan</b> (pre-set sell rules, no prediction): 🎯 take profit · 🛡️ cut losses · ⚖️ 200-day risk level (reduce if it breaks below).
      </p>

      {/* Action buckets */}
      {grouped.map((g) => (
        <section key={g.key} className={`card bucket bucket-${g.key}`}>
          <div className="bucket-head">
            <h3>{g.emoji} {g.label} <span className="dim">({g.items.length})</span></h3>
          </div>
          <p className="muted small bucket-meaning">{g.meaning}</p>
          <div className="hminis">
            {g.items.map((r) => <Mini key={r.ticker} r={r} onPick={onPick} />)}
          </div>
        </section>
      ))}

      <DrawdownCard risk={risk} drawdown={data.drawdown} />
      <FeeCard fees={data.fees} />

      <section className="card">
        <button className="link-btn" onClick={() => setShowGloss((s) => !s)}>❓ What do these terms mean? {showGloss ? "▴" : "▾"}</button>
        {showGloss && (
          <dl className="glossary">
            {GLOSSARY.map(([t, d]) => (<div key={t}><dt>{t}</dt><dd>{d}</dd></div>))}
          </dl>
        )}
      </section>

      <p className="muted small">{data.disclaimer}</p>
    </div>
  );
}
