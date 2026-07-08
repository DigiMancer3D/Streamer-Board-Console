from __future__ import annotations

from pathlib import Path
from typing import Any

from .paths import APP_ROOT
from .storage import read_json, write_json

SUPPORT_MARKER = "SBC_ADAPTER_CONTROL_V1"

def app_local_control_paths(app) -> list[Path]:
    base = app.app_path
    return [
        base / "sbc_control.json",
        base / f"{app.app_id}.control.json",
    ]

def central_control_path(app) -> Path:
    rel = Path(app.control_file)
    return APP_ROOT / rel if not rel.is_absolute() else rel

def default_hotkey_map(app) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in getattr(app, "default_hotkeys", []) or []:
        key = str(item.get("key", "")).lower()
        action_id = str(item.get("action_id") or item.get("id") or item.get("action", "")).strip()
        action_id = action_id.lower().replace(" ", "_").replace("/", "_")
        if action_id and key:
            out[action_id] = key
    return out

def build_control_payload(app, hotkeys_enabled: bool = True, hotkey_map: dict[str, str] | None = None, mode: str = "local") -> dict[str, Any]:
    merged = default_hotkey_map(app)
    if hotkey_map:
        merged.update({str(k): str(v).lower() for k, v in hotkey_map.items() if str(k).strip()})
    return {
        "protocol": SUPPORT_MARKER,
        "app_id": app.app_id,
        "hotkeys_enabled": bool(hotkeys_enabled),
        "hotkey_map": merged,
        "mode": mode,
        "note": "SBC adapter control file. Native app support reads this from the app folder."
    }

def write_app_control(app, payload: dict[str, Any]) -> list[Path]:
    written: list[Path] = []
    central = central_control_path(app)
    write_json(central, payload)
    written.append(central)

    if app.app_path.exists():
        for path in app_local_control_paths(app):
            try:
                write_json(path, payload)
                written.append(path)
            except Exception:
                pass
    return written

def write_default_control(app, hotkeys_enabled: bool = True, mode: str = "local") -> list[Path]:
    payload = build_control_payload(app, hotkeys_enabled=hotkeys_enabled, mode=mode)
    return write_app_control(app, payload)

def read_support_file(app) -> dict[str, Any]:
    path = app.app_path / "sbc_adapter_support.json"
    return read_json(path, {}) if path.exists() else {}

def entry_contains_bridge_marker(app) -> bool:
    entry = app.app_path / app.entry_file
    if not entry.exists():
        return False
    try:
        text = entry.read_text(encoding="utf-8", errors="ignore")
        return SUPPORT_MARKER in text or "sbc_app_bridge" in text or "SBCAppBridge" in text
    except Exception:
        return False

def native_adapter_status(app) -> dict[str, Any]:
    support = read_support_file(app)
    bridge_file = app.app_path / "sbc_app_bridge.py"
    central = central_control_path(app)
    local_paths = app_local_control_paths(app)

    status = {
        "app_id": app.app_id,
        "display_name": app.display_name,
        "app_path_exists": app.app_path.exists(),
        "entry_file_exists": (app.app_path / app.entry_file).exists(),
        "bridge_file_exists": bridge_file.exists(),
        "support_file_exists": bool(support),
        "entry_has_bridge_marker": entry_contains_bridge_marker(app),
        "central_control_exists": central.exists(),
        "local_control_exists": any(p.exists() for p in local_paths),
        "support": support,
    }

    status["native_ready"] = bool(
        status["app_path_exists"]
        and status["entry_file_exists"]
        and status["bridge_file_exists"]
        and status["support_file_exists"]
        and status["entry_has_bridge_marker"]
    )
    return status
