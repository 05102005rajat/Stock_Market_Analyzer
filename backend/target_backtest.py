"""Point-in-time calibration test of the weekly trade planner.

At each historical day we estimate the 'safe' take-profit from PRIOR data only,
then check whether the next week actually reached it. If the planner is honest,
the vol-scaled target should be hit ~66% of the time across every ticker — while
a one-size-fits-all fixed +3% target should be hit wildly differently (too easy
for NVDA, too hard for KO). That contrast is the whole point.

Run:  ./venv/bin/python -u target_backtest.py
"""
import numpy as np

from services import data, target, volatility

BASKET = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "KO", "JNJ", "XOM"]
HORIZON = 5
SAMPLE_EVERY = 3
FIXED_TARGET = 0.03  # +3% one-size-fits-all comparison


def main():
    print(f"Weekly target calibration — point-in-time, {HORIZON}-day window\n", flush=True)
    print(f"  {'ticker':6} {'n':>5} {'vol-tgt%':>9} {'vol-hit':>8} {'fixed+3%-hit':>13} {'P(green/wk)':>12}")
    agg_vol_hit, agg_fixed_hit, agg_green, agg_n = 0, 0, 0, 0
    for t in BASKET:
        full = data.fetch_ohlcv(t, period="5y", interval="1d")
        close = full["close"].to_numpy(float)
        high = full["high"].to_numpy(float)
        n = len(full)
        sig_full = volatility.blend_vol_series(full)  # precompute point-in-time once
        tgts, vhits, fhits, greens, cnt = [], 0, 0, 0, 0
        for ti in range(300, n - HORIZON, SAMPLE_EVERY):
            pl = target.plan(full.iloc[: ti + 1], horizon=HORIZON, sig_series=sig_full[: ti + 1])
            if not pl["available"]:
                continue
            tp_ret = pl["take_profit"]["ret_pct"] / 100.0
            entry = close[ti]
            actual_mfe = high[ti + 1: ti + 1 + HORIZON].max() / entry - 1.0
            vhits += int(actual_mfe >= tp_ret)
            fhits += int(actual_mfe >= FIXED_TARGET)
            greens += int(actual_mfe > 0)
            tgts.append(tp_ret)
            cnt += 1
        if cnt:
            print(f"  {t:6} {cnt:5d} {np.mean(tgts)*100:8.2f}% {vhits/cnt*100:7.0f}% "
                  f"{fhits/cnt*100:12.0f}% {greens/cnt*100:11.0f}%", flush=True)
            agg_vol_hit += vhits; agg_fixed_hit += fhits; agg_green += greens; agg_n += cnt

    print("\n" + "=" * 64)
    print(f"OVERALL ({agg_n} samples):")
    print(f"  Vol-scaled target hit rate:   {agg_vol_hit/agg_n*100:.1f}%  (target ~66% = calibrated)")
    print(f"  Fixed +3% target hit rate:    {agg_fixed_hit/agg_n*100:.1f}%  (varies by ticker = not portable)")
    print(f"  P(profitable exit in a week): {agg_green/agg_n*100:.1f}%")


if __name__ == "__main__":
    main()
