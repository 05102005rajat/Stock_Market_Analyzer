// The Dip-Buy verdict — the one signal with a real, tested edge (short-term mean
// reversion: buy oversold dips in an uptrend). Shows an actionable buy/target/stop
// when active, with THIS stock's own backtested win-rate. Honest: buy-side only.
export default function DipSignal({ dip, ticker }) {
  if (!dip?.available) return null;
  const h = dip.history;
  const winPct = Math.round(h.win_rate * 100);

  if (dip.active && dip.plan) {
    const p = dip.plan;
    return (
      <section className="card dip dip-active">
        <h3>🟢 Dip-buy signal — BUY</h3>
        <p className="recent-line">
          {ticker} is <b>oversold</b> (RSI2 {dip.rsi2}) but still in an uptrend — historically a buyable dip.
        </p>
        <div className="dip-plan">
          <div><span className="dim small">Buy near</span><b className="pos">${p.buy_near}</b></div>
          <div><span className="dim small">Target (typical bounce)</span><b className="pos">${p.target} (+{p.target_pct}%)</b></div>
          <div><span className="dim small">Stop</span><b className="neg">${p.stop} ({p.stop_pct}%)</b></div>
        </div>
        <p className="recent-line small">
          This stock's dips bounced <b>{winPct}% of the time</b> ({h.n_trades} times), averaging
          <b className="pos"> +{h.avg_per_trade_pct}%</b> per trade — a real but modest edge.
        </p>
        <p className="muted small">{dip.disclaimer}</p>
      </section>
    );
  }

  if (!dip.in_uptrend) {
    return (
      <section className="card dip">
        <h3>Dip-buy: not now</h3>
        <p className="recent-line small">
          {ticker} is in a <b>downtrend</b> — a dip here is a falling knife, not a buy. The mean-reversion
          edge only works while a stock is above its 200-day average.
        </p>
      </section>
    );
  }

  return (
    <section className="card dip">
      <h3>Dip-buy: waiting for a pullback</h3>
      <p className="recent-line small">
        {ticker} isn't oversold right now (RSI2 {dip.rsi2}). When it <i>does</i> dip in this uptrend, its
        dips have bounced <b>{winPct}%</b> of the time historically — so wait for the pullback.
      </p>
      <p className="muted small">{dip.disclaimer}</p>
    </section>
  );
}
