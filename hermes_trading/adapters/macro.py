"""Macro adapter stub with deterministic fallback data."""
from __future__ import annotations

from typing import Any


class SchemaError(Exception):
    pass


async def fetch(assets: list[str]) -> dict[str, Any]:
    schema_version = "macro-v1"
    result: dict[str, Any] = {"schema_version": schema_version}
    for asset in assets:
        result[asset] = {
            "schema_version": schema_version,
            "volatility_index": 0.0,
            "rates_change_bps": 0.0,
        }
    return result


async def fetch_macro(assets: list[str]) -> dict[str, Any]:
    return await fetch(assets)
