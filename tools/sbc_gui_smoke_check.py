#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "streamer_board_console.py"
text = source.read_text(encoding="utf-8")

parse_error = ""
methods = []
try:
    tree = ast.parse(text)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "StreamerBoardConsole")
    methods = [n.name for n in cls.body if isinstance(n, ast.FunctionDef)]
except Exception as exc:
    parse_error = str(exc)

required_methods = [
    "_build_dashboard",
    "_build_apps",
    "_build_profiles",
    "_build_data_tools",
    "_build_doctor",
    "_build_console_copier",
    "_build_release_prep",
    "build_release_prep_ui",
    "refresh_release_prep",
    "dashboard_context_menu",
    "profile_context_menu",
    "profile_row_selected",
    "apply_profile_editor_row",
    "save_profile_from_editor",
    "force_window_visible",
    "shutdown",
    "create_console_copy_ui",
    "refresh_console_copies",
    "launch_selected_console_copy_ui",
        "cleanup_console_copies_ui",
]

checks = {
    "parse_ok": not parse_error,
    "required_methods_inside_class": all(name in methods for name in required_methods),
    "has_backup_migrate_tab": "Backup / Migrate" in text,
    "has_console_copier_tab": "Console Copier" in text,
    "has_release_prep_tab": "Release Prep" in text,
    "has_release_prep_methods": all(s in text for s in ["_build_release_prep", "build_release_prep_ui", "inspect_release_prep_ui", "Clean Release Exports"]),
    "has_console_copier_methods": all(s in text for s in ["_build_console_copier", "create_console_copy_ui", "launch_selected_console_copy_ui",
        "cleanup_console_copies_ui", "refresh_console_copies"]),
        "has_console_copier_cleanup": "cleanup_console_copies_ui" in text and "Clean Selftest/Broken Copies" in text,
        "has_console_copier_status_columns": all(s in text for s in ["Launchable", "Status", ".sbconsole File"]),
        "has_instance_window_title": "SBC_INSTANCE_NAME" in text and "self.window_title" in text,
    "has_adapter_template_editor": "Selected Template Path / Entry Editor" in text,
    "has_adapter_templates": "Adapter Templates" in text,
    "has_apply_buttons": all(s in text for s in ["Apply Saved Profile", "Apply Saved + Run Actions"]),
    "has_custom_profile_editor": all(s in text for s in ["Profile Name / Description", "Save / Update Profile", "Delete Custom Profile"]),
    "has_dynamic_profiles": "expand_profile_for_apps" in text and "self.apps.keys()" in text,
    "has_new_template_entry": "New Template Entry" in text,
    "has_profile_actions": all(s in text for s in ["Keep", "Launch", "Close", "Restart", "Pause", "Resume"]),
    "has_profile_dropdown": "profile_combo" in text and "Profile:" in text,
    "has_profile_tree": "self.profile_tree = self._tree" in text,
    "has_quick_profile_buttons": all(s in text for s in ["Gaming", "Clean Visuals", "Talk / Podcast"]),
    "has_startup_profile_ui": "Startup Profile" in text and "Run startup profile actions" in text,
    "has_streamlined_profile_editor": all(s in text for s in ["Selected Row Editor", "Update Selected Row", "Set Row Action"]),
    "has_strict_action_language": "Keep does not change app process state" in text,
    "has_window_rescue": "force_window_visible" in text and "shutdown" in text,
    "no_duplicate_dynamic_table": "profile_editor_tree" not in text and "Dynamic App Profile Rows" not in text,
    "no_old_g502_soundcard_only_controls": "G502V Hotkeys:" not in text and "Soundcard Hotkeys:" not in text,
    "no_staged_placeholder": "Studio Profiles are staged" not in text,
}

report = {
    "tool": "sbc_gui_smoke_check",
    "source": str(source),
    "checks": checks,
    "class_methods_found": methods,
    "missing_class_methods": [name for name in required_methods if name not in methods],
    "parse_error": parse_error,
    "passed": all(checks.values()),
}
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
