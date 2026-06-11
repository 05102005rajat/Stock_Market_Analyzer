"""Fetch and normalize OHLCV price data from Yahoo Finance via yfinance."""
from __future__ import annotations

import time

import pandas as pd
import yfinance as yf

# Allowed (period, interval) constraints loosely mirror Yahoo's limits.
VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"}
VALID_INTERVALS = {"1h", "1d", "1wk", "1mo"}

# Small in-process TTL cache so repeated requests (and the extra get_meta call)
# don't hammer Yahoo and trip rate limits.
_CACHE_TTL_SECONDS = 300
_cache: dict[tuple, tuple[float, object]] = {}


def _cache_get(key: tuple):
    hit = _cache.get(key)
    if hit and (time.time() - hit[0]) < _CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _cache_set(key: tuple, value) -> None:
    _cache[key] = (time.time(), value)


def fetch_ohlcv(ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Return a clean DataFrame indexed by date with OHLCV columns.

    Raises ValueError if the ticker is unknown or returns no data.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker is required")
    if period not in VALID_PERIODS:
        period = "1y"
    if interval not in VALID_INTERVALS:
        interval = "1d"
    # Intraday (hourly) data is only available for a limited recent window
    # (~730 days) on Yahoo, so cap long spans to something it will actually return.
    if interval == "1h" and period in {"5y", "10y", "max"}:
        period = "2y"

    cache_key = ("ohlcv", ticker, period, interval)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached.copy()

    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'")

    # yfinance may return a MultiIndex (column, ticker) when given one symbol.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df = df[["open", "high", "low", "close", "volume"]]
    # Only require the price columns; a missing volume (indices/FX) shouldn't
    # wipe otherwise-valid rows.
    df = df.dropna(subset=["open", "high", "low", "close"])
    if df.empty:
        raise ValueError(f"No usable price data for ticker '{ticker}'")
    df.index = pd.to_datetime(df.index)

    _cache_set(cache_key, df)
    return df.copy()


def get_meta(ticker: str) -> dict:
    """Best-effort company/quote metadata. Cached and never raises."""
    ticker = ticker.strip().upper()
    key = ("meta", ticker)
    cached = _cache_get(key)
    if cached is not None:
        return cached
    fallback = {"name": ticker, "currency": "USD", "exchange": "", "sector": ""}
    try:
        info = yf.Ticker(ticker).info
        meta = {
            "name": info.get("longName") or info.get("shortName") or ticker,
            "currency": info.get("currency", "USD"),
            "exchange": info.get("fullExchangeName") or info.get("exchange", ""),
            "sector": info.get("sector", ""),
        }
        _cache_set(key, meta)
        return meta
    except Exception:
        return fallback


def to_candles(df: pd.DataFrame) -> list[dict]:
    """Serialize OHLCV rows to a JSON-friendly list (epoch-second time keys)."""
    out = []
    for ts, row in df.iterrows():
        vol = row["volume"]
        out.append(
            {
                "time": int(ts.timestamp()),
                "date": ts.strftime("%Y-%m-%d"),
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": round(float(row["close"]), 4),
                "volume": int(vol) if pd.notna(vol) else 0,
            }
        )
    return out
