import { useEffect, useRef, useState } from "react";
import { createChart, LineStyle, ColorType } from "lightweight-charts";

// Fibonacci retracement levels (drawn between two clicked points).
const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const FIB_COLORS = ["#8b949e", "#26a69a", "#26a69a", "#ffb01f", "#ef5350", "#ef5350", "#8b949e"];

// Renders the candlestick chart plus every overlay the user has toggled on.
//
// Two effects, deliberately separated:
//   1. [data]          -> build the chart + candle series once per data load.
//   2. [data, toggles] -> add/remove overlay series on the existing chart,
//                         so toggling a chip never tears down the whole chart.
//
// All series share epoch-second `time` keys produced by the backend so they
// align on one time scale.
export default function PriceChart({ data, toggles, focus, intraday = false }) {
  const containerRef = useRef(null);
  const legendRef = useRef(null);
  const chartRef = useRef(null);
  const candleRef = useRef(null);
  const volumeRef = useRef(null);
  // Tracks overlays we added and which chart instance they belong to, so we can
  // remove them on toggle without touching a disposed chart on a data change.
  const overlaysRef = useRef({ chart: null, series: [], priceLines: [] });
  const focusRef = useRef({ chart: null, priceLines: [] });

  // --- Drawing tools state ---
  // tool: null | "horizontal" | "trend" | "fib". pendingRef holds the first
  // click of a two-click tool. drawings persist per-ticker in localStorage.
  const [tool, setTool] = useState(null);
  const toolRef = useRef(null);
  const pendingRef = useRef(null);
  const drawnRef = useRef({ chart: null, series: [], priceLines: [] });
  const drawingsRef = useRef([]);   // live mirror of `drawings` for click handlers
  const ticker = data?.ticker || "_";
  const storeKey = `drawings:${ticker}`;
  const [drawings, setDrawings] = useState([]);

  useEffect(() => {
    let loaded = [];
    try { loaded = JSON.parse(localStorage.getItem(`drawings:${ticker}`) || "[]"); } catch { loaded = []; }
    drawingsRef.current = loaded;
    setDrawings(loaded);
  }, [ticker]);

  useEffect(() => { toolRef.current = tool; }, [tool]);

  // Esc cancels an in-progress drawing and puts the tool away so you can pan/zoom.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") { pendingRef.current = null; setTool(null); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const persist = (next) => {
    drawingsRef.current = next;
    setDrawings(next);
    try { localStorage.setItem(storeKey, JSON.stringify(next)); } catch { /* ignore */ }
  };

  // --- Effect 1: chart + candles (rebuilt only when the dataset changes) ---
  useEffect(() => {
    if (!containerRef.current || !data) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0d1015" },
        textColor: "#b3bdc9",
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(70,80,95,0.10)" },
        horzLines: { color: "rgba(70,80,95,0.10)" },
      },
      rightPriceScale: {
        borderColor: "rgba(70,80,95,0.4)",
        scaleMargins: { top: 0.10, bottom: 0.28 }, // leave room for volume pane
        entireTextOnly: true,
      },
      timeScale: {
        borderColor: "rgba(70,80,95,0.4)",
        timeVisible: intraday,
        secondsVisible: false,
        rightOffset: 8,
        barSpacing: 11,
        minBarSpacing: 4,
      },
      crosshair: {
        mode: 1, // magnet — snaps to candles like TradingView
        vertLine: { color: "rgba(120,160,230,0.5)", width: 1, style: LineStyle.Solid,
                    labelBackgroundColor: "#1f6feb" },
        horzLine: { color: "rgba(120,160,230,0.5)", width: 1, style: LineStyle.Solid,
                    labelBackgroundColor: "#1f6feb" },
      },
      watermark: {
        visible: true,
        text: data.ticker || "",
        fontSize: 64,
        fontFamily: "'Inter', sans-serif",
        color: "rgba(120,140,180,0.05)",
        horzAlign: "center",
        vertAlign: "center",
      },
      height: 480,
      autoSize: true,
    });

    // Crisper candles: thin clean borders, brighter wicks, TradingView-like greens/reds.
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#0bce8b",
      downColor: "#f6465d",
      borderUpColor: "#0bce8b",
      borderDownColor: "#f6465d",
      wickUpColor: "#5fd6ad",
      wickDownColor: "#ff7a8a",
      priceLineColor: "rgba(120,160,230,0.6)",
      priceLineStyle: LineStyle.Dotted,
      priceLineWidth: 1,
    });
    candleSeries.setData(
      data.candles.map((c) => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }))
    );

    // Volume histogram in its own bottom pane, colored by up/down day.
    const volumeSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      color: "#3a4250",
    });
    chart.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.80, bottom: 0 },
    });
    if (data.candles.some((c) => c.volume != null)) {
      volumeSeries.setData(
        data.candles.map((c) => ({
          time: c.time,
          value: c.volume || 0,
          color: c.close >= c.open ? "rgba(11,206,139,0.45)" : "rgba(246,70,93,0.45)",
        }))
      );
    }

    chartRef.current = chart;
    candleRef.current = candleSeries;
    volumeRef.current = volumeSeries;
    chart.timeScale().fitContent();

    // Live OHLC legend that updates as the crosshair moves (the readout Legend shows).
    const legendEl = legendRef.current;
    const fmt = (v) => (v == null ? "—" : v.toFixed(2));
    const renderLegend = (c) => {
      if (!legendEl || !c) return;
      const up = c.close >= c.open;
      const arrow = up ? "▲" : "▼";
      const cls = up ? "up" : "down";
      legendEl.innerHTML =
        `<span class="leg-tkr">${data.ticker}</span>` +
        `<span class="leg-ohlc">O<b>${fmt(c.open)}</b> H<b>${fmt(c.high)}</b> ` +
        `L<b>${fmt(c.low)}</b> C<b class="${cls}">${fmt(c.close)}</b> ` +
        `<span class="${cls}">${arrow}</span></span>`;
    };
    const lastBar = data.candles[data.candles.length - 1];
    renderLegend(lastBar);
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.seriesData) {
        renderLegend(lastBar);
        return;
      }
      const bar = param.seriesData.get(candleSeries);
      renderLegend(bar || lastBar);
    });

    const onResize = () => chart.timeScale().fitContent();
    window.addEventListener("resize", onResize);

    // --- Drawing: capture clicks, map to (time, price), build drawings ---
    // Append a finished drawing and keep the tool active (sticky) so you can
    // place several in a row without re-picking the tool each time. Esc finishes.
    const commit = (drawing) => {
      const next = [...drawingsRef.current, drawing];
      drawingsRef.current = next;
      setDrawings(next);
      try { localStorage.setItem(`drawings:${data.ticker}`, JSON.stringify(next)); } catch { /* ignore */ }
    };

    const onClick = (param) => {
      const activeTool = toolRef.current;
      if (!activeTool || !param.point || param.time == null) return;
      const price = candleSeries.coordinateToPrice(param.point.y);
      if (price == null) return;
      const pt = { time: param.time, price: Number(price.toFixed(4)) };

      if (activeTool === "horizontal") {
        commit({ type: "horizontal", price: pt.price });   // one click; tool stays active
        return;
      }
      // Two-click tools (trend, fib): first click stores the anchor.
      if (!pendingRef.current) {
        pendingRef.current = pt;
        return;
      }
      const a = pendingRef.current;
      pendingRef.current = null;
      commit(activeTool === "trend" ? { type: "trend", a, b: pt } : { type: "fib", a, b: pt });
    };
    chart.subscribeClick(onClick);

    return () => {
      window.removeEventListener("resize", onResize);
      chart.unsubscribeClick(onClick);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
    };
  }, [data, intraday]);

  // --- Effect 2: overlays (run after effect 1; reuse the existing chart) ---
  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle || !data) return;

    // Clear overlays we previously added to *this* chart instance. On a data
    // change the chart was just rebuilt, so the old overlays are already gone
    // with it — skip removal to avoid touching a disposed chart.
    const prev = overlaysRef.current;
    if (prev.chart === chart) {
      prev.series.forEach((s) => chart.removeSeries(s));
      prev.priceLines.forEach((pl) => candle.removePriceLine(pl));
    }
    const added = { chart, series: [], priceLines: [] };
    overlaysRef.current = added;

    const addLine = (points, color, width = 2, style = LineStyle.Solid, title) => {
      if (!points || points.length === 0) return;
      const s = chart.addLineSeries({
        color,
        lineWidth: width,
        lineStyle: style,
        priceLineVisible: false,
        lastValueVisible: !!title,
        title: title || "",
        crosshairMarkerVisible: false,
      });
      s.setData(points.map((p) => ({ time: p.time, value: p.value })));
      added.series.push(s);
      return s;
    };

    const ind = data.indicators;

    if (toggles.ma) {
      addLine(ind.sma20, "#ffb01f", 1.5, LineStyle.Solid, "SMA20");
      addLine(ind.sma50, "#3b9dff", 1.5, LineStyle.Solid, "SMA50");
    }
    if (toggles.bollinger) {
      addLine(ind.bb_upper, "#9aa4b2", 1, LineStyle.Dashed);
      addLine(ind.bb_mid, "#9aa4b2", 1, LineStyle.Dotted);
      addLine(ind.bb_lower, "#9aa4b2", 1, LineStyle.Dashed);
    }

    // Guard: a 1-bar history yields start===end (equal times), which crashes
    // lightweight-charts setData (requires strictly ascending unique times).
    if (toggles.trend && data.trend?.start && data.trend?.end && data.trend.start.time < data.trend.end.time) {
      const t = data.trend;
      const color =
        t.direction === "uptrend" ? "#26a69a" : t.direction === "downtrend" ? "#ef5350" : "#8b949e";
      addLine([t.start, t.end], color, 2, LineStyle.LargeDashed, "Trend");
    }

    if (toggles.levels && data.levels) {
      data.levels.support.forEach((price) =>
        added.priceLines.push(
          candle.createPriceLine({
            price,
            color: "#26a69a",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "S",
          })
        )
      );
      data.levels.resistance.forEach((price) =>
        added.priceLines.push(
          candle.createPriceLine({
            price,
            color: "#ef5350",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: "R",
          })
        )
      );
    }

    if (toggles.forecast && data.forecast?.available && data.forecast.points.length) {
      const lastCandle = data.candles[data.candles.length - 1];
      const anchor = { time: lastCandle.time, value: lastCandle.close };
      // Guard: lightweight-charts requires strictly ascending, unique times.
      // Keep only forecast points strictly after the anchor bar.
      const fc = data.forecast.points.filter((p) => p.time > anchor.time);
      if (fc.length) {
        addLine([anchor, ...fc.map((p) => ({ time: p.time, value: p.upper }))], "#7d5fff55", 1, LineStyle.Dotted);
        addLine([anchor, ...fc.map((p) => ({ time: p.time, value: p.lower }))], "#7d5fff55", 1, LineStyle.Dotted);
        addLine([anchor, ...fc.map((p) => ({ time: p.time, value: p.value }))], "#7d5fff", 2, LineStyle.Solid, "Forecast");
      }
    }

    // Markers: chart patterns (arrows) and candlesticks (circles) share one
    // marker set on the candle series, so we merge both sources here.
    // setMarkers allows duplicate times but requires ascending order → sort.
    const biasColor = (b) => (b === "bullish" ? "#26a69a" : b === "bearish" ? "#ef5350" : "#8b949e");
    let markers = [];

    if (toggles.patterns && data.patterns?.length) {
      markers = markers.concat(
        data.patterns.map((p) => {
          const last = p.points[p.points.length - 1];
          const bullish = p.bias === "bullish";
          return {
            time: last.time,
            position: bullish ? "belowBar" : "aboveBar",
            color: biasColor(p.bias),
            shape: bullish ? "arrowUp" : "arrowDown",
            text: p.name,
          };
        })
      );
    }

    if (toggles.candles && data.candlesticks?.length) {
      // Cap to the 8 most recent so labels don't overwhelm the chart.
      markers = markers.concat(
        data.candlesticks.slice(0, 8).map((s) => ({
          time: s.time,
          position: s.bias === "bullish" ? "belowBar" : "aboveBar",
          color: biasColor(s.bias),
          shape: "circle",
          text: s.name,
        }))
      );
    }

    markers.sort((a, b) => a.time - b.time);
    candle.setMarkers(markers);
  }, [data, toggles]);

  // --- Effect 2.5: render user drawings (horizontals, trendlines, fib) ---
  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle || !data) return;

    // Clear previously-rendered drawings from this chart instance.
    const prev = drawnRef.current;
    if (prev.chart === chart) {
      prev.series.forEach((s) => chart.removeSeries(s));
      prev.priceLines.forEach((pl) => candle.removePriceLine(pl));
    }
    const added = { chart, series: [], priceLines: [] };
    drawnRef.current = added;

    const candleTimes = data.candles.map((c) => c.time);
    const firstT = candleTimes[0];
    const lastT = candleTimes[candleTimes.length - 1];

    const lineSeries = (pts, color, width, style) => {
      const s = chart.addLineSeries({
        color, lineWidth: width, lineStyle: style ?? LineStyle.Solid,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      });
      s.setData(pts);
      added.series.push(s);
      return s;
    };

    drawings.forEach((d) => {
      // A malformed drawing must never blank the whole chart — isolate each.
      try {
        if (d.type === "horizontal") {
          added.priceLines.push(
            candle.createPriceLine({
              price: d.price, color: "#e0b341", lineWidth: 1,
              lineStyle: LineStyle.Solid, axisLabelVisible: true,
              title: `${d.price}`,
            })
          );
        } else if (d.type === "trend") {
          const [p, q] = d.a.time <= d.b.time ? [d.a, d.b] : [d.b, d.a];
          if (p.time < q.time) {
            lineSeries(
              [{ time: p.time, value: p.price }, { time: q.time, value: q.price }],
              "#4f9eff", 2, LineStyle.Solid
            );
          }
        } else if (d.type === "fib") {
          // Horizontal fib levels between the two clicked prices, spanning the
          // time range from the earlier click to the latest bar.
          const hi = Math.max(d.a.price, d.b.price);
          const lo = Math.min(d.a.price, d.b.price);
          const t0 = Math.min(d.a.time, d.b.time);
          FIB_LEVELS.forEach((lvl, i) => {
            const price = Number((hi - (hi - lo) * lvl).toFixed(4));
            lineSeries(
              [{ time: Math.max(t0, firstT), value: price }, { time: lastT, value: price }],
              FIB_COLORS[i], 1, LineStyle.Dashed
            );
            added.priceLines.push(
              candle.createPriceLine({
                price, color: FIB_COLORS[i], lineWidth: 1, lineStyle: LineStyle.Dotted,
                axisLabelVisible: true, title: `${(lvl * 100).toFixed(1)}%`,
              })
            );
          });
        }
      } catch { /* skip this drawing, keep the rest of the chart alive */ }
    });
  }, [drawings, data]);

  // --- Effect 2.7: live rubber-band preview while a tool is active ---
  // ONE reusable series + ONE reusable price line, updated as the cursor moves.
  // CRITICAL: the crosshair handler only records the desired state; the actual
  // series mutation is flushed on the next animation frame. Calling setData
  // synchronously inside subscribeCrosshairMove re-enters the chart's own redraw
  // and crashes it (blank screen) — rAF decouples it and also throttles to 60fps.
  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle || !data || !tool) return;

    const pv = chart.addLineSeries({
      color: tool === "fib" ? "#9aa4b2" : "#4f9eff",
      lineWidth: 1, lineStyle: LineStyle.Dashed,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => null,   // preview must never rescale the price axis
    });
    pv.setData([]);
    let pvLine = null;
    let raf = 0;
    let pending = null;   // latest desired preview, applied on the next frame
    const dropLine = () => { if (pvLine) { try { candle.removePriceLine(pvLine); } catch { /* gone */ } pvLine = null; } };

    const candleTimes = data.candles.map((c) => c.time);
    const firstT = candleTimes[0];
    const lastT = candleTimes[candleTimes.length - 1];

    const flush = () => {
      raf = 0;
      const p = pending;
      try {
        if (!p) { pv.setData([]); dropLine(); return; }
        if (p.kind === "h") {
          if (!pvLine) pvLine = candle.createPriceLine({
            price: p.price, color: "#e0b341", lineWidth: 1, lineStyle: LineStyle.Dashed,
            axisLabelVisible: true, title: "",
          });
          else pvLine.applyOptions({ price: p.price });
        } else {
          pv.setData(p.pts);
        }
      } catch { /* transient chart state during rebuild — ignore */ }
    };
    const schedule = (next) => { pending = next; if (!raf) raf = requestAnimationFrame(flush); };

    const onMove = (param) => {
      // Only bail when the cursor leaves the chart entirely. In the blank area
      // to the right/left of the candles param.time is undefined but param.point
      // still exists — we clamp the time below instead of clearing the preview.
      if (!param.point) { schedule(null); return; }
      const price = candle.coordinateToPrice(param.point.y);
      if (price == null) return;
      const py = Number(price.toFixed(4));

      if (tool === "horizontal") { schedule({ kind: "h", price: py }); return; }

      const a = pendingRef.current;          // no anchor yet → nothing to preview
      if (!a) { schedule({ kind: "l", pts: [] }); return; }

      // Resolve the cursor's time. Over the right/left whitespace param.time is
      // undefined, so clamp to the last/first bar so the line tracks the cursor's
      // height at the chart edge rather than vanishing.
      let t = param.time;
      if (t == null) {
        const lastX = chart.timeScale().timeToCoordinate(lastT);
        t = (lastX != null && param.point.x >= lastX) ? lastT : firstT;
      }
      if (t === a.time) { schedule({ kind: "l", pts: [] }); return; }

      if (tool === "fib") {
        const lo = Math.min(a.time, t), hi = Math.max(a.time, t);
        schedule({ kind: "l", pts: [{ time: lo, value: py }, { time: hi, value: py }] });
        return;
      }
      // trend: rubber-band line from the anchor to the cursor (times ascending).
      schedule({ kind: "l", pts: a.time < t
        ? [{ time: a.time, value: a.price }, { time: t, value: py }]
        : [{ time: t, value: py }, { time: a.time, value: a.price }] });
    };

    chart.subscribeCrosshairMove(onMove);
    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      if (raf) cancelAnimationFrame(raf);
      try { chart.removeSeries(pv); } catch { /* chart already disposed */ }
      dropLine();
    };
  }, [tool, data]);

  // --- Effect 3: focus highlight (the "why" drill-down) ---
  // Draws bright price lines for the levels/bars a clicked signal is based on
  // and zooms the chart to that region. Kept separate from overlays/markers so
  // it never clobbers them.
  useEffect(() => {
    const chart = chartRef.current;
    const candle = candleRef.current;
    if (!chart || !candle || !data) return;

    const prev = focusRef.current;
    if (prev.chart === chart) {
      prev.priceLines.forEach((pl) => candle.removePriceLine(pl));
    }
    const added = { chart, priceLines: [] };
    focusRef.current = added;
    if (!focus) return;

    const addPriceLine = (price, dashed) =>
      added.priceLines.push(
        candle.createPriceLine({
          price,
          color: "#ffd479",
          lineWidth: 2,
          lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
          axisLabelVisible: true,
          title: "◎",
        })
      );

    (focus.levels || []).forEach((p) => addPriceLine(p, false));

    // For each anchored bar, mark its close with a dashed line, then zoom in.
    const times = focus.times || [];
    times.forEach((t) => {
      const c = data.candles.find((x) => x.time === t);
      if (c) addPriceLine(c.close, true);
    });

    if (times.length) {
      const candleTimes = data.candles.map((c) => c.time);
      const minT = Math.min(...times);
      const maxT = Math.max(...times);
      const before = candleTimes.filter((t) => t <= minT);
      const after = candleTimes.filter((t) => t >= maxT);
      const from = before[Math.max(0, before.length - 25)] ?? candleTimes[0];
      const to = after[Math.min(after.length - 1, 25)] ?? candleTimes[candleTimes.length - 1];
      try {
        chart.timeScale().setVisibleRange({ from, to });
      } catch {
        /* range out of bounds — ignore */
      }
    }
  }, [focus, data]);

  const undo = () => persist(drawings.slice(0, -1));
  const clearAll = () => { persist([]); setTool(null); pendingRef.current = null; };
  const pick = (t) => {
    pendingRef.current = null;
    setTool((cur) => (cur === t ? null : t));
  };

  return (
    <div className="chart-wrap">
      <div className="draw-toolbar">
        <span className="draw-label">✏️ Draw:</span>
        <button className={`draw-btn ${tool === "horizontal" ? "on" : ""}`} onClick={() => pick("horizontal")} title="Click once to drop a horizontal price line">─ Line</button>
        <button className={`draw-btn ${tool === "trend" ? "on" : ""}`} onClick={() => pick("trend")} title="Click two points to draw a trendline">╱ Trend</button>
        <button className={`draw-btn ${tool === "fib" ? "on" : ""}`} onClick={() => pick("fib")} title="Click a high then a low to draw Fibonacci levels">≡ Fib</button>
        <span className="draw-divider" />
        <button className="draw-btn" onClick={undo} disabled={!drawings.length} title="Undo last drawing">↶ Undo</button>
        <button className="draw-btn" onClick={clearAll} disabled={!drawings.length} title="Remove all drawings">🗑 Clear</button>
        {tool && (
          <span className="draw-hint">
            {tool === "horizontal" ? "Click to drop lines — keep going · Esc to finish" :
             tool === "trend" ? "Click two points per line · Esc to finish" :
             "Click a high, then a low · Esc to finish"}
          </span>
        )}
      </div>
      <div className="chart-area">
        <div className="chart-legend" ref={legendRef} />
        <div className={`chart ${tool ? "drawing" : ""}`} ref={containerRef} />
      </div>
    </div>
  );
}
