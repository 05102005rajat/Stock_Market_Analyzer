"""Shared test helpers. All tests are network-free: they build synthetic
OHLCV frames so the suite never depends on Yahoo Finance."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

# Make `services` importable when running pytest from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def make_df(closes, start="2022-01-03"):
    """Build an OHLCV DataFrame on a business-day index from a close series."""
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range(start=start, periods=len(closes))
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes * 1.01,
            "low": closes * 0.99,
            "close": closes,
            "volume": np.full(len(closes), 1_000_000),
        },
        index=idx,
    )


@pytest.fixture
def make_df_fixture():
    return make_df
