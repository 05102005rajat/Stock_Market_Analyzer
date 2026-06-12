// Live(ish) price bar — polls /api/quote/<ticker> every 60s so the price you
// see is the latest delayed quote, not yesterday's close. No more re-clicking
// Analyze just to refresh the number.
import { useEffect, useState } from "react";

export default function LivePrice({ ticker, initial }) {
  const [q, setQ] = useState(initial || null);

  useEffect(() => {
    if (!ticker) return;
    let alive = true;
    const pull = async () => {
      try {
        const r = await fetch(`/api/quote/${ticker}`);
        const j = await r.json();
        if (alive && j && j.available) setQ(j);
      } catch {
        /* keep last quote on network hiccups */
      }
    };
    pull();
    const id = setInterval(pull, 60_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [ticker]);

  if (!q || !q.available) return null;
  const up = (q.change_pct ?? 0) >= 0;
  return (
    <section className="card live-price">
      <div className="insights-head">
        <h3>{ticker} — live</h3>
        <span className="dim small">~15 min delayed · auto-refreshes</span>
      </div>
      <div className="live-row">
        <span className="live-big">{q.price}</span>
        <span className={`live-chg ${up ? "pos" : "neg"}`}>
          {up ? "▲" : "▼"} {q.change_pct > 0 ? "+" : ""}
          {q.change_pct}%
        </span>
      </div>
      {q.day_low != null && q.day_high != null && (
        <div className="kv">
          <span>Day range</span>
          <b>
            {q.day_low} – {q.day_high}
          </b>
        </div>
      )}
    </section>
  );
}
