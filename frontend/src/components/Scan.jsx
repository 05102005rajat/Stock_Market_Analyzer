// Buy-Zone Scanner: rule-based ENTRY setups with calibrated levels — NOT a
// winner predictor (backtested: top-5 does not beat buy-and-hold). The honest
// disclaimer is intentionally prominent.
function SetupCard({ r, onPick, horizonLabel }) {
  return (
    <div className="setup clickable" onClick={() => onPick(r.ticker)} title="Click for full analysis">
      <div className="setup-head">
        <b className="setup-ticker">{r.ticker}</b>
        <span className="setup-score" title="Buy-the-dip-in-an-uptrend score (entry timing, not edge)">
          setup {r.setup_score}
        </span>
      </div>
      <div className="setup-grid">
        <div><span className="dim small">Price</span><b>{r.price}</b></div>
        <div><span className="dim small">Buy zone</span><b className="pos">{r.buy_zone[0]}–{r.buy_zone[1]}</b></div>
        <div><span className="dim small">Target ({horizonLabel})</span><b className="pos">{r.take_profit} (+{r.take_profit_pct}%)</b></div>
        <div><span className="dim small">Stop</span><b className="neg">{r.stop}</b></div>
        <div><span className="dim small">RSI</span><b>{r.rsi}</b></div>
        <div><span className="dim small">vs SPY</span><b className={r.rs_excess_pct >= 0 ? "pos" : "neg"}>{r.rs_excess_pct >= 0 ? "+" : ""}{r.rs_excess_pct}%</b></div>
      </div>
      <div className="setup-tags">
        {r.in_uptrend && <span className="badge pos">uptrend</span>}
        {r.outperforming && <span className="badge pos">leader</span>}
        {r.reversal_candle && <span className="badge pos">reversal</span>}
      </div>
    </div>
  );
}

function WatchRow({ r, onPick }) {
  const b = r.breakout;
  return (
    <div className="watch-row clickable" onClick={() => onPick(r.ticker)}
         title="Watch level only — NOT a buy signal. Click for full analysis.">
      <div className="watch-main">
        <b>{r.ticker}</b> <span className="dim small">${r.price}</span>
        {b.status === "broke" ? (
          <span className="badge neutral">{b.fresh ? "fresh break" : "above"} R ${b.level} ({b.dist_pct >= 0 ? "+" : ""}{b.dist_pct}%)</span>
        ) : (
          <span className="badge neutral">{Math.abs(b.dist_pct)}% under R ${b.level}</span>
        )}
      </div>
      <div className="watch-flags small dim">
        {b.overbought && <span className="neg">⚠ overbought (RSI {r.rsi}) — don't chase</span>}
        {b.overhead_200 && <span> · 🧱 200-day wall just above ({b.dist_200_pct}%)</span>}
        {!b.overbought && !b.overhead_200 && (
          <span>{b.status === "broke"
            ? `if it pulls back to ~$${b.level} and holds, that retest-dip is a better entry than chasing here`
            : "watching for a break — but the edge is the pullback, not the breakout"}</span>
        )}
      </div>
    </div>
  );
}

function DipAlerts({ d, onPick }) {
  const a = d.dip_alerts;
  if (!a) return null;
  return (
    <section className="card">
      <div className="insights-head"><h3>🎯 Dip-buy alerts — the one tested edge, firing now</h3></div>
      {a.active.length === 0 ? (
        <p className="muted">No dip firing right now — nothing oversold inside an uptrend. Cash is a position; wait for the pullback (watchlist below).</p>
      ) : (
        <>
          <p className="dim small"><b>{a.active.length}</b> name{a.active.length > 1 ? "s" : ""} flashing an oversold dip in an uptrend. Buy low, exit into the bounce — not on a fixed day.</p>
          <div className="setups">
            {a.active.map((r) => (
              <div key={r.ticker} className="setup dip-fire clickable" onClick={() => onPick(r.ticker)}
                   title="Oversold dip inside an uptrend — the tested edge. Click for full analysis.">
                <div className="setup-head">
                  <b className="setup-ticker">🟢 {r.ticker}</b>
                  <span className="setup-score" title="This stock's own backtested dip win-rate">{r.dip_win_pct}% win · {r.dip_n_trades} trades</span>
                </div>
                <div className="setup-grid">
                  <div><span className="dim small">Buy near</span><b className="pos">${r.dip_plan.buy_near}</b></div>
                  <div><span className="dim small">Target (typical bounce)</span><b className="pos">${r.dip_plan.target} (+{r.dip_plan.target_pct}%)</b></div>
                  <div><span className="dim small">Stop</span><b className="neg">${r.dip_plan.stop} ({r.dip_plan.stop_pct}%)</b></div>
                  <div><span className="dim small">RSI2</span><b>{r.dip_rsi2}</b></div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
      {a.waiting.length > 0 && (
        <p className="dim small" style={{ marginTop: 8 }}>🟡 <b>In an uptrend, waiting for a pullback</b> (no action yet): {a.waiting.slice(0, 10).map((r) => `${r.ticker} ${r.dip_win_pct}%`).join(" · ")}</p>
      )}
      {a.downtrend.length > 0 && (
        <p className="dim small">⚪ <b>Edge off</b> (downtrend / below 200-day — a dip here is a falling knife): {a.downtrend.slice(0, 12).join(", ")}</p>
      )}
      <p className="muted small">High win-rate, small per-trade base hits. Exit by RULE — into the bounce, at target, or the −8% stop — never on a fixed day-count. The edge is in the exit, not the calendar.</p>
    </section>
  );
}

const HORIZONS = [["1w", "1 week"], ["2w", "2 weeks"], ["1m", "1 month"]];

export default function Scan({ data, loading, error, horizon, onHorizon, onPick, onReload }) {
  if (loading) return <div className="empty">Scanning the universe for buy-zone setups…</div>;
  if (error) return <div className="error">⚠ {error}</div>;
  if (!data) return null;
  const hLabel = data.horizon_label || "1 month";

  return (
    <div className="portfolio">
      <div className="focus-bar" style={{ display: "block" }}>
        <b>⚠ These are ENTRY setups, not predictions of which will rise.</b>{" "}
        <span className="small">Direction is a coin flip — backtested, this rank does not beat buy-and-hold.
        Use it to time entries on names you already want and to size/stop them, never to pick winners.</span>
      </div>

      <DipAlerts data={data} d={data} onPick={onPick} />

      <section className="card">
        <div className="insights-head">
          <h3>Full ranking — every name scored by dip-readiness</h3>
          <div className="scan-controls">
            <span className="dim small">Hold for:</span>
            {HORIZONS.map(([k, label]) => (
              <button key={k} className={`chip ${horizon === k ? "on" : ""}`} onClick={() => onHorizon(k)}>{label}</button>
            ))}
            <button className="chip" onClick={onReload}>Rescan</button>
          </div>
        </div>
        <p className="dim small">Targets are sized to a ~{hLabel} hold — the price level reached about 2 of 3 times within {hLabel} historically. Pick a longer hold for bigger targets.</p>
        {data.top.length === 0 ? (
          <p className="muted">No qualifying setups right now (nothing in an uptrend is on sale). That's fine — cash is a position.</p>
        ) : (
          <div className="setups">
            {data.top.map((r) => <SetupCard key={r.ticker} r={r} onPick={onPick} horizonLabel={hLabel} />)}
          </div>
        )}
      </section>

      {data.breakout_watch && (data.breakout_watch.broke.length > 0 || data.breakout_watch.coiling.length > 0) && (
        <section className="card">
          <div className="insights-head"><h3>🔭 Breakout watch — levels, <span className="neg">not</span> buy signals</h3></div>
          <p className="dim small">{data.breakout_watch.note}</p>
          {data.breakout_watch.broke.length > 0 && (
            <div className="watch-group">
              <h4 className="watch-sub">⚡ Just broke its month-long ceiling</h4>
              {data.breakout_watch.broke.map((r) => <WatchRow key={r.ticker} r={r} onPick={onPick} />)}
            </div>
          )}
          {data.breakout_watch.coiling.length > 0 && (
            <div className="watch-group">
              <h4 className="watch-sub">🪤 Coiling under resistance — watch for a break</h4>
              {data.breakout_watch.coiling.map((r) => <WatchRow key={r.ticker} r={r} onPick={onPick} />)}
            </div>
          )}
          <p className="muted small">Reminder: a break is information about a level, not an edge. To actually buy, wait for the
          oversold pullback in the buy-zone list above — that's the only setup that beat holding.</p>
        </section>
      )}

      <p className="muted small">{data.disclaimer}</p>
    </div>
  );
}
