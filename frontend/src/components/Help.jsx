// Plain-English help for a brand-new investor. Every term the app shows, in
// words anyone can understand, with simple analogies and the honest caveats.

const SECTIONS = [
  {
    title: "Read this first (30 seconds)",
    items: [
      ["The one big truth", "Nobody — not this app, not a pro — can reliably predict whether a stock goes UP or DOWN next week. We tested it on real May data: guessing direction was a coin flip (50%). So this app does NOT pick winners. What it CAN do is measure two real things: the price RANGE a stock will probably stay in, and the RISK in your portfolio. Use it for that."],
      ["So what is it good for?", "Three honest things: (1) showing your true exposure (you own way more of a few companies than you think), (2) giving sensible sell targets and stop-losses, and (3) timing entries when a stock you like is on a dip. Not fortune-telling."],
    ],
  },
  {
    title: "Your money words",
    items: [
      ["Shares", "A slice of a company you own. 1.04 shares of Apple = a little more than one Apple slice."],
      ["Cost basis / Avg cost", "The average price you PAID for your shares. If it's $310 and the stock is now $325, you're up."],
      ["Value", "What your shares are worth right now (shares × current price)."],
      ["Gain / Loss (P/L)", "Profit or loss vs what you paid. Green = up, red = down."],
      ["Cash", "Money in the account not yet invested in any stock."],
    ],
  },
  {
    title: "Is it going up or down? (trend words)",
    items: [
      ["Uptrend / Downtrend", "Whether the price has generally been climbing or falling over recent months. An uptrend is like walking up a hill — bumpy, but higher over time."],
      ["Moving average (50-day / 200-day)", "The average price over the last 50 or 200 days, drawn as a smooth line. It hides the daily noise so you can see the real direction. Price above the 200-day line = healthy long-term uptrend."],
      ["Golden cross / Death cross", "When the FAST average (50-day) crosses ABOVE the SLOW one (200-day), it's a 'golden cross' — a long-term bullish mood. Crossing BELOW is a 'death cross' — bearish. Think of it as the trend's weather changing."],
      ["Support / Resistance", "Support is a FLOOR the price keeps bouncing UP off of. Resistance is a CEILING it keeps bumping its head on. Useful for guessing where it might pause."],
    ],
  },
  {
    title: "The app's summary words",
    items: [
      ["Posture (bullish / neutral / bearish)", "A one-word summary of all the signals combined: is the stock's setup leaning UP, DOWN, or flat RIGHT NOW. IMPORTANT: it describes the present situation — it is NOT a prediction it will rise. (We proved that doesn't work.)"],
      ["Confidence / Agreement", "How much the different signals AGREE with each other — high means they're all pointing the same way. It is NOT 'how likely it is to go up.'"],
      ["RSI", "A speedometer from 0 to 100 for how fast the price has moved. Above 70 = 'overbought' (sprinted up fast, may need a rest). Below 30 = 'oversold' (beaten down, may bounce). Around 50 = normal."],
      ["Relative strength (vs SPY)", "Is this stock BEATING the overall US market (the S&P 500, 'SPY') or LAGGING it? Leaders beat the market; laggards don't."],
      ["Minervini Trend Template (Stage 2)", "A famous 8-point checklist by trader Mark Minervini for a strong, healthy uptrend (price above its averages, beating the market, etc.). 'Stage 2' is the advancing stage. Passing all 8 = a textbook market leader. (Still not a promise it keeps rising.)"],
      ["Volatility / Vol regime", "How much a stock normally jumps around. 'Calm' = small daily moves, 'stormy/elevated' = big swings. Bigger swings = more risk AND bigger possible targets."],
    ],
  },
  {
    title: "Patterns & volume",
    items: [
      ["Candlestick patterns", "Shapes made by one or a few days of price bars that traders watch — like 'Hammer', 'Engulfing', 'Doji'. Each candle shows the open, high, low, and close for a day."],
      ["Chart patterns", "Bigger shapes that form over weeks — 'Double Top', 'Triangle', 'Head & Shoulders'. Some people trade them."],
      ["Pattern edge (backtest)", "We checked history: after this pattern appeared, did the price actually tend to go the way the pattern suggests? Mostly the honest answer is 'no reliable edge' — and we SHOW you that instead of hiding it. A pattern looking pretty doesn't mean it works."],
      ["Volume", "How many shares traded that day. A big spike = lots of attention/conviction. A 'dry-up' = quiet, fewer people trading. Volume confirms or questions a move."],
    ],
  },
  {
    title: "Buying & selling words",
    items: [
      ["Sell target (take-profit) 🎯", "A realistic price to sell for a profit. It's set so that, historically, the price reached it about 2 of 3 times within the period you pick (week or month). It's odds — NOT a guarantee. About 1 in 3 times it didn't get there."],
      ["Stop / cut-loss 🛡️", "A price where you'd sell to LIMIT losses if the stock drops. Pair every target with a stop so a small dip can't become a big one."],
      ["Buy zone", "A price range to buy on a dip — usually a bit below today's price, where the stock has pulled back within an uptrend."],
      ["Forecast band / range / cone", "The shaded area on the chart = where the price will PROBABLY stay (it was right ~94% in our May test). The middle line is basically a guess and is NOT reliable — trust the SHADE, not the line."],
    ],
  },
  {
    title: "Portfolio words",
    items: [
      ["Look-through exposure", "Your REAL bet on a company once your ETFs (like VOO) are unpacked into the stocks they hold. Example: you might think you own a little Apple, but VOO holds a lot of Apple too — so your true Apple bet is much bigger."],
      ["Concentration", "How much of your money is riding on just a few names. Lots of holdings can still be ONE big bet if they overlap."],
      ["Diversification", "Spreading money across DIFFERENT things that don't all move together, to lower risk. Owning 5 tech stocks isn't diversified — they move as one."],
    ],
  },
];

export default function Help() {
  return (
    <div className="portfolio help">
      <section className="card">
        <h2 style={{ marginTop: 0 }}>Help — what everything means (in plain English)</h2>
        <p className="muted small">New to investing? Start at the top. Nothing here is advice — it's just explaining the words you see in the app.</p>
      </section>
      {SECTIONS.map((s) => (
        <section key={s.title} className="card">
          <h3>{s.title}</h3>
          <dl className="glossary">
            {s.items.map(([term, def]) => (
              <div key={term}><dt>{term}</dt><dd>{def}</dd></div>
            ))}
          </dl>
        </section>
      ))}
      <p className="muted small">If a word in the app isn't here, tell me and I'll add it.</p>
    </div>
  );
}
