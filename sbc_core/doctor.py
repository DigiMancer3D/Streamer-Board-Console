from __future__ import annotations
from typing import Any

from .adapter_control import native_adapter_status

def run_doctor(apps: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for app_id, app in apps.items():
        app_path = app.app_path
        if app_path.exists():
            rows.append({"status": "PASS", "item": app.display_name, "detail": f"Path found: {app_path}"})
        else:
            rows.append({"status": "WARN", "item": app.display_name, "detail": f"Path missing: {app_path}"})

        if (app_path / "venv").exists():
            rows.append({"status": "PASS", "item": app.display_name, "detail": "venv folder found"})
        else:
            rows.append({"status": "INFO", "item": app.display_name, "detail": "venv folder not found; launcher will try system python"})

        if (app_path / app.entry_file).exists():
            rows.append({"status": "PASS", "item": app.display_name, "detail": f"Entry file found: {app.entry_file}"})
        else:
            rows.append({"status": "WARN", "item": app.display_name, "detail": f"Entry file missing: {app.entry_file}"})

        for settings_name in app.settings_files:
            if (app_path / settings_name).exists():
                rows.append({"status": "PASS", "item": app.display_name, "detail": f"Settings found: {settings_name}"})
            else:
                rows.append({"status": "INFO", "item": app.display_name, "detail": f"Settings not found yet: {settings_name}"})

        status = native_adapter_status(app)
        if status["native_ready"]:
            rows.append({"status": "PASS", "item": app.display_name, "detail": "Native SBC adapter support detected"})
        else:
            missing = []
            if not status["bridge_file_exists"]:
                missing.append("sbc_app_bridge.py")
            if not status["support_file_exists"]:
                missing.append("sbc_adapter_support.json")
            if not status["entry_has_bridge_marker"]:
                missing.append("entry hook marker")
            rows.append({
                "status": "INFO",
                "item": app.display_name,
                "detail": "Native adapter not active yet; missing " + ", ".join(missing)
            })

        if status["local_control_exists"]:
            rows.append({"status": "PASS", "item": app.display_name, "detail": "App-local SBC control file found"})
        else:
            rows.append({"status": "INFO", "item": app.display_name, "detail": "App-local SBC control file not written yet"})

    return rows
