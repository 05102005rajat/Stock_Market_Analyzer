"""Out-of-sample test on MAY 2026. The model only ever sees data from BEFORE
each prediction (point-in-time), so it never peeks at the answer.

WEEKLY: for each week in May, train on data up to the Friday before, forecast
the week, and check (a) did it call the direction, (b) did the actual price land
inside the predicted range, (c) was the weekly target reached.
MONTHLY: train on data through end of April, forecast all of May, same checks
with the 1-month target.

Run:  ./venv/bin/python -u may_test.py
"""
import numpy as np
import pandas as pd

from services import data, forecast, target

BASKET = ["AAPL", "NVDA", "GOOGL", "MSFT", "CVX", "SHEL", "DLR", "WMT",
          "COST", "CEG", "VST", "PDD", "AMD", "SPY"]
MAY = (pd.Timestamp("2026-05-01"), pd.Timestamp("2026-05-31"))


def main():
    print("Out-of-sample test on MAY 2026 (point-in-time — no peeking)\n", flush=True)
    wk = {"dir": [], "inband": [], "tp_hit": []}
    mo = {"dir": [], "inband": [], "tp_hit": []}

    for t in BASKET:
        try:
            full = data.fetch_ohlcv(t, period="5y", interval="1d")
        except Exception:
            continue
        idx = full.index
        close = full["close"].to_numpy(float)
        high = full["high"].to_numpy(float)
        may_mask = (idx >= MAY[0]) & (idx <= MAY[1])
        if may_mask.sum() < 15:
            continue

        # ---------- WEEKLY ----------
        may_idx = np.where(may_mask)[0]
        weeks = {}
        for i in may_idx:
            weeks.setdefault(idx[i].isocalendar().week, []).append(i)
        for _, days in weeks.items():
            first = days[0]
            cutoff = first - 1               # last trading day before the week
            if cutoff < 260:
                continue
            train = full.iloc[: cutoff + 1]
            h = len(days)
            fc = forecast.forecast(train, horizon=h, interval="1d")
            if not fc["available"]:
                continue
            entry = close[cutoff]
            pl = target.plan(train, horizon=5)
            # last day of the week
            last = days[-1]
            actual_last = close[last]
            p_last = fc["points"][min(h, len(fc["points"])) - 1]
            wk["dir"].append(int(np.sign(p_last["value"] - entry) == np.sign(actual_last - entry)))
            wk["inband"].append(int(p_last["lower"] <= actual_last <= p_last["upper"]))
            if pl.get("available"):
                tp = entry * (1 + pl["take_profit"]["ret_pct"] / 100)
                wk["tp_hit"].append(int(high[first:last + 1].max() >= tp))

        # ---------- MONTHLY ----------
        cutoff = may_idx[0] - 1              # end of April
        if cutoff >= 260:
            train = full.iloc[: cutoff + 1]
            h = len(may_idx)
            fc = forecast.forecast(train, horizon=h, interval="1d")
            if fc["available"]:
                entry = close[cutoff]
                last = may_idx[-1]
                actual_last = close[last]
                p_last = fc["points"][-1]
                mo["dir"].append(int(np.sign(p_last["value"] - entry) == np.sign(actual_last - entry)))
                mo["inband"].append(int(p_last["lower"] <= actual_last <= p_last["upper"]))
                pl = target.plan(train, horizon=21)
                if pl.get("available"):
                    tp = entry * (1 + pl["take_profit"]["ret_pct"] / 100)
                    mo["tp_hit"].append(int(high[may_idx[0]:last + 1].max() >= tp))
        print(f"  tested {t}", flush=True)

    def pct(a):
        return f"{np.mean(a) * 100:.0f}%" if a else "n/a"

    print("\n================  RESULTS  ================")
    print(f"WEEKLY  (n={len(wk['dir'])}):  forecast direction {pct(wk['dir'])}  |  "
          f"actual inside range {pct(wk['inband'])}  |  target reached {pct(wk['tp_hit'])}")
    print(f"MONTHLY (n={len(mo['dir'])}):  forecast direction {pct(mo['dir'])}  |  "
          f"actual inside range {pct(mo['inband'])}  |  target reached {pct(mo['tp_hit'])}")
    print("\nReminder: ~50% direction = coin flip (expected). ~95% inside-range and "
          "~66% target-reached = the calibrated parts working as designed.")


if __name__ == "__main__":
    main()
