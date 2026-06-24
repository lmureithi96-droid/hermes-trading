#!/usr/bin/env python3
"""Local trading agent web UI. Displays goal, strategy, trades, hypotheses, and history."""

from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any

import yaml

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except Exception:
    uvicorn = None  # type: ignore[assignment]
    FastAPI = None  # type: ignore[assignment]

BASE_DIR = Path(__file__).resolve().parent.parent / "state"


def _read(path: Path, fallback=None):
    if not path.exists():
        return fallback
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return path.read_text(encoding="utf-8")


def _read_trades(limit: int = 100):
    path = BASE_DIR / "trades.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:]


def _read_hypotheses(limit: int = 50):
    path = BASE_DIR / "hypotheses.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:]


def _history_files():
    hdir = BASE_DIR / "history"
    if not hdir.exists():
        return []
    return sorted([p.name for p in hdir.iterdir() if p.is_file()])[-20:]


def build_html() -> str:
    goal = _read(BASE_DIR / "goal.yaml", {}) or {}
    strategy = _read(BASE_DIR / "strategy.yaml", {}) or {}
    trades = _read_trades()
    hypotheses = _read_hypotheses()
    history = _history_files()

    def rows_for_trades(items):
        return "".join(
            f"<tr><td>{item.get('ts','')}</td><td>{item.get('asset','')}</td><td>{item.get('side','')}</td>"
            f"<td>{item.get('entry_price','')}</td><td>{item.get('status','')}</td><td>{item.get('strategy_version','')}</td></tr>"
            for item in items
        )

    def rows_for_hypotheses(items):
        return "".join(
            f"<tr><td>{item.get('ts','')}</td><td>{item.get('mode','')}</td>"
            f"<td>{item.get('variable','')}</td><td>{item.get('rationale','')}</td></tr>"
            for item in items
        )

    return f"""<!doctype html>
<html lang=en>
<meta charset=utf-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Hermes Trading</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto; margin: 24px; background:#0b0d10; color:#e7e9ea; }}
  .card {{ background:#101418; border:1px solid #1f2730; border-radius:12px; padding:16px; margin-bottom:16px; }}
  table {{ width:100%; border-collapse: collapse; }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid #1f2730; }}
  th {{ color:#8b98a8; font-weight:600; }}
  h1 {{ font-size:24px; margin:0 0 12px; }}
  h2 {{ font-size:18px; margin:0 0 8px; color:#c7ccd3; }}
</style>
<body>
<div class=card>
  <h1>Hermes Trading Agent</h1>
  <div>Status: <strong style="color:#b9f6c5">Running</strong></div>
  <div>Paper mode</div>
</div>
<div class=card>
  <h2>Strategy</h2>
  <div style="white-space: pre-wrap; color:#d3d6da;">{yaml.safe_dump(strategy)}</div>
</div>
<div class=card>
  <h2>Goal</h2>
  <div style="white-space: pre-wrap; color:#d3d6da;">{yaml.safe_dump(goal)}</div>
</div>
<div class=card>
  <h2>Recent Trades ({len(trades)})</h2>
  <table>
    <thead><tr><th>ts</th><th>asset</th><th>side</th><th>entry</th><th>status</th><th>strategy</th></tr></thead>
    <tbody>{rows_for_trades(trades)}</tbody>
  </table>
</div>
<div class=card>
  <h2>Hypotheses ({len(hypotheses)})</h2>
  <table>
    <thead><tr><th>ts</th><th>mode</th><th>variable</th><th>rationale</th></tr></thead>
    <tbody>{rows_for_hypotheses(hypotheses)}</tbody>
  </table>
</div>
<div class=card>
  <h2>History</h2>
  <div>{", ".join(history) if history else "None yet"}</div>
</div>
</body>
</html>
"""


def build_api() -> dict[str, Any]:
    return {
        "goal": _read(BASE_DIR / "goal.yaml", {}),
        "strategy": _read(BASE_DIR / "strategy.yaml", {}),
        "trades": _read_trades(),
        "hypotheses": _read_hypotheses(),
        "history": _history_files(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def main() -> int:
    try:
        import fastapi, uvicorn  # type: ignore[import-untyped]
    except Exception as exc:
        print(f"Web UI deps missing: {exc}")
        print("Run: pip install fastapi uvicorn")
        return 2

    app = FastAPI()

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/api/state", response_class=JSONResponse)
    def api_state():
        return build_api()

    uvicorn.run(app, host="0.0.0.0", port=8787)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
