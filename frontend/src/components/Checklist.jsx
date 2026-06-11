// The Buy Checklist — every engine's verdict in one place, color-coded,
// with the catalyst headlines at the bottom. A checklist to read, not a
// score to obey.
const DOT = { good: "●", warn: "●", bad: "●", info: "○" };

export default function Checklist({ checklist }) {
  if (!checklist || !checklist.available) return null;
  return (
    <section className="card">
      <div className="insights-head">
        <h3>The full picture</h3>
      </div>
      <ul className="checklist">
        {checklist.factors.map((f, i) => (
          <li key={i} className={`check-item ${f.status}`}>
            <span className={`check-dot ${f.status}`}>{DOT[f.status] || "○"}</span>
            <div>
              <b>{f.name}</b>
              <p>{f.line}</p>
            </div>
          </li>
        ))}
      </ul>
      {checklist.headlines && checklist.headlines.length > 0 && (
        <>
          <div className="kv">
            <span>Why it might be moving</span>
            <b />
          </div>
          <ul className="headline-list">
            {checklist.headlines.map((h, i) => (
              <li key={i}>
                {h.link ? (
                  <a href={h.link} target="_blank" rel="noreferrer">
                    {h.title}
                  </a>
                ) : (
                  h.title
                )}
                <span className="dim small">
                  {" "}
                  {h.publisher ? `— ${h.publisher}` : ""} {h.when || ""}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      <span className="dim small">{checklist.caveat}</span>
    </section>
  );
}
