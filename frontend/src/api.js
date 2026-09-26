// Thin client for the Flask analyze endpoint.

// Parsing the body before checking res.ok meant a non-JSON error response —
// a Flask HTML 500, a Vite proxy 502 — threw "Unexpected token '<'" and the
// real status never surfaced. Read as text first, then decide.
async function request(url, init) {
  let res;
  try {
    res = await fetch(url, init);
  } catch (e) {
    throw new Error(`Network error: ${e.message}`);
  }
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // Not JSON — surface the status rather than a parse error.
    if (!res.ok) throw new Error(`Request failed (${res.status} ${res.statusText})`);
    throw new Error("Server returned a malformed response");
  }
  if (!res.ok) {
    throw new Error(body?.error || `Request failed (${res.status})`);
  }
  return body;
}

export async function analyze({ ticker, period, interval, horizon }) {
  const params = new URLSearchParams({ ticker, period, interval, horizon });
  return request(`/api/analyze?${params.toString()}`);
}

// Portfolio view: your holdings, look-through exposure, and risk.
export async function getPortfolio() {
  return request("/api/portfolio");
}

// Save edited holdings + cash and recompute the portfolio.
export async function savePortfolio(holdings, cash) {
  return request("/api/portfolio", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ holdings, cash }),
  });
}

// Strategy lab: backtest famous strategies on one stock vs buy & hold.
export async function getStrategies(ticker, period = "1y") {
  return request(`/api/strategies?ticker=${encodeURIComponent(ticker)}&period=${period}`);
}

// Buy-zone scanner: rule-based entry setups (not predictions).
export async function getScan(horizon = "1m") {
  return request(`/api/scan?horizon=${horizon}`);
}

export async function getForecastRecord(ticker, horizon = 10) {
  return request(`/api/forecast-record?ticker=${encodeURIComponent(ticker)}&horizon=${horizon}`);
}
