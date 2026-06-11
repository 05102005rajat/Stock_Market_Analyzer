// Thin client for the Flask analyze endpoint.
export async function analyze({ ticker, period, interval, horizon }) {
  const params = new URLSearchParams({ ticker, period, interval, horizon });
  const res = await fetch(`/api/analyze?${params.toString()}`);
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body.error || `Request failed (${res.status})`);
  }
  return body;
}

// Portfolio view: your holdings, look-through exposure, and risk.
export async function getPortfolio() {
  const res = await fetch("/api/portfolio");
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}

// Save edited holdings + cash and recompute the portfolio.
export async function savePortfolio(holdings, cash) {
  const res = await fetch("/api/portfolio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holdings, cash }),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}

// Strategy lab: backtest famous strategies on one stock vs buy & hold.
export async function getStrategies(ticker, period = "1y") {
  const res = await fetch(`/api/strategies?ticker=${encodeURIComponent(ticker)}&period=${period}`);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}

// Buy-zone scanner: rule-based entry setups (not predictions).
export async function getScan(horizon = "1m") {
  const res = await fetch(`/api/scan?horizon=${horizon}`);
  const body = await res.json();
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}
