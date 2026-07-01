import { useEffect, useRef } from "react";
import { createChart, LineStyle, ColorType } from "lightweight-charts";

const baseOptions = {
  layout: {
    background: { type: ColorType.Solid, color: "#0e1117" },
    textColor: "#8b949e",
    fontFamily: "system-ui, sans-serif",
  },
  grid: { vertLines: { color: "#1c2333" }, horzLines: { color: "#1c2333" } },
  rightPriceScale: { borderColor: "#30363d" },
  timeScale: { borderColor: "#30363d", timeVisible: false },
  height: 150,
  autoSize: true,
};

// Two stacked oscillator charts: RSI (with 30/70 guides) and MACD.
export default function IndicatorPanel({ data }) {
  const rsiRef = useRef(null);
  const macdRef = useRef(null);

  useEffect(() => {
    if (!data) return;
    const charts = [];

    // --- RSI ---
    if (rsiRef.current) {
      const chart = createChart(rsiRef.current, baseOptions);
      charts.push(chart);
      const s = chart.addLineSeries({ color: "#f0b90b", lineWidth: 2, priceLineVisible: false });
      s.setData(data.indicators.rsi);
      [30, 50, 70].forEach((lvl) =>
        s.createPriceLine({
          price: lvl,
          color: lvl === 50 ? "#30363d" : "#8b949e",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
          axisLabelVisible: true,
          title: String(lvl),
        })
      );
      chart.timeScale().fitContent();
    }

    // --- MACD ---
    if (macdRef.current) {
      const chart = createChart(macdRef.current, baseOptions);
      charts.push(chart);
      const hist = chart.addHistogramSeries({ priceLineVisible: false });
      hist.setData(
        data.indicators.macd_hist.map((p) => ({
          time: p.time,
          value: p.value,
          color: p.value >= 0 ? "#26a69a88" : "#ef535088",
        }))
      );
      const macdLine = chart.addLineSeries({ color: "#4f9eff", lineWidth: 2, priceLineVisible: false });
      macdLine.setData(data.indicators.macd);
      const signalLine = chart.addLineSeries({ color: "#f0b90b", lineWidth: 1.5, priceLineVisible: false });
      signalLine.setData(data.indicators.macd_signal);
      chart.timeScale().fitContent();
    }

    return () => charts.forEach((c) => c.remove());
  }, [data]);

  return (
    <div className="oscillators">
      <div className="osc-block">
        <span className="osc-label">RSI (14)</span>
        <div className="osc-chart" ref={rsiRef} />
      </div>
      <div className="osc-block">
        <span className="osc-label">MACD (12, 26, 9)</span>
        <div className="osc-chart" ref={macdRef} />
      </div>
    </div>
  );
}
