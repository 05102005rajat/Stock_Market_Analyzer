import { useEffect, useRef } from "react";
import { createChart, LineStyle, ColorType } from "lightweight-charts";

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
  const chartRef = useRef(null);
  const candleRef = useRef(null);
  // Tracks overlays we added and which chart instance they belong to, so we can
  // remove them on toggle without touching a disposed chart on a data change.
  const overlaysRef = useRef({ chart: null, series: [], priceLines: [] });
  const focusRef = useRef({ chart: null, priceLines: [] });

  // --- Effect 1: chart + candles (rebuilt only when the dataset changes) ---
  useEffect(() => {
    if (!containerRef.current || !data) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0e1117" },
        textColor: "#c9d1d9",
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
        fontSize: 12,
      },
      grid: { vertLines: { color: "#161b26" }, horzLines: { color: "#161b26" } },
      rightPriceScale: {
        borderColor: "#30363d",
        scaleMargins: { top: 0.08, bottom: 0.12 },
        entireTextOnly: true,
      },
      timeScale: {
        borderColor: "#30363d",
        timeVisible: intraday,
        secondsVisible: false,
        rightOffset: 6,
        barSpacing: 8,
      },
      crosshair: {
        mode: 1, // magnet — snaps to candles like TradingView
        vertLine: { color: "#4f9eff88", width: 1, style: LineStyle.Dashed,
                    labelBackgroundColor: "#1f6feb" },
        horzLine: { color: "#4f9eff88", width: 1, style: LineStyle.Dashed,
                    labelBackgroundColor: "#1f6feb" },
      },
      watermark: {
        visible: true,
        text: data.ticker || "",
        fontSize: 56,
        color: "rgba(120,140,180,0.06)",
        horzAlign: "center",
        vertAlign: "center",
      },
      height: 460,
      autoSize: true,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderUpColor: "#26a69a",
      borderDownColor: "#ef5350",
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
      priceLineColor: "#4f9eff",
      priceLineStyle: LineStyle.Dotted,
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

    chartRef.current = chart;
    candleRef.current = candleSeries;
    chart.timeScale().fitContent();

    const onResize = () => chart.timeScale().fitContent();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
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
      addLine(ind.sma20, "#f0b90b", 1.5, LineStyle.Solid, "SMA20");
      addLine(ind.sma50, "#4f9eff", 1.5, LineStyle.Solid, "SMA50");
    }
    if (toggles.bollinger) {
      addLine(ind.bb_upper, "#8b949e", 1, LineStyle.Dashed);
      addLine(ind.bb_mid, "#8b949e", 1, LineStyle.Dotted);
      addLine(ind.bb_lower, "#8b949e", 1, LineStyle.Dashed);
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

  return <div className="chart" ref={containerRef} />;
}
