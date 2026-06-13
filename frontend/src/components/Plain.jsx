// Plain-English helpers used across cards.
//
// <Term word="RSI">RSI</Term> — wraps a jargon word so hovering/tapping shows a
// plain definition (dotted underline cues that it's explainable).
//
// <Plain on={plainMode}>simple sentence</Plain> — renders a friendly one-liner
// ONLY when Plain English mode is on, so technical users aren't slowed down.

const GLOSSARY = {
  rsi: "RSI is a 0–100 'speedometer' for how hard a stock has been bought or sold lately. Under 30 = beaten down (a possible bargain), over 70 = run up hot.",
  rsi2: "A faster version of RSI (2-day). Same idea: low = recently dropped a lot, high = recently jumped a lot.",
  oversold: "Fallen fast and far enough that it MIGHT be due for a bounce — like a stretched rubber band. Odds, not a promise.",
  overbought: "Risen fast and far enough that it might be due for a rest or pullback.",
  resistance: "A price 'ceiling' the stock has struggled to break above before. Getting through it often needs extra buying.",
  support: "A price 'floor' the stock has tended to bounce up from before.",
  "200-day": "The average price over roughly the last 10 months. Above it = generally healthy/uptrend; below it = generally weak.",
  "50-day": "The average price over roughly the last 2.5 months — a faster trend gauge than the 200-day.",
  macd: "A momentum gauge built from two moving averages. Above its signal line = upward momentum; below = downward.",
  atr: "Average True Range — how much the stock typically moves in a day. Used to set a sensible stop-loss distance.",
  "stop": "A pre-decided price where you'd sell to cap a loss if the trade goes against you.",
  "take-profit": "A pre-decided price where you'd sell to lock in a gain.",
  volatility: "How wildly the price swings. High volatility = bigger up AND down moves.",
  breakout: "When price pushes ABOVE a ceiling (resistance) it had been stuck under.",
  "uptrend": "Price is generally rising over time — higher highs and higher lows.",
  "downtrend": "Price is generally falling over time.",
  drawdown: "How far a stock has fallen from its recent peak — the 'how much it hurt' number.",
  "insider": "People who work at the company (executives, directors). Their buying/selling is disclosed to the SEC.",
  "cluster buying": "Several different insiders buying around the same time — a stronger signal than one person.",
  consensus: "The average view of the Wall Street analysts who cover the stock.",
  "price target": "Where an analyst thinks the stock will be in ~12 months. Optimistic on average — read the direction, not the exact number.",
  candlestick: "The little bars on a price chart. Their shapes have names traders use as weak hints — not reliable predictions.",
  "relative strength": "Whether the stock is outperforming or lagging the overall market (the S&P 500).",
  sharpe: "A reward-for-risk score: return earned per unit of bumpiness. Higher is better.",
  kelly: "A formula for how big a bet to make given your edge. Most people use a small FRACTION of it to avoid wild swings.",
  "golden cross": "When the 50-day average crosses ABOVE the 200-day — often read as a longer-term bullish sign.",
  beta: "How much the stock moves relative to the market. Above 1 = swings more than the market; below 1 = calmer.",
};

export function Term({ word, children }) {
  const key = (word || (typeof children === "string" ? children : "")).toLowerCase().trim();
  const def = GLOSSARY[key];
  if (!def) return <>{children}</>;
  return (
    <span className="glossary-term" title={def} tabIndex={0}>
      {children}
    </span>
  );
}

export function Plain({ on, children }) {
  if (!on) return null;
  return <p className="plain-note">💡 {children}</p>;
}

export default Term;
