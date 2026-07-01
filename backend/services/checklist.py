"""Buy checklist — composes every engine into ONE multi-factor read.

Answers the complaint "the buy zone keeps showing the same thing": instead of
'price dropped -> buy', each factor gets a status with its own measured
evidence, and the user sees the WHOLE situation:

  trend / dip signal / sector attribution / extension / earnings proximity /
  analyst stance / today's gap / recent headlines (the catalyst).

No composite score on purpose: the project's own walk-forward study showed
score-blending added no edge, so this stays a transparent checklist a human
reads, not a number a human obeys.
"""
from __future__ import annotations

GOOD, WARN, BAD, INFO = "good", "warn", "bad", "info"


def _factor(name, status, line):
    return {"name": name, "status": status, "line": line}


def build(*, dip=None, resistance=None, sector=None, ext=None,
          earnings=None, pros=None, gap=None, news=None) -> dict:
    f: list[dict] = []

    # Trend (from resistance engine's 200d filter)
    if resistance and resistance.get("available") and resistance.get("uptrend") is not None:
        up = resistance["uptrend"]
        f.append(_factor(
            "Long-term trend", GOOD if up else BAD,
            "Above its 200d average — dip-buying and breakout odds both measured better in uptrends."
            if up else
            "BELOW its 200d average — every measured edge in this app weakened below the 200d. "
            "Buying falling knives in downtrends is where the dip stats die.",
        ))

    # Dip signal
    if dip and dip.get("available"):
        active = dip.get("active")
        hist = dip.get("history") or {}
        line = None
        if active:
            line = "Oversold dip in an uptrend — the one entry pattern this project's own backtests validated."
        else:
            line = "No validated dip entry active right now."
        f.append(_factor("Dip signal (RSI2)", GOOD if active else INFO, line))

    # Sector attribution
    if sector and sector.get("available"):
        ev = sector.get("event")
        notes = sector.get("notes") or []
        if ev == "broad_selloff":
            f.append(_factor("Sector context", WARN, notes[0] if notes else
                             "Sector-wide selloff today — group event, already priced same-day historically."))
        elif notes:
            f.append(_factor("Sector context", INFO, notes[0]))

    # Extension / rubber band
    if ext and ext.get("available") and ext.get("state") != "normal":
        st = ext["state"]
        status = WARN if st in ("extended", "blowoff", "stretched_below") else GOOD
        f.append(_factor("Stretch vs 50d MA", status, (ext.get("notes") or [""])[0]))

    # Earnings proximity
    if earnings and earnings.get("available") and earnings.get("days_to_earnings") is not None:
        d = earnings["days_to_earnings"]
        if d <= 7:
            status = BAD if earnings.get("hot_runup") else WARN
            f.append(_factor("Earnings risk", status,
                             earnings.get("note") or f"Earnings in {d} days — event risk on the position."))

    # Street stance
    if pros and pros.get("available"):
        f.append(_factor("Street consensus", INFO, pros["line"]))

    # Today's gap
    if gap and gap.get("available") and gap.get("gapped_today"):
        f.append(_factor("Opening gap", INFO,
                         (gap.get("note") or "Gapped at the open — fills are worst in the first 15 minutes.")))

    # Catalyst headlines
    items = (news or {}).get("items") or []

    return {
        "available": bool(f),
        "factors": f,
        "headlines": items,
        "caveat": (
            "A checklist to read, not a score to obey — blending these into one number added no edge "
            "in this project's own walk-forward tests."
        ),
    }
