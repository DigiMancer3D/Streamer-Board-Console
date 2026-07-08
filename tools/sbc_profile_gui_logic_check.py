#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
source = APP_ROOT / "streamer_board_console.py"
text = source.read_text(encoding="utf-8", errors="ignore")
tree = ast.parse(text)

def get_method(name: str):
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "StreamerBoardConsole":
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name == name:
                    return child
    return None

def method_calls(method, attr_name: str) -> bool:
    if method is None:
        return False
    for node in ast.walk(method):
        if isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr == attr_name:
                return True
    return False

required = [
    "apply_named_profile",
    "apply_selected_profile",
    "profile_changed",
    "load_selected_profile_into_editor",
    "save_profile_from_editor",
    "delete_selected_custom_profile",
]
methods = {name: get_method(name) for name in required}

checks = {
    "all_required_methods_exist": all(methods.values()),
    "apply_named_calls_profile_changed": method_calls(methods["apply_named_profile"], "profile_changed"),
    "apply_selected_calls_profile_changed": method_calls(methods["apply_selected_profile"], "profile_changed"),
    "save_profile_from_editor_present": methods["save_profile_from_editor"] is not None,
    "custom_editor_vars_present": all(s in text for s in [
        "profile_edit_name_var",
        "profile_edit_desc_var",
        "profile_editor_state",
        "profile_editor_hotkeys_var",
        "profile_editor_action_var",
    ]),
    "custom_editor_buttons_present": all(s in text for s in [
        "Load Selected Into Editor",
        "Save / Update Profile",
        "Delete Custom Profile",
        "Update Selected Row",
    ]),
}

report = {
    "tool": "sbc_profile_gui_logic_check",
    "source": str(source),
    "checks": checks,
    "passed": all(checks.values()),
}

print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
