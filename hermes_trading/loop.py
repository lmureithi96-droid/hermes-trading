"""Reliable async trading loop with retries and circuit breaker."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from hermes_trading.adapters.price import fetch_price
from hermes_trading.adapters.onchain import fetch_onchain
from hermes_trading.adapters.news import fetch_news
from hermes_trading.adapters.macro import fetch_macro
from hermes_trading.score import score


CIRCUIT_BREAK_THRESHOLD = 5
ADAPTER_RETRIES = 3
ADAPTER_RETRY_BACKOFF = 1.5  # seconds, exponential


async def _fetch_with_retry(fetch_fn, **kwargs):
    failures = 0
    last_exc = None
    for attempt in range(1, ADAPTER_RETRIES + 1):
        try:
            return await fetch_fn(**kwargs)
        except Exception as exc:
            last_exc = exc
            failures += 1
            await asyncio.sleep(ADAPTER_RETRY_BACKOFF ** attempt)
    raise last_exc  # type: ignore[misc]


class CircuitOpen(Exception):
    pass


class AdapterCircuitBreaker:
    def __init__(self, threshold: int = CIRCUIT_BREAK_THRESHOLD):
        self.threshold = threshold
        self.failures = 0
        self.last_failure_ts: float | None = None

    def record_failure(self):
        self.failures += 1
        self.last_failure_ts = time.time()

    def record_success(self):
        self.failures = 0
        self.last_failure_ts = None

    def guard(self, name: str):
        if self.failures >= self.threshold:
            raise CircuitOpen(f"Adapter circuit open for {name}")
        return True


async def run_loop(goal_path: Path, asset_override: str | None = None):
    state_dir = goal_path.parent
    trades_path = state_dir / "trades.jsonl"
    heartbeat_path = state_dir / "heartbeat.json"
    strategy_path = state_dir / "strategy.yaml"

    # naive goal load without extra dep
    import yaml

    goal = yaml.safe_load(goal_path.read_text())
    assets = [asset_override] if asset_override else [a.strip() for a in goal["asset"].split(",") if a.strip()]

    breakers = {
        "price": AdapterCircuitBreaker(),
        "onchain": AdapterCircuitBreaker(),
        "news": AdapterCircuitBreaker(),
        "macro": AdapterCircuitBreaker(),
    }

    # Track active entry signals per asset for next bar
    active_long_signals: dict[str, bool] = {a: False for a in assets}

    while True:
        start_ts = time.time()
        market_snapshot = {}

        # Fetch adapters independently; abort loop if any circuit opens
        for name, fetch_fn in {
            "price": fetch_price,
            "onchain": fetch_onchain,
            "news": fetch_news,
            "macro": fetch_macro,
        }.items():
            cb = breakers[name]
            try:
                cb.guard(name)
                data = await _fetch_with_retry(fetch_fn, assets=assets)
                cb.record_success()
                market_snapshot[name] = data
            except CircuitOpen as exc:
                # Hard halt on circuit open — force manual / auto restart
                raise SystemExit(f"Circuit break: {exc}")
            except Exception as exc:
                cb.record_failure()
                raise SystemExit(f"Adapter failure {name}: {exc}")

        # Simple deterministic strategy: RSI < threshold for any asset → paper long
        # Evaluate per asset and log trade idea
        for asset in assets:
            price_data = market_snapshot.get("price", {})
            rsi = None
            if isinstance(price_data, dict):
                rsi = (((price_data.get(asset) or {}).get("indicators") or {}).get("rsi"))

            # If we have RSI and below threshold, mark signal active and enter if not already entered
            if isinstance(rsi, (int, float)):
                indicator_threshold = 30.0
                if rsi < indicator_threshold:
                    active_long_signals[asset] = True
                else:
                    active_long_signals[asset] = False

            # Paper entry logic
            trade_record = None
            if active_long_signals.get(asset):
                trade_record = {
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "asset": asset,
                    "side": "long",
                    "entry_price": (((price_data.get(asset) or {}).get("price"))),
                    "status": "open",
                    "strategy_version": strategy_path.read_text() if strategy_path.exists() else "unknown",
                }
                # Only log if not already open (dedupe by simple in-memory per asset; persistent state would be better)
                # For brevity we always append; downstream reflection can dedupe by asset+open
                trades_path.parent.mkdir(parents=True, exist_ok=True)
                with trades_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(trade_record) + "\n")

        heartbeat = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "assets": assets,
            "ok": True,
            "price_ok": "price" in market_snapshot,
            "onchain_ok": "onchain" in market_snapshot,
            "news_ok": "news" in market_snapshot,
            "macro_ok": "macro" in market_snapshot,
        }
        heartbeat_path.write_text(json.dumps(heartbeat, indent=2), encoding="utf-8")

        # Keep loop cadence ~1 minute
        elapsed = time.time() - start_ts
        sleep_s = max(0.0, 60.0 - elapsed)
        if sleep_s:
            await asyncio.sleep(sleep_s)
