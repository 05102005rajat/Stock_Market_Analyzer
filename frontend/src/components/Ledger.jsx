// Signal Ledger — the app's own live, out-of-sample track record. Every signal
// it emits is logged and auto-scored at 5/21/63 days. This is the honesty
// capstone: if a signal's realized edge vs SPY is ~0, it's descriptive, not
// predictive — and this page proves it either way.
import { useEffect, useState } from "react";

export default function Ledger() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/ledger")
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="card">Scoring the ledger…</div>;
  if (!data) return <div className="card">Ledger unavailable.</div>;

  const cal = data.calibration || {};
  return (
    <div className="ledger-page">
      <section className="card">
        <div className="insights-head">
          <h3>Signal ledger — live scoreboard</h3>
        </div>
        {!cal.available ? (
          <p className="rec-detail">{cal.message || "No matured signals yet."}</p>
        ) : (
          <>
            <p className="rec-detail">{cal.note}</p>
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Signal type</th>
                  <th>n</th>
                  <th>Win</th>
                  <th>Avg 21d</th>
                  <th>Edge vs SPY</th>
                </tr>
              </thead>
              <tbody>
                {(cal.type_stats || []).map((t) => (
                  <tr key={t.signal_type}>
                    <td>{t.signal_type}</td>
                    <td>{t.n}</td>
                    <td>{t.win_rate}%</td>
                    <td className={t.avg_dir_return_21d >= 0 ? "pos" : "neg"}>
                      {t.avg_dir_return_21d > 0 ? "+" : ""}
                      {t.avg_dir_return_21d}%
                    </td>
                    <td className={t.avg_edge_vs_spy_21d >= 0 ? "pos" : "neg"}>
                      {t.avg_edge_vs_spy_21d > 0 ? "+" : ""}
                      {t.avg_edge_vs_spy_21d}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(cal.calibration_curve || []).length > 0 && (
              <>
                <h4 className="dim">Calibration — predicted vs realized</h4>
                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Predicted band</th>
                      <th>n</th>
                      <th>Realized up-rate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cal.calibration_curve.map((c) => (
                      <tr key={c.predicted_band}>
                        <td>{c.predicted_band}</td>
                        <td>{c.n}</td>
                        <td>{c.realized_up_rate}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </>
        )}
      </section>

      <section className="card">
        <div className="insights-head">
          <h3>Recent logged signals</h3>
        </div>
        <table className="ledger-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Ticker</th>
              <th>Type</th>
              <th>Dir</th>
              <th>21d</th>
            </tr>
          </thead>
          <tbody>
            {(data.recent || []).map((r) => (
              <tr key={r.id}>
                <td>{r.ts}</td>
                <td>{r.ticker}</td>
                <td>{r.signal_type}</td>
                <td>{r.direction}</td>
                <td className={r.ret_21 == null ? "dim" : r.ret_21 >= 0 ? "pos" : "neg"}>
                  {r.ret_21 == null ? "pending" : `${(r.ret_21 * 100).toFixed(1)}%`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
