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
    "has_streamlined_row_editor": "Selected Row Editor" in text,
    "has_update_selected_row_button": "Update Selected Row" in text,
    "has_set_all_keep_button": "Set All Actions Keep" in text,
    "single_table_carries_display_column": '("app_id", "display", "hotkeys", "mode", "action")' in text,
    "save_uses_profile_editor_state": "profile_editor_state" in text and "for app_id in self.apps.keys()" in text,
    "required_methods_exist": all(name in methods for name in [
        "load_profile_into_editor_state",
        "refresh_profile_tree",
        "profile_row_selected",
        "apply_profile_editor_row",
        "set_profile_editor_all_keep",
        "set_selected_profile_row_hotkeys",
        "set_selected_profile_row_action",
        "app_display_name",
    ]),
}
report = {
    "tool": "sbc_profile_dynamic_editor_check",
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
