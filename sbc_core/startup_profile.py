from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import USER_DATA
from .studio_profiles import load_profiles, apply_profile

STARTUP_PROFILE_PATH = USER_DATA / "startup_studio_profile.json"

def default_startup_config() -> dict[str, Any]:
    return {
        "enabled": False,
        "profile": "Gaming",
        "launch_apps": False,
    }

def read_startup_config() -> dict[str, Any]:
    data = default_startup_config()
    if STARTUP_PROFILE_PATH.exists():
        try:
            loaded = json.loads(STARTUP_PROFILE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
        except Exception:
            pass

    data["enabled"] = bool(data.get("enabled", False))
    data["profile"] = str(data.get("profile") or "Gaming")
    data["launch_apps"] = bool(data.get("launch_apps", False))
    return data

def save_startup_config(profile: str, enabled: bool = True, launch_apps: bool = False) -> dict[str, Any]:
    USER_DATA.mkdir(parents=True, exist_ok=True)
    data = {
        "enabled": bool(enabled),
        "profile": str(profile or "Gaming"),
        "launch_apps": bool(launch_apps),
    }
    STARTUP_PROFILE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data

def clear_startup_config() -> dict[str, Any]:
    data = default_startup_config()
    data["enabled"] = False
    STARTUP_PROFILE_PATH.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data

def validate_startup_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = read_startup_config() if config is None else config
    profiles = load_profiles()
    profile_name = str(cfg.get("profile") or "")
    return {
        "ok": profile_name in profiles,
        "enabled": bool(cfg.get("enabled", False)),
        "profile": profile_name,
        "launch_apps": bool(cfg.get("launch_apps", False)),
        "available_profiles": sorted(profiles.keys()),
        "exists": STARTUP_PROFILE_PATH.exists(),
        "path": str(STARTUP_PROFILE_PATH),
    }

def apply_startup_profile(apps: dict[str, Any]) -> dict[str, Any]:
    cfg = read_startup_config()
    validation = validate_startup_config(cfg)
    if not cfg.get("enabled", False):
        return {
            "ok": True,
            "skipped": True,
            "reason": "startup profile disabled",
            "config": cfg,
            "validation": validation,
        }
    if not validation.get("ok"):
        return {
            "ok": False,
            "skipped": True,
            "reason": f"startup profile not found: {cfg.get('profile')}",
            "config": cfg,
            "validation": validation,
        }

    result = apply_profile(str(cfg.get("profile")), apps, launch_apps=bool(cfg.get("launch_apps", False)))
    return {
        "ok": bool(result.get("ok")),
        "skipped": False,
        "config": cfg,
        "validation": validation,
        "apply_result": result,
    }
