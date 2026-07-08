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
    "has_single_dynamic_profile_table": 'self.profile_tree = self._tree' in text and '("app_id", "display", "hotkeys", "mode", "action")' in text,
    "no_second_profile_editor_tree": "profile_editor_tree" not in text,
    "has_selected_row_editor": "Selected Row Editor" in text,
    "has_update_selected_row": "Update Selected Row" in text,
    "has_right_click_row_actions": "Set Row Hotkeys ON" in text and "Set Row Action" in text,
    "has_no_legacy_launch_checkbox_text": "Legacy launch checkbox" not in text,
    "has_no_compact_g502_soundcard_only_controls": "G502V Hotkeys:" not in text and "Soundcard Hotkeys:" not in text,
    "required_methods_exist": all(name in methods for name in [
        "profile_row_selected",
        "selected_profile_row_app_id",
        "set_selected_profile_row_hotkeys",
        "set_selected_profile_row_action",
        "apply_profile_editor_row",
        "set_profile_editor_all_keep",
        "refresh_profile_tree",
    ]),
}

report = {
    "tool": "sbc_profile_streamlined_editor_check",
    "checks": checks,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
