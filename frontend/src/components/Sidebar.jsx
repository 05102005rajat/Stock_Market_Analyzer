// Right-hand analytics summary: trend verdict, key indicator snapshot,
// detected patterns, support/resistance levels, and forecast metrics.
import MultiTimeframe from "./MultiTimeframe";
import Insights from "./Insights";
import Minervini from "./Minervini";
import Backtest from "./Backtest";
import SignalGauge from "./SignalGauge";
import TradePlan from "./TradePlan";
import RecentAction from "./RecentAction";
import DipSignal from "./DipSignal";
import Resistance from "./Resistance";
import SectorPulse from "./SectorPulse";
import EarningsWatch from "./EarningsWatch";
import Pros from "./Pros";
import GapCard from "./GapCard";
import ExtensionCard from "./ExtensionCard";
import Checklist from "./Checklist";
import PatternRead from "./PatternRead";
import LivePrice from "./LivePrice";
import ForecastRecord from "./ForecastRecord";
import InsiderCard from "./InsiderCard";
import SizingCard from "./SizingCard";

export default function Sidebar({ data, focus, onFocus, plainMode = false }) {
  if (!data) return null;
  const { trend, latest = {}, patterns = [], levels = {}, forecast, meta } = data;
  const mtf = data.multiTimeframe;
  const candlesticks = data.candlesticks || [];
  const vol = data.volume || {};
  const focusKey = focus?.key;
  const focusSignal = (key, anchor) => onFocus && onFocus({ ...anchor, key });
  const resistance = levels.resistance || [];
  const support = levels.support || [];

  const direction = trend?.direction || "sideways";
  const trendColor =
    direction === "uptrend" ? "pos" : direction === "downtrend" ? "neg" : "neutral";

  const fcPoints = forecast?.points || [];
  const fcLast = fcPoints[fcPoints.length - 1];
  const fcChange =
    fcLast && latest.close ? ((fcLast.value - latest.close) / latest.close) * 100 : null;
  const fcUp = fcChange != null && fcChange >= 0;

  return (
    <aside className="sidebar">
      <RecentAction data={data} plainMode={plainMode} />

      <LivePrice ticker={data.ticker} initial={data.quote} />

      <Checklist checklist={data.checklist} plainMode={plainMode} />

      <PatternRead read={data.patternRead} plainMode={plainMode} />

      <DipSignal dip={data.dipSignal} ticker={data.ticker} plainMode={plainMode} />

      <Resistance res={data.resistance} onFocus={onFocus} focusKey={focusKey} plainMode={plainMode} />

      <SizingCard sizing={data.sizing} ticker={data.ticker} plainMode={plainMode} />

      <EarningsWatch watch={data.earningsWatch} />

      <GapCard gap={data.gap} />

      <ExtensionCard ext={data.extension} />

      <Pros pros={data.pros} plainMode={plainMode} />

      <InsiderCard insider={data.insider} plainMode={plainMode} />

      <SectorPulse pulse={data.sectorPulse} />

      <SignalGauge signal={data.signal} />

      <TradePlan plan={data.tradePlan} />

      <Insights insights={data.insights} onFocus={onFocus} focusKey={focusKey} />

      <section className="card">
        <h3>Trend</h3>
        <div className={`verdict ${trendColor}`}>{direction.toUpperCase()}</div>
        <div className="kv">
          <span>Slope / bar</span>
          <b>{trend?.slope_pct_per_bar ?? "—"}%</b>
        </div>
        <div className="kv">
          <span>Fit strength (R²)</span>
          <b>{trend?.r2 ?? "—"}</b>
        </div>
        <span className="dim small">Trend of the displayed chart window.</span>
      </section>

      <MultiTimeframe mtf={mtf} />

      <Minervini minervini={data.minervini} />

      <section className="card">
        <h3>Patterns ({patterns.length})</h3>
        {patterns.length === 0 && <p className="muted">None detected in this window.</p>}
        {patterns.map((p, i) => (
          <div
            key={i}
            className={`pattern clickable ${focusKey === `pat-${i}` ? "focused" : ""}`}
            onClick={() => focusSignal(`pat-${i}`, { times: p.points.map((pt) => pt.time), levels: [] })}
            title="Click to highlight on the chart"
          >
            <div className="pattern-head">
              <span
                className={`badge ${
                  p.bias === "bullish" ? "pos" : p.bias === "bearish" ? "neg" : "neutral"
                }`}
              >
                {p.bias}
              </span>
              <b>{p.name}</b>
            </div>
            <p className="muted small">{p.description}</p>
            <span className="small dim">
              {p.points[0].date} → {p.points[p.points.length - 1].date}
            </span>
          </div>
        ))}
      </section>

      <section className="card">
        <h3>Candlesticks ({candlesticks.length})</h3>
        {candlesticks.length === 0 && <p className="muted small">None in the recent window.</p>}
        {candlesticks.slice(0, 8).map((s, i) => (
          <div
            key={i}
            className={`signal-row clickable ${focusKey === `cdl-${i}` ? "focused" : ""}`}
            onClick={() => focusSignal(`cdl-${i}`, { times: [s.time], levels: [] })}
            title="Click to highlight on the chart"
          >
            <span className={`dot ${s.bias === "bullish" ? "pos" : s.bias === "bearish" ? "neg" : "neutral"}`} />
            <b className="signal-name">{s.name}</b>
            <span className="dim small">{s.date}</span>
          </div>
        ))}
      </section>

      <Backtest backtest={data.backtest} />

      <section className="card">
        <h3>Volume</h3>
        {vol.available ? (
          <>
            <div className="kv">
              <span>vs 50-day avg</span>
              <b className={vol.latest_ratio >= 1.5 ? "pos" : ""}>
                {vol.latest_ratio != null ? `${vol.latest_ratio}×` : "—"}
              </b>
            </div>
            <div className="kv">
              <span>OBV trend</span>
              <b className={vol.obv_trend === "rising" ? "pos" : vol.obv_trend === "falling" ? "neg" : ""}>
                {vol.obv_trend}
              </b>
            </div>
            {(vol.signals || []).slice(0, 4).map((s, i) => (
              <div
                key={i}
                className={`signal-row clickable ${focusKey === `vol-${i}` ? "focused" : ""}`}
                onClick={() => focusSignal(`vol-${i}`, { times: [s.time], levels: [] })}
                title="Click to highlight on the chart"
              >
                <span className={`dot ${s.bias === "bullish" ? "pos" : s.bias === "bearish" ? "neg" : "neutral"}`} />
                <b className="signal-name">{s.name}</b>
                <span className="dim small">{s.date}</span>
              </div>
            ))}
          </>
        ) : (
          <p className="muted small">No volume data for this instrument.</p>
        )}
      </section>

      <section className="card">
        <h3>Key levels</h3>
        <div className="levels">
          <div>
            <span className="dim small">Resistance</span>
            {resistance.length ? (
              resistance.map((r, i) => <div key={i} className="lvl neg">{r}</div>)
            ) : (
              <div className="lvl dim">—</div>
            )}
          </div>
          <div>
            <span className="dim small">Support</span>
            {support.length ? (
              support.map((s, i) => <div key={i} className="lvl pos">{s}</div>)
            ) : (
              <div className="lvl dim">—</div>
            )}
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Forecast</h3>
        {forecast?.available ? (
          <>
            <div className="kv">
              <span>{forecast.horizon}-bar target</span>
              <b className={fcUp ? "pos" : "neg"}>
                {fcLast?.value} ({fcUp ? "+" : ""}{fcChange?.toFixed(2)}%)
              </b>
            </div>
            <div className="kv">
              <span>Dir. accuracy</span>
              <b>{forecast.metrics?.directional_accuracy ?? "—"}</b>
            </div>
            <div className="kv">
              <span>vs. baseline</span>
              <b>{forecast.metrics?.baseline_accuracy ?? "—"}</b>
            </div>
            <div className="kv">
              <span>RMSE (log-ret)</span>
              <b>{forecast.metrics?.rmse_logret ?? "—"}</b>
            </div>
            {forecast.band && (
              <div className="kv">
                <span>Band</span>
                <b title="Scaled by blended OHLC volatility; multiplier adapts to this stock's tail fatness">
                  ±{forecast.band.multiplier}σ · {forecast.band.tail}
                </b>
              </div>
            )}
            <p className="muted small">{forecast.disclaimer}</p>
            <ForecastRecord ticker={data.ticker} horizon={forecast.horizon} />
          </>
        ) : (
          <p className="muted small">{forecast?.reason || "Unavailable."}</p>
        )}
      </section>

      {meta?.sector && <p className="dim small footnote">{meta.exchange} · {meta.sector}</p>}
    </aside>
  );
}
