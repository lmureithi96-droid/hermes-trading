"""News sentiment adapter stub with deterministic fallback data."""
from __future__ import annotations

from typing import Any


class SchemaError(Exception):
    pass


async def fetch(assets: list[str]) -> dict[str, Any]:
    schema_version = "news-v1"
    result: dict[str, Any] = {"schema_version": schema_version}
    for asset in assets:
        result[asset] = {
            "schema_version": schema_version,
            "sentiment_score": 0.0,
            "headlines": [],
        }
    return result


async def fetch_news(assets: list[str]) -> dict[str, Any]:
    return await fetch(assets)
