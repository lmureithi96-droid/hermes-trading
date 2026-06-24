"""Score trades against goal in [-1, +1]."""
from __future__ import annotations

from typing import Any


def score(trades: list[dict[str, Any]], goal: dict[str, Any]) -> float:
    if not trades:
        return 0.0

    # realised return from first->last trade
    pnl = sum(float(t.get("pnl", 0.0)) for t in trades)
    target = float(goal.get("target_return_30d", 0.05))

    # max drawdown approximation from equity curve
    equity = [0.0]
    for t in trades:
        equity.append(equity[-1] + float(t.get("pnl", 0.0)))
    peak = equity[0]
    max_dd = 0.0
    for point in equity:
        if point > peak:
            peak = point
        dd = (peak - point) / (abs(peak) if peak != 0 else 1.0)
        if dd > max_dd:
            max_dd = dd
    max_drawdown_lim = float(goal.get("max_drawdown", 0.08))
    if max_drawdown_lim <= 0:
        max_drawdown_lim = 0.08
    dd_score = max(-1.0, 1.0 - (max_dd / max_drawdown_lim))
    dd_score = max(-1.0, min(1.0, dd_score))

    # Sharpe approximation: mean/std of per-trade pnl (annualised rough)
    import statistics
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    if len(pnls) < 2:
        sharpe_score = 0.0
    else:
        avg = statistics.mean(pnls)
        std = statistics.stdev(pnls)
        sharpe = (avg / std) if std > 0 else 0.0
        sharpe = sharpe * (len(pnls) ** 0.5)  # crude annualisation
        min_sharpe = float(goal.get("min_sharpe", 1.2))
        sharpe_score = max(-1.0, min(1.0, sharpe / min_sharpe)) if min_sharpe > 0 else 0.0

    ret_component = max(-1.0, min(1.0, pnl / target)) if target != 0 else 0.0
    composite = (ret_component + dd_score + sharpe_score) / 3.0
    return max(-1.0, min(1.0, composite))
