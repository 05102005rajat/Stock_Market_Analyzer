// The Dip-Buy verdict — the one signal with a real, tested edge (short-term mean
// reversion: buy oversold dips in an uptrend). Shows an actionable buy/target/stop
// when active, with THIS stock's own backtested win-rate. Honest: buy-side only.
import { Plain } from "./Plain";

export default function DipSignal({ dip, ticker, plainMode = false }) {
  if (!dip?.available) return null;
  const h = dip.history;
  const winPct = Math.round(h.win_rate * 100);

  if (dip.active && dip.plan) {
    const p = dip.plan;
    return (
      <section className="card dip dip-active">
        <h3>🟢 Dip-buy signal — BUY</h3>
        <Plain on={plainMode}>
          {ticker} has dropped enough to look like a short-term bargain, and it's still in an uptrend.
          Stocks in this exact situation have bounced back {winPct}% of the time. Good odds — not a sure thing.
        </Plain>
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
        <Plain on={plainMode}>
          {ticker} is falling and below its long-term average. Buying a falling stock here is like catching a
          falling knife — the "buy the dip" idea only works when a stock is still in an uptrend.
        </Plain>
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
      <Plain on={plainMode}>
        {ticker} hasn't dropped enough to be a bargain right now. The patient move is to WAIT for it to dip
        rather than buy at today's price — its past dips bounced {winPct}% of the time.
      </Plain>
      <p className="recent-line small">
        {ticker} isn't oversold right now (RSI2 {dip.rsi2}). When it <i>does</i> dip in this uptrend, its
        dips have bounced <b>{winPct}%</b> of the time historically — so wait for the pullback.
      </p>
      <p className="muted small">{dip.disclaimer}</p>
    </section>
  );
}
