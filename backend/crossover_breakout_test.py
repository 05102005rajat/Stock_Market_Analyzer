"""Point-in-time backtest: was the EMA/MACD crossover BUY flashing BEFORE big
up-moves ('bumps'), and does a BUY actually beat the base rate for a breakout?

No lookahead: EMAs/MACD are causal (ewm), so reading them at day t uses only
data up to t. Forward returns use t+H (the future we're trying to predict).
"""
import warnings; warnings.filterwarnings("ignore")
import pickle
import numpy as np
import pandas as pd

cache = pickle.load(open(".resistance_cache.pkl", "rb"))
CLOSE = cache["close"]
TICKERS = list(CLOSE.columns)

# user's holdings that exist in the cache
HELD = ["NVDA", "AAPL", "MU", "AVGO", "INTC", "NKE", "UNH", "CEG", "AMZN", "MSFT"]

EMA_F, EMA_M, EMA_S = 55, 89, 204
MACD_F, MACD_S, MACD_SIG = 13, 34, 9
H = 21          # forward horizon (≈1 trading month)
BUMP = 0.15     # a "bump"/breakout = +15% over the next H days
CRASH = -0.15   # a "crash" = -15% over the next H days


def ema(s, span):
    return s.ewm(span=span, adjust=False).mean()


def signal_frame(close):
    """Per-day BUY/SELL booleans (point-in-time) for one ticker."""
    c = close.dropna()
    ef, em, es = ema(c, EMA_F), ema(c, EMA_M), ema(c, EMA_S)
    macd = ema(c, MACD_F) - ema(c, MACD_S)
    bull_stack = (ef > em) & (em > es)
    buy = bull_stack & (macd > 0) & (c > ef)
    bear_stack = (ef < em) & (em < es)
    sell = bear_stack & (macd < 0) & (c < ef)
    fwd = c.shift(-H) / c - 1.0
    warm = c.notna().cumsum() > (EMA_S + 5)   # ignore EMA warm-up
    return pd.DataFrame({"close": c, "buy": buy, "sell": sell, "fwd": fwd,
                         "warm": warm})


# ---------------------------------------------------------------------------
# PART A — concrete: before each stock's BIGGEST bump, what did the signal say?
# ---------------------------------------------------------------------------
print("="*78)
print("PART A — your stocks: the day BEFORE their biggest 1-month surge,")
print("         what was the EMA/MACD signal already saying?")
print("="*78)
print(f"{'TKR':5s} {'surge start':11s} {'+21d move':>9s}  signal the day before")
print("-"*78)
for tk in HELD:
    sf = signal_frame(CLOSE[tk])
    sf = sf[sf["warm"]]
    if sf["fwd"].dropna().empty:
        print(f"{tk:5s} (insufficient history)"); continue
    # biggest forward 21d move and the day it started
    start = sf["fwd"].idxmax()
    move = sf.loc[start, "fwd"]
    # signal as of the day BEFORE the surge began
    prior = sf.loc[:start].iloc[-2] if len(sf.loc[:start]) >= 2 else sf.loc[start]
    state = "BUY" if prior["buy"] else "SELL" if prior["sell"] else "neutral"
    print(f"{tk:5s} {start.strftime('%Y-%m-%d')}  {move*100:>7.0f}%   {state}")

# ---------------------------------------------------------------------------
# PART B — the honest test across ALL 80 cached large-caps:
#   does a BUY signal actually precede a bump more than the base rate? and
#   does it ALSO precede crashes (which cherry-picking winners would hide)?
# ---------------------------------------------------------------------------
all_fwd, all_buy, all_sell = [], [], []
fresh_buy_fwd = []   # the actionable moment: the day the signal FLIPS to buy
for tk in TICKERS:
    sf = signal_frame(CLOSE[tk])
    sf = sf[sf["warm"]].dropna(subset=["fwd"])
    if sf.empty:
        continue
    all_fwd.append(sf["fwd"].to_numpy())
    all_buy.append(sf["buy"].to_numpy())
    all_sell.append(sf["sell"].to_numpy())
    flip = sf["buy"].to_numpy() & ~np.r_[False, sf["buy"].to_numpy()[:-1]]
    fresh_buy_fwd.append(sf["fwd"].to_numpy()[flip])

fwd = np.concatenate(all_fwd)
buy = np.concatenate(all_buy)
sell = np.concatenate(all_sell)
fresh = np.concatenate(fresh_buy_fwd) if fresh_buy_fwd else np.array([])

def rate(mask_returns, thr, up=True):
    if len(mask_returns) == 0: return float("nan"), 0
    hits = (mask_returns >= thr) if up else (mask_returns <= thr)
    return hits.mean()*100, len(mask_returns)

base_bump, n_all = rate(fwd, BUMP)
buy_bump, n_buy = rate(fwd[buy], BUMP)
fresh_bump, n_fresh = rate(fresh, BUMP)
base_crash, _ = rate(fwd, CRASH, up=False)
buy_crash, _ = rate(fwd[buy], CRASH, up=False)

print()
print("="*78)
print(f"PART B — honest hit-rate across all {len(TICKERS)} large-caps, "
      f"{n_all:,} stock-days")
print(f"         a 'bump' = +{int(BUMP*100)}% over the next {H} trading days")
print("="*78)
print(f"  Base rate  P(bump in {H}d), ANY day ...................... {base_bump:5.1f}%")
print(f"  After a BUY signal is active ........................... {buy_bump:5.1f}%   (n={n_buy:,})")
print(f"  On the day the signal FRESHLY flips to BUY ............. {fresh_bump:5.1f}%   (n={n_fresh:,})")
print(f"  --> lift over base from a fresh BUY: {fresh_bump-base_bump:+.1f} pts")
print()
print(f"  But does BUY also precede CRASHES (-{int(abs(CRASH)*100)}% in {H}d)?")
print(f"  Base rate  P(crash), ANY day .......................... {base_crash:5.1f}%")
print(f"  After a BUY signal is active .......................... {buy_crash:5.1f}%")
print()
# average forward return after buy vs base
print(f"  Avg forward {H}d return — base: {fwd.mean()*100:+.2f}%   "
      f"after BUY: {fwd[buy].mean()*100:+.2f}%   "
      f"fresh BUY: {fresh.mean()*100:+.2f}%" if len(fresh) else "")
