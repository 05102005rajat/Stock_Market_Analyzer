"""Does 'buy where a politician disclosed buying, when price returns to that
level' beat just buying the index? Honest, disclosure-lag-aware backtest.

Vedant's hypothesis: if a disclosed trade bought stock X at price P, and X is
near P again now, that's a good buy.

Why this is the honest design:
  * Trades are stamped at the DISCLOSURE date (trade_day + ~45d), the earliest
    you could actually have acted. Using the trade date would be look-ahead.
  * Signal fires when price returns within TOL of the disclosed entry AFTER
    disclosure. Forward 21/63d return is measured vs QQQ bought the same day.
  * Edge = signal return minus QQQ return. |t|>2 and positive edge would mean
    a real effect; ~0 with |t|<2 means it's just buying the index.

DATA (free, no Quiver needed): the broader, better-sampled version of this is
congressional trades. Pull them from the free Quiver congressional CSV or the
House/Senate disclosure scrapers, into a DataFrame with columns:
    ticker, transaction_date, disclosure_date, type ('Purchase')
Then provide a price fetcher (yfinance) and run. Politician-specific feeds
(e.g. Quiver's Trump endpoint) are paid; the congressional set is free, larger,
and tests the identical mechanism.

Usage:
    trades = load_congress_trades_csv("congress_trades.csv")  # your file
    run(trades, fetch_close=yf_close)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

LAG_FALLBACK = 45
TOL = 0.02
HORIZONS = (21, 63)
WATCH_DAYS = 120


def yf_close(ticker: str) -> pd.Series:
    import yfinance as yf
    s = yf.Ticker(ticker).history(period="10y")["Close"]
    s.index = s.index.tz_localize(None)
    return s


def load_congress_trades_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.lower().strip() for c in df.columns]
    df = df.rename(columns={"transactiondate": "transaction_date",
                            "disclosuredate": "disclosure_date"})
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    if "disclosure_date" in df:
        df["disclosure_date"] = pd.to_datetime(df["disclosure_date"])
    else:
        df["disclosure_date"] = df["transaction_date"] + pd.Timedelta(days=LAG_FALLBACK)
    is_buy = df.get("type", "Purchase").astype(str).str.contains("urchase|uy", regex=True)
    return df[is_buy].copy()


def run(trades: pd.DataFrame, fetch_close, market_ticker: str = "QQQ") -> dict:
    qqq = fetch_close(market_ticker)
    hits = []
    price_cache: dict[str, pd.Series] = {}
    for _, tr in trades.iterrows():
        tk = str(tr["ticker"]).upper()
        try:
            p = price_cache.get(tk) or price_cache.setdefault(tk, fetch_close(tk))
        except Exception:
            continue
        if p is None or p.empty:
            continue
        disclosed = pd.Timestamp(tr["disclosure_date"])
        after = p[p.index >= disclosed]
        if len(after) < max(HORIZONS) + 5:
            continue
        entry = float(p.asof(pd.Timestamp(tr["transaction_date"])))
        if not np.isfinite(entry) or entry <= 0:
            continue
        watch = after.iloc[:WATCH_DAYS]
        near = watch[(watch / entry - 1).abs() <= TOL]
        if near.empty:
            continue
        t0 = near.index[0]
        i = p.index.get_loc(t0)
        if i + max(HORIZONS) >= len(p):
            continue
        qi = qqq.index.get_indexer([t0], method="nearest")[0]
        row = {"ticker": tk}
        ok = True
        for h in HORIZONS:
            row[f"stk_{h}"] = float(p.iloc[i + h] / p.iloc[i] - 1)
            if qi + h < len(qqq):
                row[f"qqq_{h}"] = float(qqq.iloc[qi + h] / qqq.iloc[qi] - 1)
            else:
                ok = False
        if ok:
            hits.append(row)
    hits = pd.DataFrame(hits)
    print(f"signals (price returned to disclosed entry, post-disclosure): {len(hits)}\n")
    if hits.empty:
        print("No signals. Check ticker formatting / date columns.")
        return {"n": 0}
    print(f"{'horizon':>8} {'stock':>9} {'qqq':>8} {'edge':>8} {'t':>7} {'win_vs_qqq':>11}")
    out = {"n": len(hits)}
    for h in HORIZONS:
        d = (hits[f"stk_{h}"] - hits[f"qqq_{h}"]).dropna()
        t = stats.ttest_1samp(d, 0)
        print(f"{h:>6}d  {hits[f'stk_{h}'].mean()*100:>7.2f}% {hits[f'qqq_{h}'].mean()*100:>7.2f}% "
              f"{d.mean()*100:>+7.2f}% {t.statistic:>7.2f} {(d>0).mean()*100:>10.0f}%")
        out[f"edge_{h}"] = round(d.mean()*100, 2)
        out[f"t_{h}"] = round(float(t.statistic), 2)
    print("\nIf edge ~ 0 and |t| < 2: 'same price as the politician' adds nothing "
          "over buying the index.")
    return out


if __name__ == "__main__":
    print("Provide a congress-trades CSV and run(). See module docstring.")
