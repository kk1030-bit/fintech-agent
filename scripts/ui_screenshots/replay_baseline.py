"""W01-A baseline replay server.

Serves the unchanged web_app (templates/dashboard.html, same bytes as Render on
2026-10-05) but replaces the two network-bound endpoints with the responses
recorded from Render in design/baseline-w01/render-probe-2026-10-05.json, so
screenshots can be taken at exact 1440x900 / 390x844 without touching FinMind
or the production Supabase. Nothing here is used in production.

    python scripts/ui_screenshots/replay_baseline.py  # http://127.0.0.1:5051
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from flask import jsonify, request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from web_app import app  # noqa: E402


def recorded_stocks():  # Render 2026-10-05: 500 text/html
    return "<!doctype html><title>500 Internal Server Error</title><h1>Internal Server Error</h1>", 500


def recorded_analyze():
    code = str((request.get_json(silent=True) or {}).get("stock_code") or "").strip()
    if not code:
        return jsonify({"ok": False, "error": "請輸入股票代號。"}), 400
    if not code.isdigit():
        return jsonify({"ok": False, "error": "目前網站版先支援台股數字代號，例如 2330、2317、2454。"}), 400
    time.sleep(60)  # real analysis not replayed: keep the loading state on screen
    return jsonify({"ok": False, "error": "REPLAY：未重播真實分析（會寫入正式 Supabase）"}), 400


app.view_functions["known_stocks"] = recorded_stocks
app.view_functions["analyze_stock"] = recorded_analyze

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5051, threaded=True)
