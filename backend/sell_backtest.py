"""Do 'sell signals' actually predict DOWN moves? Point-in-time, honest.

We test the classic exit/sell triggers — overbought RSI, very extended above the
50-day average, and trend-broken (below the 200-day) — and ask: when the signal
fires, is the FORWARD return lower (or negative) than just holding? Sampled
NON-OVERLAPPING so the significance is honest.

If forward returns after a 'sell signal' ≈ the universe average, the signal does
NOT predict drops — it can only be used as profit-taking / risk discipline.

Run:  ./venv/bin/python -u sell_backtest.py
"""
import numpy as np
import pandas as pd

from services import data

BASKET = ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "CVX", "XOM",
          "WMT", "COST", "JPM", "V", "HD", "PG", "JNJ", "UNH", "AMD", "AVGO"]


def _rsi(c, p=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def main():
    print("Do sell signals predict DOWN moves? (forward returns after the signal)\n", flush=True)
    px = pd.DataFrame({t: data.fetch_ohlcv(t, "5y", "1d")["close"] for t in BASKET}).dropna(how="all")
    sma20 = px.rolling(20).mean()
    sma50 = px.rolling(50).mean()
    sma200 = px.rolling(200).mean()
    rsi = px.apply(_rsi)

    sigs = {
        "overbought RSI>70": rsi > 70,
        "very extended (>10% over 50DMA)": px > 1.10 * sma50,
        "trend broken (below 200DMA)": px < sma200,
    }

    for H, hl in ((5, "1-week"), (21, "1-month")):
        fwd = px.shift(-H) / px - 1
        sub = px.index[list(range(210, len(px) - H, H))]   # non-overlapping in time
        fwd_sub = fwd.loc[sub]
        base = fwd_sub.stack().dropna()
        print(f"  {hl} forward return:  (universe avg = {base.mean()*100:+.2f}%, "
              f"down-rate = {(base < 0).mean()*100:.0f}%)")
        for name, mask in sigs.items():
            msub = mask.loc[sub]
            sel = fwd_sub.where(msub).stack().dropna()
            if len(sel) < 20:
                print(f"    {name:34} n<20")
                continue
            # per-date diff vs the non-selected names, t-tested across dates
            diffs = []
            for dt in sub:
                sd = fwd_sub.loc[dt].where(msub.loc[dt]).dropna()
                rd = fwd_sub.loc[dt].where(~msub.loc[dt]).dropna()
                if len(sd) and len(rd):
                    diffs.append(sd.mean() - rd.mean())
            diffs = np.array(diffs)
            t = diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs))) if len(diffs) > 2 else float("nan")
            down = (sel < 0).mean()
            verdict = "predicts DOWN" if (sel.mean() < 0 and t < -2) else "no edge"
            print(f"    {name:34} n={len(sel):4d}  avg {sel.mean()*100:+6.2f}%  "
                  f"down {down*100:3.0f}%  vs rest {diffs.mean()*100:+5.2f}% (t={t:+.1f})  -> {verdict}")
        print()


if __name__ == "__main__":
    main()
