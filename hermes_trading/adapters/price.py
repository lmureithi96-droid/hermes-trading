"""Price adapter: OHLCV + basic indicators."""
from __future__ import annotations

from typing import Any


class SchemaError(Exception):
    pass


async def fetch(assets: list[str]) -> dict[str, Any]:
    import yfinance as yf  # lazy import

    schema_version = "price-v1"
    result: dict[str, Any] = {"schema_version": schema_version}

    for asset in assets:
        try:
            ticker = yf.Ticker(asset)
            hist = ticker.history(period="7d", interval="1h")
            prices = hist["Close"].dropna().tolist() if not hist.empty else []
            indicators: dict[str, Any] = {}
            if len(prices) >= 14:
                deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
                gains = [d if d > 0 else 0.0 for d in deltas[-14:]]
                losses = [-d if d < 0 else 0.0 for d in deltas[-14:]]
                avg_gain = sum(gains) / 14.0
                avg_loss = sum(losses) / 14.0
                rs = (avg_gain / avg_loss) if avg_loss > 0 else 100.0
                indicators["rsi"] = 100.0 - (100.0 / (1.0 + rs))
            last_price = prices[-1] if prices else None
            result[asset] = {"schema_version": schema_version, "price": last_price, "indicators": indicators}
        except Exception as exc:
            raise RuntimeError(f"price adapter failed for {asset}: {exc}") from exc
    return result
