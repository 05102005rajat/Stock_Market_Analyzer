"""Does a BUY-THE-DIP / SELL-THE-BOUNCE verdict actually work? A real trade
simulator, point-in-time (signals act on the PRIOR day), realistic exits, scored
by win-rate + expectancy + profit-factor and compared to RANDOM entries of the
same holding length (the honest 'is it better than luck?' benchmark).

ENTRY  : RSI(2) < ENTRY_RSI and price > 200-day MA (oversold dip inside an uptrend)
EXIT   : price closes back above the 5-day MA (bounce), OR +TARGET hit, OR -STOP, OR time-stop
Run    : ./venv/bin/python -u trade_test.py
"""
import numpy as np
import pandas as pd

from services import data

BASKET = ["AAPL", "NVDA", "GOOGL", "MSFT", "AMZN", "META", "AMD", "AVGO", "TSLA",
          "NFLX", "CVX", "WMT", "COST", "JPM", "V", "HD", "PG", "JNJ", "VST", "CEG"]
ENTRY_RSI = 15
TARGET = 0.06     # take profit
STOP = -0.08
MAXDAYS = 12


def _rsi(c, p=2):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / p, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / p, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _exit_walk(c, sma5, entries):
    """Apply the SAME exit logic to a given set of (sorted) entry day-indices."""
    n = len(c)
    trades, durations = [], []
    in_t, ep, ei = False, 0.0, 0
    eset = set(int(x) for x in entries)
    for i in range(210, n):
        if not in_t:
            if (i - 1) in eset:
                in_t, ep, ei = True, c[i], i
        else:
            ret = c[i] / ep - 1
            if (c[i] > sma5[i]) or ret >= TARGET or ret <= STOP or (i - ei) >= MAXDAYS:
                trades.append(ret); durations.append(i - ei); in_t = False
    return np.array(trades), np.array(durations)


def simulate(df):
    c = df["close"].to_numpy(float)
    rsi2 = _rsi(df["close"], 2).to_numpy()
    sma200 = df["close"].rolling(200).mean().to_numpy()
    sma5 = df["close"].rolling(5).mean().to_numpy()
    n = len(c)
    cond = (rsi2 < ENTRY_RSI) & (c > sma200)
    dip_entries = np.where(cond[210:n])[0] + 210
    return c, sma5, dip_entries


def random_benchmark(c, sma5, n_entries, rng):
    """Random entry days run through the SAME exit logic — isolates ENTRY skill
    from the (win-rate-inflating) exit mechanics."""
    if n_entries == 0:
        return np.array([])
    cand = np.arange(210, len(c) - 1)
    ent = rng.choice(cand, size=min(n_entries, len(cand)), replace=False)
    trades, _ = _exit_walk(c, sma5, np.sort(ent))
    return trades


def stats(trades):
    if len(trades) == 0:
        return None
    wins = trades[trades > 0]
    losses = trades[trades <= 0]
    pf = wins.sum() / (-losses.sum()) if len(losses) and losses.sum() < 0 else float("inf")
    return {"n": len(trades), "win": float(np.mean(trades > 0)), "avg": float(np.mean(trades)),
            "pf": pf}


def main():
    print(f"Buy-the-dip simulator (RSI2<{ENTRY_RSI} in uptrend; exit on bounce/+{int(TARGET*100)}%/-{int(-STOP*100)}%/{MAXDAYS}d)\n", flush=True)
    print(f"  {'stock':6} {'trades':>7} {'win%':>6} {'avg/trade':>10} {'PF':>5}   {'random-same-exit win%':>21}")
    rng = np.random.default_rng(0)
    allt, allrand = [], []
    for t in BASKET:
        try:
            df = data.fetch_ohlcv(t, period="5y", interval="1d")
        except Exception:
            continue
        c, sma5, dip_entries = simulate(df)
        trades, _ = _exit_walk(c, sma5, dip_entries)
        s = stats(trades)
        if not s:
            continue
        rb = random_benchmark(c, sma5, len(dip_entries), rng)  # same exit logic
        rwin = float(np.mean(rb > 0)) if len(rb) else float("nan")
        allt.append(trades); allrand.append(rb)
        print(f"  {t:6} {s['n']:7d} {s['win']*100:5.0f}% {s['avg']*100:9.2f}% {s['pf']:5.2f}   "
              f"{rwin*100:13.0f}%", flush=True)

    at = np.concatenate(allt); ar = np.concatenate(allrand)
    S = stats(at)
    print("\n" + "=" * 60)
    print(f"OVERALL: {S['n']} trades | win {S['win']*100:.0f}% | avg/trade {S['avg']*100:+.2f}% | "
          f"profit-factor {S['pf']:.2f}")
    print(f"RANDOM entries (SAME exit rules): win {np.mean(ar>0)*100:.0f}% | avg {np.mean(ar)*100:+.2f}%")
    edge = (S['win'] - np.mean(ar > 0)) * 100
    # significance: is the dip win-rate > random? two-proportion z
    p1, n1 = S['win'], S['n']; p2, n2 = np.mean(ar > 0), len(ar)
    pp = (p1 * n1 + p2 * n2) / (n1 + n2)
    z = (p1 - p2) / np.sqrt(pp * (1 - pp) * (1 / n1 + 1 / n2))
    print(f"\nWin-rate edge over random: {edge:+.0f} points (z = {z:+.1f}).")
    print("Verdict:", "REAL EDGE (z>2 and positive expectancy)" if z > 2 and S['avg'] > 0 else
          "no reliable edge over random luck.")


if __name__ == "__main__":
    main()
