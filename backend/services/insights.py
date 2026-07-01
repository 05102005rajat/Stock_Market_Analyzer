"""Situation-aware recommendation engine.

Takes the full technical picture (trend, multi-timeframe regime, momentum,
support/resistance, candlesticks, chart patterns, volume, Minervini stage) and
produces a plain-English read of the situation plus a prioritized list of what
to watch — tailored to whether the stock is going up, down, or chopping.

Transparent, rule-based, and explicitly NOT investment advice.
"""
from __future__ import annotations

DISCLAIMER = "Rule-based technical observations for education only — not investment advice."


def _nearest(levels: list[float], price: float, above: bool):
    """Nearest level strictly above (resistance) or below (support) price."""
    cands = [l for l in levels if (l > price if above else l < price)]
    if not cands:
        return None
    return min(cands) if above else max(cands)


def _pct(a: float, b: float) -> float:
    return (a / b - 1.0) * 100 if b else 0.0


def generate(ctx: dict) -> dict:
    """Build {situation, bias, recommendations[], watch[], disclaimer}."""
    trend = ctx.get("trend") or {}
    mtf = ctx.get("multiTimeframe") or {}
    regime = mtf.get("regime") or {}
    latest = ctx.get("latest") or {}
    levels = ctx.get("levels") or {}
    candles = ctx.get("candlesticks") or []
    chart_patterns = ctx.get("patterns") or []
    volume = ctx.get("volume") or {}
    minervini = ctx.get("minervini") or {}
    ticker = ctx.get("ticker", "This stock")

    price = latest.get("close")
    rsi = latest.get("rsi")
    macd = latest.get("macd")
    macd_signal = latest.get("macd_signal")
    sma50 = latest.get("sma50")

    resistance = levels.get("resistance") or []
    support = levels.get("support") or []
    near_res = _nearest(resistance, price, above=True) if price else None
    near_sup = _nearest(support, price, above=False) if price else None

    alignment = mtf.get("alignment", "")
    cross = regime.get("cross")
    above_200 = regime.get("above_sma200")
    mino_stage = minervini.get("stage", "") if minervini.get("available") else ""
    mino_passes = bool(minervini.get("passes"))

    overbought = rsi is not None and rsi > 70
    oversold = rsi is not None and rsi < 30
    macd_bull = macd is not None and macd_signal is not None and macd > macd_signal

    latest_candle = candles[0] if candles else None
    lc_time = latest_candle.get("time") if latest_candle else None
    vol_signals = volume.get("signals") or []
    recent_breakout = next((s for s in vol_signals if s["name"] == "Breakout on Volume"), None)
    recent_breakdown = next((s for s in vol_signals if s["name"] == "Breakdown on Volume"), None)
    recent_dryup = next((s for s in vol_signals if s["name"] == "Volume Dry-Up"), None)

    near_res_pct = _pct(near_res, price) if (near_res and price) else None
    near_sup_pct = _pct(near_sup, price) if (near_sup and price) else None
    near_resistance = near_res_pct is not None and near_res_pct <= 3.0
    near_support = near_sup_pct is not None and near_sup_pct >= -3.0

    # --- Overall directional bias from weighted evidence ---
    bull, bear = 0, 0
    if above_200 is True:
        bull += 1
    elif above_200 is False:
        bear += 1
    if cross == "golden":
        bull += 1
    elif cross == "death":
        bear += 1
    if "up" in alignment.lower():
        bull += 1
    elif "down" in alignment.lower() or "bearish" in alignment.lower():
        bear += 1
    if macd is not None and macd_signal is not None:  # don't vote on absent data
        bull += 1 if macd_bull else 0
        bear += 0 if macd_bull else 1
    if "Stage 2" in mino_stage:
        bull += 2
    elif "Stage 4" in mino_stage:
        bear += 2
    if latest_candle:
        if latest_candle["bias"] == "bullish":
            bull += 1
        elif latest_candle["bias"] == "bearish":
            bear += 1

    bias = "bullish" if bull > bear else "bearish" if bear > bull else "neutral"

    recs: list[dict] = []

    def _anchor(times=None, levels=None):
        """Build a chart-anchor (bar times + price levels) dropping any Nones."""
        t = [x for x in (times or []) if x is not None]
        l = [x for x in (levels or []) if x is not None]
        if not t and not l:
            return None
        return {"times": t, "levels": l}

    def rec(title, detail, b, priority, anchor=None):
        item = {"title": title, "detail": detail, "bias": b, "priority": priority}
        if anchor:
            item["anchor"] = anchor
        recs.append(item)

    # ---------------- Situation summary ----------------
    regime_txt = (
        "above its 200-day average" if above_200 else
        "below its 200-day average" if above_200 is False else
        "in early territory (limited history)"
    )
    rsi_txt = f"{rsi:.0f}" if rsi is not None else "—"
    momentum_txt = (
        f"overbought (RSI {rsi_txt})" if overbought else
        f"oversold (RSI {rsi_txt})" if oversold else
        f"neutral (RSI {rsi_txt})" if rsi is not None else "unmeasured"
    )
    pos_txt = ""
    if near_res and near_resistance:
        pos_txt = f" and pressing against resistance near {near_res} ({near_res_pct:+.1f}%)"
    elif near_sup and near_support:
        pos_txt = f" and sitting just above support near {near_sup} ({near_sup_pct:+.1f}%)"
    stage_txt = f"{mino_stage}. " if mino_stage else ""
    situation = (
        f"{ticker} is {regime_txt}, {alignment.lower() or 'trend unclear'}{pos_txt}. "
        f"{stage_txt}Momentum is {momentum_txt}."
    )

    # ---------------- Rules (situational) ----------------
    if mino_passes:
        rec("Textbook Stage 2 uptrend",
            f"Passes all 8 of Minervini's Trend Template criteria — among the strongest "
            f"technical profiles. Classic entries are pullbacks toward the 50-day MA"
            + (f" (~{sma50})" if sma50 else "") + ".", "bullish", 1,
            _anchor(levels=[sma50]))

    if bias == "bullish" and not overbought and near_support and latest_candle and latest_candle["bias"] == "bullish":
        rec("Trend-continuation setup at support",
            f"A bullish {latest_candle['name']} near support {near_sup} within an uptrend — "
            f"watch for follow-through; a close back above the recent swing high confirms.",
            "bullish", 1, _anchor(times=[lc_time], levels=[near_sup]))

    if bias == "bullish" and near_resistance and recent_dryup:
        rec("Breakout watch — coiling below resistance",
            f"Price is coiling below resistance {near_res} with volume drying up. "
            f"A high-volume close above {near_res} would be the breakout trigger.",
            "bullish", 1, _anchor(times=[recent_dryup.get("time")], levels=[near_res]))

    if recent_breakout:
        rec("Breakout confirmed by volume",
            f"New high on heavy volume ({recent_breakout['date']}). Momentum favors "
            f"continuation; former resistance often flips to support on a retest.",
            "bullish", 1, _anchor(times=[recent_breakout.get("time")]))

    if bias == "bullish" and overbought:
        rec("Extended — avoid chasing",
            f"RSI {rsi_txt} is overbought inside an uptrend. Prefer waiting for a pullback toward "
            f"the 50-day MA{f' (~{sma50})' if sma50 else ''} or a reversal candle rather than buying strength.",
            "neutral", 2, _anchor(levels=[sma50]))

    if bias == "bullish" and near_resistance and latest_candle and latest_candle["bias"] == "bearish":
        rec("Caution — bearish candle at resistance",
            f"A bearish {latest_candle['name']} at resistance {near_res} can spark a short-term "
            f"pullback. Watch {near_sup if near_sup else 'the prior support'} as the next floor.",
            "bearish", 2, _anchor(times=[lc_time], levels=[near_res, near_sup]))

    if bias == "bearish" and (cross == "death" or above_200 is False):
        rec("Downtrend regime — rallies tend to fade",
            f"Price is below the 200-day MA{' with a death cross' if cross == 'death' else ''}. "
            f"Bounces toward {near_res if near_res else 'overhead resistance'} often fail; "
            f"avoid bottom-fishing until a proper base forms.", "bearish", 1,
            _anchor(levels=[near_res]))

    if bias == "bearish" and oversold and latest_candle and latest_candle["bias"] == "bullish":
        rec("Possible oversold bounce (counter-trend)",
            f"RSI {rsi_txt} with a bullish {latest_candle['name']} can fuel a bounce toward "
            f"{near_res if near_res else 'resistance'} — but the larger trend is still down, "
            f"so treat it as a trade, not a turn.", "neutral", 2,
            _anchor(times=[lc_time], levels=[near_res]))

    if recent_breakdown:
        rec("Breakdown confirmed by volume",
            f"New low on heavy volume ({recent_breakdown['date']}) — sellers in control; "
            f"former support often flips to resistance.", "bearish", 1,
            _anchor(times=[recent_breakdown.get("time")]))

    if "Mixed" in alignment or "choppy" in alignment.lower():
        rec("Choppy — trade the range, not the trend",
            f"Timeframes disagree. Lower conviction; the range between "
            f"{near_sup if near_sup else 'support'} and {near_res if near_res else 'resistance'} "
            f"is more reliable than a directional bet.", "neutral", 2,
            _anchor(levels=[near_sup, near_res]))

    # Momentum footnote if nothing else covered MACD.
    if macd is not None and macd_signal is not None:
        rec("Momentum (MACD)",
            f"MACD is {'above' if macd_bull else 'below'} its signal line — "
            f"{'bullish' if macd_bull else 'bearish'} short-term momentum.",
            "bullish" if macd_bull else "bearish", 3)

    # ---------------- What to watch (direction-aware) ----------------
    watch: list[str] = []
    if near_res:
        watch.append(f"Resistance to clear: {near_res}" + (f" ({near_res_pct:+.1f}%)" if near_res_pct is not None else ""))
    if near_sup:
        watch.append(f"Support to hold: {near_sup}" + (f" ({near_sup_pct:+.1f}%)" if near_sup_pct is not None else ""))
    if bias == "bullish":
        watch.append("In this uptrend: bullish continuation candles (hammer, bullish engulfing) at support are buy signals; bearish reversal candles (shooting star, bearish engulfing) at resistance warn of pullbacks.")
    elif bias == "bearish":
        watch.append("In this downtrend: bearish continuation candles at resistance confirm weakness; only a bullish reversal candle on heavy volume at support hints at a turn.")
    else:
        watch.append("While choppy: watch for a decisive, high-volume close beyond the range to define the next trend.")
    watch.append("Confirmation rule of thumb: a breakout/breakdown matters more when volume is above its 50-day average.")

    recs.sort(key=lambda r: r["priority"])
    return {
        "situation": situation,
        "bias": bias,
        "recommendations": recs[:6],
        "watch": watch,
        "disclaimer": DISCLAIMER,
    }
