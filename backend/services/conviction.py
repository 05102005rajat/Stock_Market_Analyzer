"""Conviction Stack — the 'best combo', built only from signals that survive
rigorous evidence, NOT a pile of chart indicators.

The hard lesson from the research: stacking weak chart signals (MACD + RSI +
crossover + Bollinger) makes the data-snooping problem WORSE — they're all the
same price line wearing different hats, so they agree for the wrong reasons. The
combo that actually has evidence pairs signals from INDEPENDENT sources, each
with its own economic mechanism:

  * Momentum / relative strength   — STRONG   (Jegadeesh-Titman 1993; replicated
                                     across 40+ markets) — winners keep winning.
  * Trend stage (Minervini)        — MODERATE — a momentum/trend confirmation.
  * Opportunistic insider buying   — STRONG   (Cohen-Malloy-Pomorski 2012:
                                     ~82 bps/month) — informed cash going in.
  * Earnings posture               — the "priced-in" CAUTION (see below).

For CONTRAST, the EMA/MACD chart crossover is shown but tagged WEAK and given
ZERO weight — so you can literally see the evidence gap on screen.

────────────────────────────────────────────────────────────────────────────
THE EARNINGS RUN-UP PATTERN (user's observation: Broadcom / Palo Alto, and
other companies in the SAME sector, ran up into earnings then dropped RIGHT
BEFORE/ON the print — whether the eventual result was good OR bad). This is
REAL but it is a CAUTION, not a buy: the run-up itself prices the good news in,
so "sell the news" hits even on a beat (the Micron setup). We CANNOT honestly
turn it into "buy the run-up then sell before the dump" — that requires timing
the exit before a binary event that frequently gaps overnight, and the
memorable winners are survivorship bias. So the stack treats a hot pre-earnings
run-up as a RISK flag that LOWERS conviction.

Like every signal here, the stack's verdict is logged to the Signal Ledger and
scored forward vs SPY — trust the scoreboard, not the label.
"""
from __future__ import annotations

# evidence-strength weights (weak chart signals contribute ZERO on purpose)
_W = {"strong": 2, "moderate": 1, "weak": 0}

EVIDENCE = {
    "principle": (
        "Built from INDEPENDENT, evidence-backed signals (momentum, insider "
        "buying, trend) — not a stack of chart indicators that all derive from "
        "the same price line. Combining independent signals is the only 'combo' "
        "with real academic support; combining correlated chart signals just "
        "overfits."
    ),
    "sources": (
        "Momentum: Jegadeesh-Titman 1993. Insider buying: Cohen-Malloy-Pomorski "
        "2012 (~82 bps/mo for opportunistic trades). These have replicated "
        "out-of-sample; chart-pattern/MACD/RSI signals largely have not."
    ),
    "caveat": (
        "Evidence-backed does not mean certain. Momentum suffers violent "
        "crashes; published edges decay (McLean-Pontiff 2016). The stack is "
        "logged to the ledger and scored forward — read its real accuracy there."
    ),
}


def _add(comps, name, strength, state, detail):
    comps.append({
        "name": name,
        "strength": strength,          # strong | moderate | weak
        "state": state,                # bullish | bearish | caution | neutral
        "detail": detail,
        "weight": _W[strength],
    })


def assess(ctx: dict) -> dict:
    """Aggregate the evidence-backed signals already computed in /api/analyze.

    ctx keys used (all optional / handled defensively):
      relativeStrength, minervini, insider, earningsWatch, crossover
    """
    rs = ctx.get("relativeStrength") or {}
    mino = ctx.get("minervini") or {}
    ins = ctx.get("insider") or {}
    earn = ctx.get("earningsWatch") or {}
    cross = ctx.get("crossover") or {}

    comps: list[dict] = []

    # 1) MOMENTUM / RELATIVE STRENGTH — STRONG ------------------------------
    if rs:
        out = rs.get("outperforming")
        ex = rs.get("excess_pct")
        lb = rs.get("lookback", "")
        if out is True:
            _add(comps, "Momentum (relative strength)", "strong", "bullish",
                 f"Outperforming SPY by {ex:+.1f}% over {lb} — winners tend to persist.")
        elif out is False:
            _add(comps, "Momentum (relative strength)", "strong", "bearish",
                 f"Lagging SPY by {ex:+.1f}% over {lb} — relative weakness tends to persist.")

    # 2) TREND STAGE (Minervini) — MODERATE ---------------------------------
    if mino.get("available"):
        passed = mino.get("passed")
        stage = mino.get("stage")
        sc = mino.get("score")
        if passed:
            _add(comps, "Trend stage (Minervini)", "moderate", "bullish",
                 f"Passes the Stage-2 uptrend template ({sc}) — confirms the momentum.")
        elif stage and "2" not in str(stage):
            _add(comps, "Trend stage (Minervini)", "moderate", "bearish",
                 f"Not in a Stage-2 uptrend (stage: {stage}).")

    # 3) OPPORTUNISTIC INSIDER BUYING — STRONG ------------------------------
    if ins.get("available"):
        if ins.get("cluster_buy") or ins.get("buying"):
            val = ins.get("buy_value")
            npl = ins.get("buy_people")
            extra = f"{npl} insiders, ${val:,.0f}" if (npl and val) else "open-market buying"
            tag = "cluster of insiders" if ins.get("cluster_buy") else "insider"
            _add(comps, "Insider buying (Form 4)", "strong", "bullish",
                 f"Recent open-market {tag} buying ({extra}) — informed cash going in.")
        elif ins.get("selling"):
            # selling is a WEAK signal (often routine/diversification) — note, don't over-weight
            _add(comps, "Insider activity (Form 4)", "weak", "neutral",
                 "Recent insider selling — usually routine/diversification; weak signal.")

    # 4) EARNINGS POSTURE — the priced-in CAUTION (user's run-up pattern) ----
    if earn.get("available"):
        dte = earn.get("days_to_earnings")
        if earn.get("hot_runup"):
            when = f"in ~{dte} days" if dte is not None else "soon"
            _add(comps, "Earnings run-up (priced-in risk)", "moderate", "caution",
                 f"Has run up hot into earnings ({when}). This pattern has shown up "
                 f"across nearby companies in the same sector: the stock climbs into "
                 f"the print, then drops right BEFORE/ON earnings — regardless of "
                 f"whether the eventual result is good or bad, because the run-up "
                 f"already priced the good news in. A risk flag, not a buy.")

    # 5) CHART CROSSOVER — WEAK, shown for CONTRAST (zero weight) ------------
    if cross.get("available") and cross.get("state") in ("buy", "sell"):
        st = "bullish" if cross["state"] == "buy" else "bearish"
        _add(comps, "EMA/MACD crossover (chart)", "weak", st,
             "Trend-following chart signal — near-zero predictive edge after costs; "
             "shown for comparison only, not counted toward conviction.")

    # --- aggregate (only strong + moderate count; weak = 0) ----------------
    bull = sum(c["weight"] for c in comps if c["state"] == "bullish")
    bear = sum(c["weight"] for c in comps if c["state"] == "bearish")
    cautions = [c for c in comps if c["state"] == "caution"]
    caution_pts = sum(c["weight"] for c in cautions)
    net = bull - bear - caution_pts

    # how many INDEPENDENT evidence-backed bullish signals align
    aligned = sum(1 for c in comps
                  if c["state"] == "bullish" and c["strength"] in ("strong", "moderate"))
    strong_bull = sum(1 for c in comps
                      if c["state"] == "bullish" and c["strength"] == "strong")

    if aligned >= 2 and strong_bull >= 1 and bear == 0:
        verdict, direction = "high_bull", "up"
        headline = f"Higher conviction — {aligned} independent evidence-backed signals align bullish"
    elif net <= -2:
        verdict, direction = "bear", "down"
        headline = "Evidence-backed signals lean bearish"
    elif bull == 0 and bear == 0:
        verdict, direction = "none", None
        headline = "No evidence-backed signals firing right now"
    else:
        verdict, direction = "mixed", None
        headline = "Mixed — evidence-backed signals don't agree"

    if cautions and direction == "up":
        headline += " — but watch the earnings run-up caution"

    return {
        "available": bool(comps),
        "verdict": verdict,        # high_bull | bear | mixed | none
        "direction": direction,    # up | down | None  (for the ledger)
        "headline": headline,
        "aligned_bullish": aligned,
        "net_score": net,
        "components": comps,
        "evidence": EVIDENCE,
        "note": (
            "Only momentum, insider buying, and trend are counted (Strong/Moderate "
            "evidence). The chart crossover is shown but weighted zero. A hot "
            "pre-earnings run-up lowers conviction (priced-in risk)."
        ),
    }
