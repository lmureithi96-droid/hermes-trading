"""Paper/live trading entrypoint."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from hermes_trading.loop import run_loop
from hermes_trading.score import score


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes trading worker")
    parser.add_argument("--asset", default=None, help="Override asset from goal.yaml")
    args = parser.parse_args()

    goal_path = Path(__file__).resolve().parent.parent / "state" / "goal.yaml"
    asyncio.run(run_loop(goal_path=goal_path, asset_override=args.asset))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
