"""Does the Buy-Zone Scanner's top-5 beat buy-and-hold? Point-in-time, honest.

At each sampled day we rank the universe by setup_score using ONLY past data,
take the top-5 (highest score) and bottom-5 (lowest positive), and measure their
forward 5-day and 21-day returns vs the equal-weight universe. If top-5 ≈
universe ≈ bottom-5, the screen has NO directional edge (the expected result).

Run:  ./venv/bin/python -u scanner_backtest.py
"""
import numpy as np
import pandas as pd

from services import data, indicators, scanner


def main():
    uni = scanner.universe()
    print(f"Scanner backtest — universe of {len(uni)} names, point-in-time\n", flush=True)

    spy = data.fetch_ohlcv("SPY", period="5y", interval="1d")
    spy_close = spy["close"]

    closes = {}
    for t in uni:
        try:
            d = data.fetch_ohlcv(t, period="5y", interval="1d")
            closes[t] = d["close"]
        except Exception:
            continue
    prices = pd.DataFrame(closes).dropna(how="all")
    print(f"  loaded {prices.shape[1]} names, {prices.shape[0]} days", flush=True)

    sma20 = prices.rolling(20).mean()
    sma200 = prices.rolling(200).mean()
    rsi = prices.apply(lambda c: indicators.rsi(c))
    spy_ret = (spy_close / spy_close.shift(126) - 1).reindex(prices.index)
    stock_ret = prices / prices.shift(126) - 1
    rs_excess = stock_ret.sub(spy_ret, axis=0) * 100

    gate = (prices > sma200) & (rs_excess > 0)
    rsi_score = ((55 - rsi) / 30).clip(0, 1)
    pullback = ((sma20 / prices - 1) / 0.05).clip(0, 1)
    score = (100 * (0.55 * rsi_score + 0.35 * pullback + 0.10)).where(gate, 0.0)

    fwd5 = prices.shift(-5) / prices - 1
    fwd21 = prices.shift(-21) / prices - 1

    rows = {"top5": {5: [], 21: []}, "bottom5": {5: [], 21: []}, "uni": {5: [], 21: []}}
    idx = prices.index
    for i in range(210, len(idx) - 21, 3):
        t = idx[i]
        s = score.loc[t].dropna()
        s = s[s > 0]
        if len(s) < 6:
            continue
        top = s.nlargest(5).index
        bot = s.nsmallest(5).index
        for h, fwd in ((5, fwd5), (21, fwd21)):
            f = fwd.loc[t]
            rows["top5"][h].append(float(f[top].mean()))
            rows["bottom5"][h].append(float(f[bot].mean()))
            rows["uni"][h].append(float(f.dropna().mean()))

    print(f"\n  {'group':9} {'5d avg':>9} {'5d win':>8} {'21d avg':>9} {'21d win':>8}")
    for g in ("top5", "bottom5", "uni"):
        a5 = np.array(rows[g][5]); a21 = np.array(rows[g][21])
        print(f"  {g:9} {a5.mean()*100:8.2f}% {np.mean(a5>0)*100:7.0f}% "
              f"{a21.mean()*100:8.2f}% {np.mean(a21>0)*100:7.0f}%")

    t5 = np.array(rows["top5"][21]); u = np.array(rows["uni"][21])
    edge = (t5.mean() - u.mean()) * 100
    # paired t-stat on the per-date difference
    diff = t5 - u
    tstat = diff.mean() / (diff.std(ddof=1) / np.sqrt(len(diff))) if len(diff) > 2 else 0
    print(f"\n  Top-5 vs universe (21d): edge {edge:+.2f}% per pick, paired t = {tstat:+.2f}")
    print("  Verdict:", "EDGE (t>2)" if abs(tstat) > 2 and edge > 0 else
          "NO meaningful edge — screen times entries, it does not pick winners.")


if __name__ == "__main__":
    main()
