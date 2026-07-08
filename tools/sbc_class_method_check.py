#!/usr/bin/env python3
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import streamer_board_console

cls = streamer_board_console.StreamerBoardConsole
required = [
    "dashboard_context_menu",
    "_build_profiles",
    "_profile_action_values",
    "apply_selected_profile",
    "profile_context_menu",
    "profile_row_selected",
    "selected_profile_row_app_id",
    "set_selected_profile_row_hotkeys",
    "set_selected_profile_row_action",
    "apply_profile_editor_row",
    "set_profile_editor_all_keep",
    "refresh_profile_tree",
    "load_selected_profile_into_editor",
    "save_profile_from_editor",
    "delete_selected_custom_profile",
    "apply_startup_profile_on_launch",
    "dry_run_import_user_data_ui",
    "import_user_data_backup_ui",
    "export_user_data_backup_ui",
    "refresh_backup_tools",
    "_build_data_tools",
    "apply_startup_now_ui",
    "clear_startup_profile_ui",
    "set_selected_startup_profile",
    "refresh_startup_controls",
    "_scrollable_content",
    "migrate_latest_previous_build_ui",
    "_build_doctor",
    "_build_release_prep",
    "build_release_prep_ui",
    "refresh_release_prep",
    "refresh_all",
]

report = {
    "tool": "sbc_class_method_check",
    "class": "StreamerBoardConsole",
    "missing": [name for name in required if not hasattr(cls, name)],
    "methods": [name for name, _obj in inspect.getmembers(cls, inspect.isfunction)],
}
report["passed"] = not report["missing"]
print(json.dumps(report, indent=2, sort_keys=True))
raise SystemExit(0 if report["passed"] else 1)
