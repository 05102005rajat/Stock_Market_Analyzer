// Parse a brokerage positions CSV (e.g. a Robinhood export) into holdings rows.
// Read-only and local: it only reads text you hand it. It maps three columns —
// Symbol, Quantity, Average Cost — flexibly by name, skips junk, and merges
// duplicate tickers. Returns { rows } or { error }.

export function splitCSVLine(line) {
  const out = [];
  let cur = "";
  let q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (q) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') q = false;
      else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { out.push(cur); cur = ""; }
    else cur += ch;
  }
  out.push(cur);
  return out;
}

const num = (s) => {
  const v = parseFloat(String(s || "").replace(/[^0-9.\-]/g, ""));
  return Number.isFinite(v) ? v : null;
};

export function parseHoldingsCSV(text) {
  const lines = String(text || "").split(/\r?\n/).filter((l) => l.trim());
  if (!lines.length) return { error: "The file looks empty." };

  // Find the header row: the first line that has both a symbol-ish and a quantity-ish column.
  let header = null;
  let hi = -1;
  for (let i = 0; i < lines.length; i++) {
    const cells = splitCSVLine(lines[i]).map((c) => c.trim().toLowerCase());
    const hasSym = cells.some((c) => c.includes("symbol") || c.includes("ticker") || c.includes("instrument"));
    const hasQty = cells.some((c) => c.includes("quantity") || c.includes("shares") || c === "qty");
    if (hasSym && hasQty) { header = cells; hi = i; break; }
  }
  if (hi < 0) {
    return { error: "Couldn't find a header with Symbol and Quantity columns — make sure it's a positions/holdings export." };
  }

  const col = (...names) => header.findIndex((h) => names.some((n) => h.includes(n)));
  const ti = col("symbol", "ticker", "instrument");
  const qi = col("quantity", "shares", "qty");
  // Per-share cost only. "cost basis" is excluded on purpose: in Schwab and
  // E*Trade exports it's the TOTAL dollar cost of the lot, so treating it as a
  // per-share price turned a 10-share/$1,500-basis position into avg_cost 1500
  // and showed a ~90% loss. It's picked up separately below and divided out.
  const ci = col("average cost", "avg cost", "average buy", "avg price", "average price", "cost/share", "cost per share");
  const bi = col("cost basis", "total cost");

  const merged = {};
  for (let i = hi + 1; i < lines.length; i++) {
    const r = splitCSVLine(lines[i]);
    // Keep hyphens: BRK-B became BRKB, which the backend can't fetch and which
    // then vanished silently into summary.failed_tickers.
    const ticker = (r[ti] || "").trim().toUpperCase().replace(/[^A-Z.\-]/g, "");
    const shares = num(r[qi]);
    if (!ticker || !(shares > 0)) continue;            // skip cash rows, blanks, totals
    let avg = ci >= 0 ? num(r[ci]) : null;
    if (avg == null && bi >= 0) {
      // Only a total-cost column available — convert it to per-share.
      const basis = num(r[bi]);
      if (basis != null && shares > 0) avg = basis / shares;
    }
    if (!merged[ticker]) {
      merged[ticker] = { ticker, shares, avg_cost: avg };
    } else {
      const m = merged[ticker];                        // same ticker twice -> share-weighted avg cost
      const tot = m.shares + shares;
      if (m.avg_cost != null && avg != null) m.avg_cost = (m.avg_cost * m.shares + avg * shares) / tot;
      else m.avg_cost = m.avg_cost ?? avg;
      m.shares = tot;
    }
  }

  const rows = Object.values(merged).map((r) => ({
    ...r,
    shares: Math.round(r.shares * 1e6) / 1e6,
    avg_cost: r.avg_cost != null ? Math.round(r.avg_cost * 100) / 100 : null,
  }));
  if (!rows.length) return { error: "No valid stock positions found in the file." };
  return { rows };
}
