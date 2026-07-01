"""Do famous strategies actually beat buy-and-hold? Point-in-time, honest.

PART A — TIMING one instrument: buy-and-hold vs a 200-day moving-average filter
(in the market only when price > 200-DMA, else cash). The classic question:
does getting out below the 200-DMA help? We score TOTAL RETURN, VOLATILITY,
MAX DRAWDOWN (worst peak-to-trough drop) and SHARPE (return per unit of risk).

PART B — PICKING stocks: across a basket, do stocks that pass Minervini /
golden-cross / top relative-strength / oversold-in-uptrend earn higher FORWARD
3-month returns than the universe average? With a significance check.

Run:  ./venv/bin/python -u strategy_test.py
"""
import numpy as np
import pandas as pd

from services import data

BASKET = ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "CVX", "XOM",
          "WMT", "COST", "JPM", "V", "HD", "PG", "JNJ", "UNH", "AMD", "AVGO"]
TIMING = ["SPY", "QQQ", "AAPL", "NVDA"]


def stats(daily_ret):
    eq = np.cumprod(1 + daily_ret)
    total = (eq[-1] - 1) * 100
    vol = np.std(daily_ret, ddof=1) * np.sqrt(252) * 100
    dd = (eq / np.maximum.accumulate(eq) - 1).min() * 100
    sharpe = (np.mean(daily_ret) / (np.std(daily_ret, ddof=1) + 1e-12)) * np.sqrt(252)
    return total, vol, dd, sharpe


def part_a():
    print("PART A — Timing one stock: Buy-and-Hold vs 200-day-MA filter (5y)\n", flush=True)
    print(f"  {'name':6} {'strategy':14} {'return':>9} {'vol':>7} {'maxDD':>8} {'Sharpe':>7}")
    for t in TIMING:
        df = data.fetch_ohlcv(t, period="5y", interval="1d")
        c = df["close"].to_numpy(float)
        r = np.diff(np.log(c))                    # daily log returns (len n-1)
        sma200 = pd.Series(c).rolling(200).mean().to_numpy()
        # Decide using info available the day BEFORE the return (no lookahead).
        in_mkt = (c[:-1] > sma200[:-1]).astype(float)
        in_mkt = np.nan_to_num(in_mkt)
        bh = r
        strat = r * in_mkt                        # in cash (0%) when below the 200-DMA
        for name, ret in (("Buy & Hold", bh), ("200-DMA filter", strat)):
            tot, vol, dd, sh = stats(ret)
            print(f"  {t:6} {name:14} {tot:8.0f}% {vol:6.0f}% {dd:7.0f}% {sh:6.2f}")
        print()


def part_b():
    print("PART B — Picking stocks: forward 3-month return by strategy (vs buy-hold)\n", flush=True)
    H = 63
    spy = data.fetch_ohlcv("SPY", period="5y", interval="1d")["close"]
    closes = {}
    for t in BASKET:
        try:
            closes[t] = data.fetch_ohlcv(t, period="5y", interval="1d")["close"]
        except Exception:
            continue
    px = pd.DataFrame(closes).dropna(how="all")
    spy = spy.reindex(px.index).ffill()

    sma50 = px.rolling(50).mean()
    sma150 = px.rolling(150).mean()
    sma200 = px.rolling(200).mean()
    sma200_prior = sma200.shift(22)
    rsi = px.apply(_rsi)
    rs = (px / px.shift(126) - 1).sub(spy / spy.shift(126) - 1, axis=0)
    fwd = px.shift(-H) / px - 1

    minervini = (px > sma150) & (px > sma200) & (sma150 > sma200) & (sma50 > sma150) & (sma200 > sma200_prior) & (rs > 0)
    golden = sma50 > sma200
    oversold_up = (px > sma200) & (rsi < 40)

    buckets = {"Buy & Hold (all)": pd.DataFrame(True, index=px.index, columns=px.columns),
               "Minervini Stage-2": minervini, "Golden cross": golden,
               "Oversold-in-uptrend": oversold_up}

    rs_rank = rs.rank(axis=1, pct=True)
    buckets["Top relative-strength"] = rs_rank >= 0.75

    # NON-OVERLAPPING in time (every H days) AND aggregated to one observation per
    # DATE before the t-test. Flattening (date, stock) pairs would treat ~15
    # cross-sectionally-correlated names per date as independent and massively
    # overstate the t-stat (design effect ~6x). We compare each strategy's per-date
    # mean to the per-date mean of the NON-selected names, then t-test across dates.
    sub = px.index[list(range(210, len(px) - H, H))]
    print(f"  (using {len(sub)} INDEPENDENT dates; per-date means t-tested across dates — honest)")
    print(f"  {'strategy':22} {'picks':>7} {'avg 3-mo':>9} {'vs rest':>9} {'t-stat':>7}")
    fwd_sub = fwd.loc[sub]
    for name, mask in buckets.items():
        msub = mask.loc[sub]
        sel_all = fwd_sub.where(msub).stack().dropna()
        if len(sel_all) < 20:
            continue
        # per-date difference: mean(selected) - mean(not-selected) on that date
        diffs = []
        for dt in sub:
            sel_d = fwd_sub.loc[dt].where(msub.loc[dt]).dropna()
            rest_d = fwd_sub.loc[dt].where(~msub.loc[dt]).dropna()
            if len(sel_d) and len(rest_d):
                diffs.append(sel_d.mean() - rest_d.mean())
        diffs = np.array(diffs)
        if name.startswith("Buy"):
            tag, t = "", float("nan")
        else:
            t = diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs))) if len(diffs) > 2 else float("nan")
            tag = f"{diffs.mean()*100:+.2f}%"
        print(f"  {name:22} {len(sel_all):7d} {sel_all.mean()*100:8.2f}% {tag:>9} {t:7.2f}")


def _rsi(c, period=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def main():
    part_a()
    part_b()
    print("\nRead: a strategy 'works better' if it beats Buy & Hold on Sharpe / drawdown "
          "(Part A) or earns a higher forward return with a t-stat > 2 (Part B).")


if __name__ == "__main__":
    main()
