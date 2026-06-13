// Command palette — press Cmd/Ctrl+K anywhere to jump to a ticker or a section.
// The single biggest "feels pro" navigation upgrade: keyboard-driven, no
// hunting through tabs. Type a ticker and Enter to analyze it; type a page
// name to switch views.
import { useEffect, useMemo, useRef, useState } from "react";

const PAGES = [
  { id: "analyze", label: "Analyze a stock", hint: "search & full breakdown" },
  { id: "portfolio", label: "My Portfolio", hint: "holdings, exposure, exits" },
  { id: "scan", label: "Buy Zones", hint: "scanner" },
  { id: "strategies", label: "Strategy Lab", hint: "backtests" },
  { id: "ledger", label: "Signal Ledger", hint: "live scoreboard" },
  { id: "help", label: "Help", hint: "what each card means" },
];

export default function CommandPalette({ open, onClose, onTicker, onPage, owned = [], recent = [] }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setSel(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  // Build the result list: matching pages + matching owned/recent tickers +
  // the raw typed ticker as a fallback "analyze X" action.
  const results = useMemo(() => {
    const Q = q.trim().toUpperCase();
    const pageHits = PAGES.filter((p) => !Q || p.label.toUpperCase().includes(Q))
      .map((p) => ({ type: "page", ...p }));
    const tickerPool = Array.from(new Set([...owned, ...recent]));
    const tickerHits = tickerPool
      .filter((t) => !Q || t.includes(Q))
      .slice(0, 8)
      .map((t) => ({ type: "ticker", id: t, label: t, hint: owned.includes(t) ? "owned" : "recent" }));
    const out = [...tickerHits, ...pageHits];
    if (Q && !tickerPool.includes(Q) && /^[A-Z.]{1,6}$/.test(Q)) {
      out.unshift({ type: "ticker", id: Q, label: `Analyze ${Q}`, hint: "go" });
    }
    return out;
  }, [q, owned, recent]);

  useEffect(() => {
    setSel((s) => Math.min(s, Math.max(0, results.length - 1)));
  }, [results.length]);

  if (!open) return null;

  const choose = (r) => {
    if (!r) return;
    if (r.type === "ticker") onTicker(r.id);
    else onPage(r.id);
    onClose();
  };

  const onKey = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSel((s) => Math.min(s + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSel((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(results[sel]);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <div className="cmdk-overlay" onClick={onClose}>
      <div className="cmdk" onClick={(e) => e.stopPropagation()}>
        <input
          ref={inputRef}
          className="cmdk-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={onKey}
          placeholder="Jump to a ticker or page…  (↑↓ to move, Enter to go, Esc to close)"
          spellCheck={false}
        />
        <ul className="cmdk-list">
          {results.map((r, i) => (
            <li
              key={`${r.type}-${r.id}`}
              className={`cmdk-item ${i === sel ? "sel" : ""}`}
              onMouseEnter={() => setSel(i)}
              onClick={() => choose(r)}
            >
              <span className="cmdk-icon">{r.type === "ticker" ? "📈" : "▸"}</span>
              <span className="cmdk-label">{r.label}</span>
              <span className="cmdk-hint dim small">{r.hint}</span>
            </li>
          ))}
          {results.length === 0 && <li className="cmdk-item dim">No matches</li>}
        </ul>
      </div>
    </div>
  );
}
