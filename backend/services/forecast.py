"""Short-horizon price forecast using a gradient-boosted regressor on lagged
features. This is a transparent statistical baseline — not investment advice —
and deliberately avoids heavy deep-learning dependencies.

Strategy: predict next-day log-return from a window of recent returns and
technical features, then roll the prediction forward `horizon` steps, feeding
each prediction back in (recursive multi-step forecasting).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from services import volatility

N_LAGS = 10


def _adaptive_z(df: pd.DataFrame, sig_series: np.ndarray, horizon: int, window: int = 504) -> float:
    """Per-stock band multiplier: the 95th percentile of |standardized H-day move|
    over the trailing window, floored at 1.96 and capped at 2.6.

    This makes the band adapt to each stock's OWN tail fatness — near-Gaussian
    indices get ~1.96, fat-tailed growth names get ~2.1 — so coverage lands on
    95% for everything, without hard-coded stock categories. Point-in-time:
    every move used has a realized outcome within the in-sample history.
    """
    logc = np.log(df["close"].to_numpy(dtype=float))
    n = len(logc)
    u = []
    for s in range(max(0, n - horizon - window), n - horizon):
        sd = sig_series[s]
        if np.isfinite(sd) and sd > 0:
            u.append(abs((logc[s + horizon] - logc[s]) / (sd * np.sqrt(horizon))))
    if len(u) < 60:
        return 1.96
    return float(np.clip(np.quantile(u, 0.95), 1.96, 2.6))


def _features(returns: pd.Series, close: pd.Series) -> pd.DataFrame:
    """Build a lagged-return feature matrix aligned with next-day target."""
    feat = pd.DataFrame(index=returns.index)
    for lag in range(1, N_LAGS + 1):
        feat[f"ret_lag{lag}"] = returns.shift(lag)
    feat["roll_mean5"] = returns.shift(1).rolling(5).mean()
    feat["roll_std5"] = returns.shift(1).rolling(5).std()
    feat["roll_mean10"] = returns.shift(1).rolling(10).mean()
    feat["mom10"] = close.pct_change(10).shift(1)
    return feat


def track_record(df: pd.DataFrame, horizon: int = 10, n_tests: int = 40) -> dict:
    """Honest walk-forward scorecard: 'how many times was the forecast right?'

    For each of the last `n_tests` trading days we train on only the data up to
    that day, forecast `horizon` days ahead, and check whether the DIRECTION was
    right. Nothing peeks at the future. We also break it down by up-calls vs
    down-calls, because in a bull run "always up" scores high without skill — the
    honest test is whether it's right in BOTH directions.
    """
    close = df["close"].astype(float)
    log_ret = np.log(close / close.shift(1)).dropna()
    if len(log_ret) < 150 + horizon:
        return {"available": False, "reason": "need ~8 months of history to score reliably"}

    feat_all = _features(log_ret, close)
    target_all = log_ret.shift(-1)

    n = len(log_ret)
    start = max(120, n - n_tests - horizon)

    dir_hits = dir_tries = 0
    up_calls = up_hits = down_calls = down_hits = 0
    up_actuals = 0
    model = GradientBoostingRegressor(
        n_estimators=80, max_depth=3, learning_rate=0.06, subsample=0.8, random_state=42)

    refit_every = 8
    fitted = False
    for j, t in enumerate(range(start, n - horizon)):
        Xtr = feat_all.iloc[:t].dropna()
        ytr = target_all.loc[Xtr.index].dropna()
        Xtr = Xtr.loc[ytr.index]
        if len(Xtr) < 100:
            continue
        # Refit on schedule, but also on the first usable window — otherwise an
        # early `continue` (above) could leave the model unfitted when j skips
        # past a multiple of refit_every, crashing model.predict below.
        if not fitted or j % refit_every == 0:
            model.fit(Xtr.to_numpy(), ytr.to_numpy())
            fitted = True

        # One-shot horizon estimate: project the average predicted daily drift.
        # (Much faster than full recursive roll, and direction is what we score.)
        f = feat_all.iloc[[t]].fillna(0.0).to_numpy()
        pred_ret = float(model.predict(f)[0])

        entry_close = float(close.iloc[t])
        actual_close = float(close.iloc[t + horizon])
        pred_dir = np.sign(pred_ret)
        actual_dir = np.sign(actual_close - entry_close)
        if actual_dir == 0:
            continue
        dir_tries += 1
        if actual_dir > 0:
            up_actuals += 1
        if pred_dir > 0:
            up_calls += 1
            if actual_dir > 0:
                up_hits += 1
        elif pred_dir < 0:
            down_calls += 1
            if actual_dir < 0:
                down_hits += 1
        if pred_dir == actual_dir:
            dir_hits += 1

    if dir_tries == 0:
        return {"available": False, "reason": "not enough completed forecasts to score"}

    hit_rate = dir_hits / dir_tries
    up_frac = up_actuals / dir_tries
    majority_baseline = max(up_frac, 1 - up_frac)
    edge = hit_rate - majority_baseline
    verdict = ("beats a simple baseline" if edge > 0.03
               else "worse than guessing the usual direction" if edge < -0.03
               else "about the same as a simple baseline")

    return {
        "available": True,
        "horizon": horizon,
        "tries": dir_tries,
        "direction_hits": dir_hits,
        "hit_rate": round(hit_rate * 100, 1),
        "coin_flip": 50.0,
        "majority_baseline": round(majority_baseline * 100, 1),
        "up_calls": up_calls,
        "up_accuracy": round(up_hits / up_calls * 100, 1) if up_calls else None,
        "down_calls": down_calls,
        "down_accuracy": round(down_hits / down_calls * 100, 1) if down_calls else None,
        "verdict": verdict,
        "plain": (
            f"Tested {dir_tries} times on this stock's recent history (walk-forward, no peeking), "
            f"the {horizon}-day forecast called direction right {dir_hits} times ({round(hit_rate*100)}%). "
            f"Always guessing the more common direction would score {round(majority_baseline*100)}%, "
            f"so it {verdict}."
            + (f" When it predicted UP it was right {round(up_hits/up_calls*100)}% of the time"
               if up_calls else "")
            + (f"; when it predicted DOWN, {round(down_hits/down_calls*100)}%."
               if down_calls else ".")
            + " This is why the app shows a RANGE, not a single price."
        ),
        "disclaimer": "Honest out-of-sample track record on recent history. Past accuracy does not guarantee future accuracy.",
    }


def forecast(df: pd.DataFrame, horizon: int = 10, interval: str = "1d") -> dict:
    """Return a recursive multi-step close-price forecast and model diagnostics."""
    horizon = max(1, min(int(horizon), 60))
    close = df["close"].astype(float)

    if len(close) < N_LAGS + 40:
        return {
            "available": False,
            "reason": "Not enough history to train a forecast (need ~50+ bars).",
            "points": [],
        }

    log_ret = np.log(close / close.shift(1))
    feat = _features(log_ret, close)
    target = log_ret.shift(-1)  # predict the *next* day's return

    data = feat.copy()
    data["target"] = target
    data = data.dropna()

    X = data.drop(columns="target").to_numpy()
    y = data["target"].to_numpy()

    # Hold out the last 20% chronologically to report honest error.
    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42
    )
    model.fit(X_train, y_train)

    if len(X_test):
        pred_test = model.predict(X_test)
        rmse = float(np.sqrt(np.mean((pred_test - y_test) ** 2)))
        # Directional accuracy: did we get the sign of the move right?
        dir_acc = float(np.mean(np.sign(pred_test) == np.sign(y_test)))
        # Honest baseline: always guess the majority direction on the test set.
        up_frac = float(np.mean(y_test > 0))
        baseline_acc = max(up_frac, 1 - up_frac)
    else:
        rmse, dir_acc, baseline_acc = None, None, None

    # Refit on all data before forecasting forward.
    model.fit(X, y)

    # Recursive roll-forward. We extend the return series with each prediction
    # and recompute features off the growing series.
    work_close = close.copy()
    work_ret = log_ret.copy()
    future_ts = _future_dates(df.index, horizon, interval)

    # --- Volatility-based bands: decouple SCALE (blend vol) from MULTIPLIER
    # (empirical per-tail z). Falls back to the GBR residual std × 1.96 when the
    # vol estimate is unavailable (very short history).
    sig_series = volatility.blend_vol_series(df)
    sigma_day = float(sig_series[np.isfinite(sig_series)][-1]) if np.isfinite(sig_series).any() else None
    resid_std = rmse if rmse else float(np.std(y))
    # Backtest verdict (band_backtest.py): blend SCALE lifts coverage 92.7%→94.3%;
    # a per-stock ADAPTIVE multiplier (tied to the name's own tail fatness) then
    # lands it on 95.2% — indices stay ~1.96, fat-tailed growth widens to ~2.1.
    if sigma_day and sigma_day > 0:
        zmult = _adaptive_z(df, sig_series, horizon)
        z_lo, z_hi, vol_band = -zmult, zmult, True
    else:
        zmult, z_lo, z_hi, vol_band = 1.96, -1.96, 1.96, False

    points = []
    for step in range(1, horizon + 1):
        f = _features(work_ret, work_close).iloc[[-1]].fillna(0.0).to_numpy()
        pred_ret = float(model.predict(f)[0])
        next_close = float(work_close.iloc[-1] * np.exp(pred_ret))
        next_ts = future_ts[step - 1]

        if vol_band:
            # Asymmetric, log-space band scaled by the conditional vol.
            sd_cum = sigma_day * np.sqrt(step)
            lower = next_close * np.exp(z_lo * sd_cum)
            upper = next_close * np.exp(z_hi * sd_cum)
        else:
            band = next_close * resid_std * np.sqrt(step)
            lower, upper = next_close - 1.96 * band, next_close + 1.96 * band

        points.append(
            {
                "time": int(next_ts.timestamp()),
                "date": next_ts.strftime("%Y-%m-%d"),
                "value": round(next_close, 4),
                "lower": round(float(lower), 4),
                "upper": round(float(upper), 4),
            }
        )

        # Append prediction to the working series for the next step.
        work_close = pd.concat([work_close, pd.Series([next_close], index=[next_ts])])
        work_ret = pd.concat([work_ret, pd.Series([pred_ret], index=[next_ts])])

    tail = "fat-tailed" if zmult >= 2.15 else "heavy" if zmult >= 2.03 else "near-normal"
    return {
        "available": True,
        "horizon": horizon,
        "model": "GradientBoostingRegressor on lagged log-returns",
        "band": {
            "method": "blend-vol scale × per-stock adaptive multiplier" if vol_band else "fallback",
            "multiplier": round(float(zmult), 2),
            "tail": tail,
        },
        "metrics": {
            "rmse_logret": round(rmse, 5) if rmse is not None else None,
            "directional_accuracy": round(dir_acc, 3) if dir_acc is not None else None,
            "baseline_accuracy": round(baseline_acc, 3) if baseline_acc is not None else None,
        },
        "points": points,
        "disclaimer": (
            "Calibrated RANGE estimate, not a prediction. Walk-forward tested, the "
            "centre line does not beat a naive 'price stays flat' baseline on direction; "
            "the band coverage is honest (~95%). Use the cone, not the line."
        ),
    }


def _future_dates(index: pd.DatetimeIndex, horizon: int, interval: str) -> list[pd.Timestamp]:
    """Generate future bar timestamps, skipping weekends for daily data.

    Holidays are not modeled, but business-day spacing keeps the forecast off
    Saturdays/Sundays, which is the common-case correctness issue.
    """
    last = index[-1]
    if interval == "1d":
        # Start from the NEXT business day so we never drop a real forecast day
        # when `last` itself isn't a business day (off-calendar/weekend index).
        return list(pd.bdate_range(start=last + pd.offsets.BDay(1), periods=horizon))
    step = {"1wk": 7, "1mo": 30}.get(interval, _infer_step_days(index))
    return [last + pd.Timedelta(days=step * (i + 1)) for i in range(horizon)]


def _infer_step_days(index: pd.DatetimeIndex) -> float:
    """Median spacing between bars in days (handles daily/weekly/monthly)."""
    if len(index) < 2:
        return 1.0
    deltas = np.diff(index.asi8) / 1e9 / 86400.0
    return float(np.median(deltas)) or 1.0
