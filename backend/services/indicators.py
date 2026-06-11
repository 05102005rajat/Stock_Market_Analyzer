"""Technical indicators computed with pandas/numpy (no TA-Lib dependency)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI.

    Edge cases handled explicitly so a strong run doesn't return NaN:
    - no losses in the window  -> RSI = 100
    - no gains in the window    -> RSI = 0
    - flat (no gains or losses) -> RSI = 50
    Warm-up bars (first `period`) remain NaN via min_periods.
    """
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi_series = 100 - (100 / (1 + rs))
    # Resolve the divide-by-zero cases the ratio leaves as NaN/inf.
    rsi_series = rsi_series.where(avg_loss != 0, 100.0)
    rsi_series = rsi_series.where(avg_gain != 0, 0.0)
    rsi_series = rsi_series.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)
    # Restore warm-up NaNs (where the rolling averages were undefined).
    rsi_series = rsi_series.where(avg_gain.notna() & avg_loss.notna(), np.nan)
    return rsi_series


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "hist": hist})


def bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    return pd.DataFrame(
        {"bb_mid": mid, "bb_upper": mid + num_std * std, "bb_lower": mid - num_std * std}
    )


def _line(df: pd.DataFrame, series: pd.Series) -> list[dict]:
    """Pair an indicator series with epoch-second timestamps, dropping NaNs."""
    out = []
    for ts, val in series.items():
        if pd.isna(val):
            continue
        out.append({"time": int(ts.timestamp()), "value": round(float(val), 4)})
    return out


def compute_all(df: pd.DataFrame) -> dict:
    """Return every indicator as JSON-friendly line series plus latest snapshot."""
    close = df["close"]
    macd_df = macd(close)
    bb = bollinger(close)
    rsi_series = rsi(close)

    indicators = {
        "sma20": _line(df, sma(close, 20)),
        "sma50": _line(df, sma(close, 50)),
        "ema12": _line(df, ema(close, 12)),
        "ema26": _line(df, ema(close, 26)),
        "rsi": _line(df, rsi_series),
        "macd": _line(df, macd_df["macd"]),
        "macd_signal": _line(df, macd_df["signal"]),
        "macd_hist": _line(df, macd_df["hist"]),
        "bb_upper": _line(df, bb["bb_upper"]),
        "bb_mid": _line(df, bb["bb_mid"]),
        "bb_lower": _line(df, bb["bb_lower"]),
    }

    def last(series: pd.Series):
        s = series.dropna()
        return round(float(s.iloc[-1]), 4) if not s.empty else None

    latest = {
        "close": last(close),
        "sma20": last(sma(close, 20)),
        "sma50": last(sma(close, 50)),
        "rsi": last(rsi_series),
        "macd": last(macd_df["macd"]),
        "macd_signal": last(macd_df["signal"]),
    }
    return {"indicators": indicators, "latest": latest}
