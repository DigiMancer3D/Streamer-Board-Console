from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .paths import APP_ROOT, ADAPTER_DIR, TEMPLATE_DIR, expand_user_path

HOW2_INTEGRATE_PATH = APP_ROOT / "HOW2_INTEGRATE_ADAPTERS.md"
CORE_ADAPTERS = {"soundcard", "g502v"}

DEFAULT_TEMPLATES: dict[str, dict[str, Any]] = {
    "bitninja_mocap": {
        "app_id": "bitninja_mocap",
        "display_name": "Bitninja Mocap Lite",
        "default_path": "~/Bitninja-Mocap-Lite",
        "launch_mode": "shell",
        "entry_file": "run_bitninja_lite_standard.sh",
        "settings_files": [],
        "control_file": "user_data/app_controls/bitninja_mocap.control.json",
        "supports": {
            "launch_close": True,
            "restart": True,
            "resource_monitor": True,
            "pause_park_suspend": True,
            "hotkeys_toggle": False,
            "hotkey_remap": False,
            "local_live_toggle": "future",
            "theme_sync": "future",
            "emoji_sync": False
        },
        "default_hotkeys": [],
        "notes": "Template only. Enable after confirming local path and launch script."
    },
    "deck_card_widget": {
        "app_id": "deck_card_widget",
        "display_name": "Deck Card Widget",
        "default_path": "~/Deck-Card-Widget",
        "launch_mode": "shell",
        "entry_file": "launch_deck_card_widget.sh",
        "settings_files": [],
        "control_file": "user_data/app_controls/deck_card_widget.control.json",
        "supports": {
            "launch_close": True,
            "restart": True,
            "resource_monitor": True,
            "pause_park_suspend": True,
            "hotkeys_toggle": False,
            "hotkey_remap": False,
            "local_live_toggle": "future",
            "theme_sync": "future",
            "emoji_sync": True
        },
        "default_hotkeys": [],
        "notes": "Template only. Edit entry_file if your local launcher has a different name."
    },
    "swar": {
        "app_id": "swar",
        "display_name": "SWAR Script Writer/Reader",
        "default_path": "~/SWAR/SWAR_v0_6_0_RC1",
        "launch_mode": "shell",
        "entry_file": "launch_standard.sh",
        "settings_files": ["SWAR.udata"],
        "control_file": "user_data/app_controls/swar.control.json",
        "supports": {
            "launch_close": True,
            "restart": True,
            "resource_monitor": True,
            "pause_park_suspend": True,
            "hotkeys_toggle": False,
            "hotkey_remap": False,
            "local_live_toggle": False,
            "theme_sync": "future",
            "emoji_sync": False
        },
        "default_hotkeys": [],
        "notes": "Template only. Update default_path if your current SWAR folder is a newer version."
    }
}

def ensure_adapter_templates() -> list[Path]:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for app_id, payload in DEFAULT_TEMPLATES.items():
        path = TEMPLATE_DIR / f"{app_id}.json"
        if not path.exists():
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            written.append(path)
    return written

def safe_app_id(value: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value)).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "custom_app"

def template_path(app_id: str) -> Path:
    return TEMPLATE_DIR / f"{safe_app_id(app_id)}.json"

def adapter_path(app_id: str) -> Path:
    return ADAPTER_DIR / f"{safe_app_id(app_id)}.json"

def load_template(app_id: str) -> dict[str, Any]:
    ensure_adapter_templates()
    path = template_path(app_id)
    if not path.exists():
        raise FileNotFoundError(f"Adapter template not found: {app_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data

def _row_for_template(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    app_id = str(data.get("app_id") or path.stem)
    active = adapter_path(app_id).exists()
    app_path = expand_user_path(str(data.get("default_path", "")))
    entry = str(data.get("entry_file", ""))
    entry_path = app_path / entry
    return {
        "app_id": app_id,
        "display_name": str(data.get("display_name", app_id)),
        "template_path": str(path),
        "adapter_path": str(adapter_path(app_id)),
        "active": active,
        "default_path": str(app_path),
        "default_path_raw": str(data.get("default_path", "")),
        "entry_file": entry,
        "app_path_exists": app_path.exists(),
        "entry_file_exists": entry_path.exists(),
        "notes": str(data.get("notes", "")),
    }

def list_templates() -> dict[str, Any]:
    ensure_adapter_templates()
    rows = []
    for path in sorted(TEMPLATE_DIR.glob("*.json")):
        try:
            rows.append(_row_for_template(path))
        except Exception as exc:
            rows.append({
                "app_id": path.stem,
                "display_name": path.stem,
                "template_path": str(path),
                "adapter_path": "",
                "active": False,
                "default_path": "",
                "default_path_raw": "",
                "entry_file": "",
                "app_path_exists": False,
                "entry_file_exists": False,
                "notes": f"Template read error: {exc}",
            })

    return {
        "ok": True,
        "template_dir": str(TEMPLATE_DIR),
        "adapter_dir": str(ADAPTER_DIR),
        "templates": rows,
        "count": len(rows),
    }

def update_template(
    app_id: str,
    default_path: str | None = None,
    entry_file: str | None = None,
    display_name: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    ensure_adapter_templates()
    path = template_path(app_id)
    if not path.exists():
        return {"ok": False, "error": f"Template not found: {app_id}", "app_id": app_id}

    data = json.loads(path.read_text(encoding="utf-8"))
    if default_path is not None:
        data["default_path"] = str(default_path)
    if entry_file is not None:
        data["entry_file"] = str(entry_file)
    if display_name is not None:
        data["display_name"] = str(display_name)
    if notes is not None:
        data["notes"] = str(notes)

    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    real_app_id = str(data.get("app_id") or app_id)
    active_path = adapter_path(real_app_id)
    mirrored_active = False
    if active_path.exists():
        active_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        mirrored_active = True

    row = _row_for_template(path)
    row.update({
        "ok": True,
        "mirrored_active": mirrored_active,
    })
    return row

def create_custom_template(
    app_id: str,
    display_name: str,
    default_path: str,
    entry_file: str,
    launch_mode: str = "shell",
) -> dict[str, Any]:
    ensure_adapter_templates()
    safe_id = safe_app_id(app_id)
    path = template_path(safe_id)
    if path.exists():
        return {"ok": False, "error": f"Template already exists: {safe_id}", "app_id": safe_id, "template_path": str(path)}
    data = {
        "app_id": safe_id,
        "display_name": display_name or safe_id,
        "default_path": default_path,
        "launch_mode": launch_mode,
        "entry_file": entry_file,
        "settings_files": [],
        "control_file": f"user_data/app_controls/{safe_id}.control.json",
        "supports": {
            "launch_close": True,
            "restart": True,
            "resource_monitor": True,
            "pause_park_suspend": True,
            "hotkeys_toggle": False,
            "hotkey_remap": False,
            "local_live_toggle": False,
            "theme_sync": False,
            "emoji_sync": False
        },
        "default_hotkeys": [],
        "notes": "Custom template created from SBC."
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return {"ok": True, "app_id": safe_id, "template_path": str(path), "template": data}


def derive_template_identity(default_path: str, entry_file: str) -> dict[str, str]:
    """Derive a useful app_id/display name from path + entry."""
    path_text = str(default_path or "").strip().rstrip("/")
    entry_text = str(entry_file or "").strip()
    folder_name = Path(path_text).name if path_text else ""
    entry_stem = Path(entry_text).stem if entry_text else ""
    base = folder_name or entry_stem or "custom_app"
    app_id = safe_app_id(base)
    display = base.replace("_", " ").replace("-", " ").strip().title() or app_id
    return {"app_id": app_id, "display_name": display}

def create_template_from_path_entry(default_path: str, entry_file: str, display_name: str | None = None) -> dict[str, Any]:
    ident = derive_template_identity(default_path, entry_file)
    return create_custom_template(
        ident["app_id"],
        display_name or ident["display_name"],
        default_path,
        entry_file,
        launch_mode="shell",
    )

def enable_template(app_id: str, overwrite: bool = False) -> dict[str, Any]:
    ensure_adapter_templates()
    src = template_path(app_id)
    if not src.exists():
        return {"ok": False, "error": f"Template not found: {app_id}", "app_id": app_id}

    data = json.loads(src.read_text(encoding="utf-8"))
    real_app_id = str(data.get("app_id") or app_id)
    dest = adapter_path(real_app_id)
    if dest.exists() and not overwrite:
        return {
            "ok": True,
            "already_active": True,
            "app_id": real_app_id,
            "adapter_path": str(dest),
            "message": f"Adapter already active: {real_app_id}",
        }

    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return {
        "ok": True,
        "already_active": False,
        "app_id": real_app_id,
        "adapter_path": str(dest),
        "message": f"Enabled adapter template: {real_app_id}. Restart console to show full app controls.",
    }

def disable_adapter(app_id: str) -> dict[str, Any]:
    safe_id = safe_app_id(app_id)
    if safe_id in CORE_ADAPTERS:
        return {
            "ok": False,
            "error": f"Core adapter is protected and cannot be disabled here: {safe_id}",
            "app_id": safe_id,
        }
    dest = adapter_path(safe_id)
    if not dest.exists():
        return {"ok": True, "already_disabled": True, "app_id": safe_id, "message": f"Adapter already disabled: {safe_id}"}
    dest.unlink()
    return {
        "ok": True,
        "already_disabled": False,
        "app_id": safe_id,
        "message": f"Disabled adapter: {safe_id}. Restart console to remove old app controls if they are visible.",
    }

def integration_guide_text() -> str:
    if HOW2_INTEGRATE_PATH.exists():
        return HOW2_INTEGRATE_PATH.read_text(encoding="utf-8", errors="replace")
    return "HOW2_INTEGRATE_ADAPTERS.md is missing."
