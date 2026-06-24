"""Reflection cycle: deterministic fallback or Hermes-driven hypothesis."""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from hermes_trading.score import score


HISTORY_DIR = Path(__file__).resolve().parent.parent / "state" / "history"
HYPOTHESES_PATH = Path(__file__).resolve().parent.parent / "state" / "hypotheses.jsonl"
STRATEGY_PATH = Path(__file__).resolve().parent.parent / "state" / "strategy.yaml"
TRADES_PATH = Path(__file__).resolve().parent.parent / "state" / "trades.jsonl"


def _load_trades(limit: int = 25) -> list[dict[str, Any]]:
    if not TRADES_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    with TRADES_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def _save_strategy(strategy: dict[str, Any]) -> str:
    STRATEGY_PATH.write_text(yaml.safe_dump(strategy, sort_keys=False), encoding="utf-8")
    return yaml.safe_dump(strategy, sort_keys=False)


def _record_hypothesis(hypothesis: dict[str, Any]):
    HYPOTHESES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HYPOTHESES_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(hypothesis) + "\n")


def _previous_version_name(strategy: dict[str, Any]) -> str:
    version = strategy.get("version", "01")
    padded = str(version).zfill(4)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return str(HISTORY_DIR / f"v{padded}.yaml")


def _bump_version(strategy: dict[str, Any]) -> str:
    try:
        version_int = int(str(strategy.get("version", "01")))
    except Exception:
        version_int = 1
    new_version = str(version_int + 1).zfill(2)
    strategy["version"] = new_version
    return new_version


def _fallback_reflection(strategy: dict[str, Any], trades: list[dict[str, Any]], goal: dict[str, Any]) -> dict[str, Any]:
    # Copy strategy and change exactly one variable
    updated = copy.deepcopy(strategy)
    _bump_version(updated)

    realised = sum(float(t.get("pnl", 0.0)) for t in trades)
    max_dd = _estimate_max_drawdown(trades)
    if realised < goal.get("target_return_30d", 0.05):
        updated["entry"]["threshold"] = round(float(updated["entry"].get("threshold", 30)) + 2, 4)
        variable = "entry.threshold"
        rationale = "Return below target; loosen entry threshold to increase trade frequency."
    elif max_dd > goal.get("max_drawdown", 0.08):
        updated["stop_loss_pct"] = round(float(updated.get("stop_loss_pct", 2.0)) - 0.2, 4)
        variable = "stop_loss_pct"
        rationale = "Drawdown exceeded limit; tighten stop-loss to reduce tail risk."
    else:
        updated["position_size_r"] = round(float(updated.get("position_size_r", 0.5)) + 0.05, 4)
        variable = "position_size_r"
        rationale = "Within bands; increase position size modestly to improve expected return."

    hypothesis = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "mode": "fallback",
        "variable": variable,
        "prior": strategy.get("version"),
        "next": updated.get("version"),
        "change": {
            "from": strategy.get(variable.split(".")[0], strategy),
            "to": updated.get(variable.split(".")[0], updated),
        },
        "rationale": rationale,
    }
    _record_hypothesis(hypothesis)
    return updated


def _estimate_max_drawdown(trades: list[dict[str, Any]]) -> float:
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
    return max_dd


def main() -> int:
    parser = argparse.ArgumentParser(description="Reflection cycle")
    parser.add_argument("--fallback", action="store_true", help="Use deterministic fallback rule")
    parser.add_argument("--hermes", action="store_true", help="Use Hermes subprocess mode")
    args = parser.parse_args()

    goal = yaml.safe_load(Path(__file__).resolve().parent.parent.joinpath("state", "goal.yaml").read_text())
    trades = _load_trades()
    if not STRATEGY_PATH.exists():
        raise SystemExit("strategy.yaml missing")

    strategy = yaml.safe_load(STRATEGY_PATH.read_text())
    prior_version_name = _previous_version_name(strategy)

    if args.fallback:
        updated = _fallback_reflection(strategy, trades, goal)
        print("Saved prior to:", prior_version_name)
        print("New strategy:\n" + yaml.safe_dump(updated, sort_keys=False))
        _save_strategy(updated)
        return 0

    if args.hermes:
        raise NotImplementedError("Hermes-driven reflection requires Hermes CLI wiring in Phase 7.")

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
