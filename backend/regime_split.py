"""Regime-split robustness check for the recovery hypothesis.

Question: is the 'still-weak / recovering bounces' result carried by the 2020
COVID V-shaped recovery, or does it hold in non-2020 regimes?

For R2_recovering_state, R5_slope50_up, STILL_WEAK we recompute, split by the
SIGNAL date into 4 buckets:
  (1) 2016-2019, (2) 2020 (COVID crash+bounce), (3) 2021-2022 (bear), (4) 2023-2026
  - pooled forward-3mo mean return (descriptive, overlapping)
  - per-date-diff vs other stocks, NON-OVERLAPPING (same stride-H logic as rt)
"""
import numpy as np
import pandas as pd

import recovery_test as rt

H = 63  # 3 months

px = rt.load_closes()
f = rt.features(px)

BUCKETS = [
    ("2016-2019", "2016-01-01", "2019-12-31"),
    ("2020_COVID", "2020-01-01", "2020-12-31"),
    ("2021-2022_bear", "2021-01-01", "2022-12-31"),
    ("2023-2026", "2023-01-01", "2026-12-31"),
]

fwd = px.shift(-H) / px - 1  # forward 3mo return aligned to signal date


def in_bucket(idx, lo, hi):
    return (idx >= pd.Timestamp(lo)) & (idx <= pd.Timestamp(hi))


def pooled_mean(mask, lo, hi):
    """Descriptive pooled forward-3mo mean for signals fired in [lo,hi]."""
    m = mask.copy()
    sel = in_bucket(m.index, lo, hi)
    m.loc[~sel] = False
    vals = fwd.where(m).stack().dropna()
    return (round(float(vals.mean()) * 100, 2) if len(vals) else None,
            int(len(vals)))


def perdate_diff_bucket(mask, lo, hi):
    """Non-overlapping per-date diff vs OTHER stocks, restricted to dates in
    [lo,hi]. Mirrors rt._perdate_diff_t stride-H sampling so dates stay
    non-overlapping, then filters to the bucket window."""
    dates = fwd.index[list(range(260, len(fwd) - H, H))]
    diffs = []
    for dt in dates:
        if not (pd.Timestamp(lo) <= dt <= pd.Timestamp(hi)):
            continue
        sel = fwd.loc[dt].where(mask.loc[dt]).dropna()
        rest = fwd.loc[dt].where(~mask.loc[dt]).dropna()
        if len(sel) and len(rest):
            diffs.append(sel.mean() - rest.mean())
    diffs = np.array(diffs)
    if len(diffs) > 2:
        t = diffs.mean() / (diffs.std(ddof=1) / np.sqrt(len(diffs)))
    else:
        t = float("nan")
    return (round(float(diffs.mean()) * 100, 2) if len(diffs) else None,
            round(float(t), 2) if len(diffs) > 2 else None,
            int(len(diffs)))


SIGNALS = ["R2_recovering_state", "R5_slope50_up", "STILL_WEAK"]

print(f"{'signal':22s} {'bucket':16s} {'pool3mo%':>9s} {'n_obs':>7s} "
      f"{'diffVother%':>12s} {'t':>6s} {'ndates':>7s}")
print("-" * 90)
for key in SIGNALS:
    mask = rt.signal(key, f)
    # full-sample reference row
    fm, fn = pooled_mean(mask, "2000-01-01", "2099-01-01")
    fd, ft, fnd = perdate_diff_bucket(mask, "2000-01-01", "2099-01-01")
    print(f"{key:22s} {'ALL':16s} {str(fm):>9s} {fn:>7d} "
          f"{str(fd):>12s} {str(ft):>6s} {fnd:>7d}")
    for name, lo, hi in BUCKETS:
        pm, pn = pooled_mean(mask, lo, hi)
        dd, tt, nd = perdate_diff_bucket(mask, lo, hi)
        print(f"{'':22s} {name:16s} {str(pm):>9s} {pn:>7d} "
              f"{str(dd):>12s} {str(tt):>6s} {nd:>7d}")
    print()

# Also: how concentrated are signal firings by year? (where does the data live)
print("\n=== signal-firing counts by year (pooled obs that have a fwd-3mo) ===")
for key in SIGNALS:
    mask = rt.signal(key, f)
    s = fwd.where(mask).stack().dropna()
    yrs = s.index.get_level_values(0).year
    vc = pd.Series(yrs).value_counts().sort_index()
    print(f"{key:22s} " + " ".join(f"{y}:{c}" for y, c in vc.items()))
