"""Tests for services/extension.py, services/news.py, services/checklist.py."""
import numpy as np
import pandas as pd

from services import checklist, extension, news


def _df(close):
    close = np.asarray(close, dtype=float)
    return pd.DataFrame({"close": close}, index=pd.bdate_range("2023-01-02", periods=len(close)))


def test_extension_extended_state():
    # flat base then a vertical run to ~+20% over the 50d MA
    close = np.concatenate([np.full(200, 100.0), np.linspace(100, 132, 30)])
    out = extension.analyze(_df(close))
    assert out["available"] and out["state"] in ("extended", "blowoff")
    assert out["ext_pct"] >= 15
    text = " ".join(out["notes"]).lower()
    assert "momentum" in text and "drawdown" in text  # both sides of the honest story


def test_extension_ma_touch_after_run():
    # run far above the MA, then drift back down to it
    close = np.concatenate([
        np.full(150, 100.0),
        np.linspace(100, 128, 25),     # the hot run
        np.linspace(128, 123, 60),     # bleed back to the rising MA
    ])
    out = extension.analyze(_df(close))
    assert out["available"]
    assert out["state"] == "ma_touch_after_run"
    assert any("re-entry" in n or "add" in n for n in out["notes"])


def test_extension_normal_quiet():
    close = 100 + np.cumsum(np.random.default_rng(0).normal(0, 0.1, 300))
    out = extension.analyze(_df(close))
    assert out["available"] and out["state"] == "normal"


def test_news_extracts_old_and_new_schema():
    old = {"title": "Chip stocks rally", "publisher": "Reuters", "link": "https://x",
           "providerPublishTime": 0}
    new = {"content": {"title": "Memory prices surge", "provider": {"displayName": "Bloomberg"},
                       "canonicalUrl": {"url": "https://y"}, "pubDate": "2026-06-10T12:00:00Z"}}
    out = news.headlines("MU", fetch_news=lambda t: [old, new, {"junk": 1}])
    assert out["available"] and len(out["items"]) == 2
    assert out["items"][0]["title"] == "Chip stocks rally"
    assert out["items"][1]["publisher"] == "Bloomberg"


def test_news_fetch_error_degrades():
    def boom(t): raise RuntimeError("net")
    assert news.headlines("MU", fetch_news=boom)["available"] is False


def test_checklist_composes_and_flags_downtrend():
    out = checklist.build(
        dip={"available": True, "active": True, "history": {}},
        resistance={"available": True, "uptrend": False},
        sector={"available": True, "event": "broad_selloff", "notes": ["sector note"]},
        ext={"available": True, "state": "extended", "notes": ["stretch note"]},
        earnings={"available": True, "days_to_earnings": 3, "hot_runup": True, "note": "hot"},
        pros={"available": True, "line": "Street consensus: Buy"},
        gap={"available": True, "gapped_today": True, "note": "gap note"},
        news={"available": True, "items": [{"title": "t"}]},
    )
    assert out["available"]
    names = [f["name"] for f in out["factors"]]
    assert "Long-term trend" in names and "Earnings risk" in names
    trend = next(f for f in out["factors"] if f["name"] == "Long-term trend")
    assert trend["status"] == "bad"
    earn = next(f for f in out["factors"] if f["name"] == "Earnings risk")
    assert earn["status"] == "bad"
    assert out["headlines"]


def test_checklist_empty_inputs():
    out = checklist.build()
    assert out["available"] is False
