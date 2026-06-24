"""On-chain adapter stub with deterministic fallback data."""
from __future__ import annotations

from typing import Any


class SchemaError(Exception):
    pass


async def fetch(assets: list[str]) -> dict[str, Any]:
    schema_version = "onchain-v1"
    result: dict[str, Any] = {"schema_version": schema_version}
    for asset in assets:
        result[asset] = {
            "schema_version": schema_version,
            "active_addresses": 0,
            "exchange_inflow": 0.0,
            "exchange_outflow": 0.0,
        }
    return result


async def fetch_onchain(assets: list[str]) -> dict[str, Any]:
    return await fetch(assets)
