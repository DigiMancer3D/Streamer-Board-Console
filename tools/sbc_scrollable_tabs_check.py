#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "streamer_board_console.py"
text = source.read_text(encoding="utf-8")
tree = ast.parse(text)
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "StreamerBoardConsole")
methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}

checks = {
    "has_scrollable_content_method": "_scrollable_content" in methods,
    "apps_tab_uses_scrollable_content": "apps_parent = self._scrollable_content(self.apps_tab)" in text,
    "profiles_tab_uses_scrollable_content": "profiles_parent = self._scrollable_content(self.profiles_tab)" in text,
    "uses_vertical_scrollbar": 'ttk.Scrollbar(container, orient="vertical"' in text,
    "mousewheel_bound": "<MouseWheel>" in text and "<Button-4>" in text and "<Button-5>" in text,
}
passed = all(checks.values())
print(json.dumps({"tool": "sbc_scrollable_tabs_check", "checks": checks, "passed": passed}, indent=2, sort_keys=True))
raise SystemExit(0 if passed else 1)
