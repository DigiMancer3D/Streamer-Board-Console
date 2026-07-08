#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
source = APP_ROOT / "streamer_board_console.py"
text = source.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(text)

methods = set()
for node in tree.body:
    if isinstance(node, ast.ClassDef) and node.name == "StreamerBoardConsole":
        for child in node.body:
            if isinstance(child, ast.FunctionDef):
                methods.add(child.name)

checks = {
    "has_force_window_visible": "force_window_visible" in methods,
    "has_shutdown": "shutdown" in methods,
    "uses_safe_geometry": "SBC_WINDOW_GEOMETRY" in text,
    "uses_topmost_rescue": 'attributes("-topmost", True)' in text,
    "monitor_catches_keyboard_interrupt": "except KeyboardInterrupt" in text,
}

report = {
    "tool": "sbc_window_rescue_check",
    "source": str(source),
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
