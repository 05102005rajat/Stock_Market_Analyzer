// "Right now" — what the recent candles are doing, in plain English. This is
// the "current candle trend" most people actually want, without jargon. If a
// candlestick shape just formed, we name it AND say what it looks like.

// What each candlestick shape LOOKS like (so the name means something).
const SHAPES = {
  "Doji": "a tiny body with wicks both ways — buyers and sellers tied (indecision).",
  "Bullish Marubozu": "a big green candle with almost no wicks — buyers in full control all day.",
  "Bearish Marubozu": "a big red candle with almost no wicks — sellers in full control all day.",
  "Hammer": "a small body up top with a long lower wick — sellers pushed it down, buyers slammed it back up.",
  "Inverted Hammer": "a small body at the bottom with a long upper wick — a probe higher after a drop.",
  "Hanging Man": "a small body up top with a long lower wick, after a run-up — a possible warning.",
  "Shooting Star": "a small body at the bottom with a long upper wick — buyers got rejected at the highs.",
  "Bullish Engulfing": "a big green candle that completely swallows the prior red one — buyers took over.",
  "Bearish Engulfing": "a big red candle that swallows the prior green one — sellers took over.",
  "Bullish Harami": "a small green candle tucked inside the prior big red one — selling may be stalling.",
  "Bearish Harami": "a small red candle inside the prior big green one — buying may be stalling.",
  "Piercing Line": "a red day then a green day that closes back above the middle — a bullish push back.",
  "Dark Cloud Cover": "a green day then a red day that closes below the middle — a bearish push back.",
  "Morning Star": "down, tiny pause, then up — a 3-day bottoming shape.",
  "Evening Star": "up, tiny pause, then down — a 3-day topping shape.",
  "Three White Soldiers": "three strong green days in a row — steady buying.",
  "Three Black Crows": "three strong red days in a row — steady selling.",
};

export default function RecentAction({ data }) {
  if (!data?.candles?.length) return null;
  const c = data.candles;
  const n = c.length;
  const last = c[n - 1];
  const ref5 = c[Math.max(0, n - 6)];
  const chg5 = ((last.close / ref5.close - 1) * 100);
  const up = last.close >= last.open;

  const move =
    chg5 > 4 ? "a strong push higher" :
    chg5 > 1 ? "drifting up" :
    chg5 < -4 ? "a sharp drop" :
    chg5 < -1 ? "drifting down" : "roughly flat (going sideways)";

  // Most recent candlestick shape, if it's within the last ~3 days.
  const recent = (data.candlesticks || []).find(
    (s) => s.time >= c[Math.max(0, n - 3)].time
  );

  return (
    <section className="card recent">
      <h3>Right now</h3>
      <p className="recent-line">
        Over the last 5 days it's been <b>{move}</b> ({chg5 >= 0 ? "+" : ""}{chg5.toFixed(1)}%).
        The latest day closed <b className={up ? "pos" : "neg"}>{up ? "up (green ▲)" : "down (red ▼)"}</b>.
      </p>
      {recent ? (
        <p className="recent-line small">
          A <b>{recent.name}</b> shape just formed — {SHAPES[recent.name] || recent.description}{" "}
          <span className="dim">(traders read it as {recent.bias}, but candles don't reliably predict — treat it as a hint, not a signal.)</span>
        </p>
      ) : (
        <p className="muted small">No notable candle shape in the last few days — just normal day-to-day movement.</p>
      )}
    </section>
  );
}
