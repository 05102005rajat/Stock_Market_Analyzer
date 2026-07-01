"""Per-stock × per-strategy success — and why a high number is usually a mirage.

For each stock we score several timing strategies by 'success' = % of 1-month
forward windows that were profitable when the strategy said 'in'. We then do the
HONEST test: find each stock's BEST strategy on the FIRST 60% of history
(in-sample), and check that SAME strategy on the LAST 40% (out-of-sample). If the
80%-ers were skill, they'd persist. If they were luck/drift, they collapse toward
the stock's plain buy-and-hold base rate.

Run:  ./venv/bin/python -u per_stock_test.py
"""
import numpy as np
import pandas as pd

from services import data

STOCKS = ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "CVX", "WMT",
          "COST", "JPM", "AMD", "AVGO", "NFLX", "TSLA"]
H = 21  # 1-month forward


def _rsi(c, p=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/p, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/p, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def signals(px):
    sma50 = px.rolling(50).mean()
    sma200 = px.rolling(200).mean()
    rsi = _rsi(px)
    hi20 = px.rolling(20).max()
    return {
        "above 200-DMA": px > sma200,
        "golden cross": sma50 > sma200,
        "RSI < 35 (dip)": rsi < 35,
        "RSI > 55 (mom)": rsi > 55,
        "20-day breakout": px >= hi20,
        "buy & hold": pd.Series(True, index=px.index),
    }


def main():
    print(f"Per-stock strategy success (1-month forward win-rate)\n", flush=True)
    print(f"  {'stock':6} {'best strat (in-sample)':22} {'IS win':>7} {'OOS win':>8} {'buy&hold OOS':>13}")
    is_best, oos_of_best, bh_oos_all = [], [], []
    for t in STOCKS:
        try:
            px = data.fetch_ohlcv(t, period="5y", interval="1d")["close"]
        except Exception:
            continue
        fwd = px.shift(-H) / px - 1
        win = (fwd > 0)
        sig = signals(px)
        n = len(px)
        split = int(n * 0.6)
        is_mask = np.zeros(n, bool); is_mask[210:split] = True
        oos_mask = np.zeros(n, bool); oos_mask[split:n - H] = True
        isr = pd.Series(is_mask, index=px.index)
        oosr = pd.Series(oos_mask, index=px.index)

        scores = {}
        for name, s in sig.items():
            sel = win[s & isr].dropna()
            if len(sel) >= 30:
                scores[name] = sel.mean()
        # best NON-buyhold strategy in-sample
        best = max((k for k in scores if k != "buy & hold"), key=lambda k: scores[k], default=None)
        if best is None:
            continue
        is_win = scores[best]
        oos_sel = win[sig[best] & oosr].dropna()
        oos_win = oos_sel.mean() if len(oos_sel) >= 15 else float("nan")
        bh_oos = win[oosr].dropna().mean()
        print(f"  {t:6} {best:22} {is_win*100:6.0f}% {oos_win*100:7.0f}% {bh_oos*100:12.0f}%")
        is_best.append(is_win)
        if np.isfinite(oos_win):
            oos_of_best.append(oos_win); bh_oos_all.append(bh_oos)

    print("\n================  THE PUNCHLINE  ================")
    print(f"  Best strategy per stock, IN-SAMPLE win-rate:        {np.mean(is_best)*100:.0f}%  (looks great!)")
    print(f"  THOSE SAME strategies, OUT-OF-SAMPLE win-rate:      {np.mean(oos_of_best)*100:.0f}%")
    print(f"  Plain buy-and-hold, OUT-OF-SAMPLE win-rate:         {np.mean(bh_oos_all)*100:.0f}%")
    print("\n  If the out-of-sample 'best' ≈ buy-and-hold, the high in-sample numbers were")
    print("  drift + luck (data-mining), NOT a repeatable edge.")


if __name__ == "__main__":
    main()
