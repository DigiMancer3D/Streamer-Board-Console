from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import USER_DATA
from .adapter_control import build_control_payload, write_app_control

PROFILES_DIR = USER_DATA / "profiles"
ACTIVE_PROFILE_PATH = USER_DATA / "active_studio_profile.json"

PROFILE_ACTIONS = ["keep", "launch", "close", "restart", "pause", "resume"]

DEFAULT_PROFILES: dict[str, dict[str, Any]] = {
    "Gaming": {
        "description": "Normal live mode: Soundcard and G502V hotkeys enabled.",
        "apps": {
            "soundcard": {"hotkeys_enabled": True, "mode": "local", "action": "keep"},
            "g502v": {"hotkeys_enabled": True, "mode": "local", "action": "keep"}
        }
    },
    "Talk / Podcast": {
        "description": "Talking mode: keep G502V visual live, pause Soundcard movement hotkeys.",
        "apps": {
            "soundcard": {"hotkeys_enabled": False, "mode": "local", "action": "keep"},
            "g502v": {"hotkeys_enabled": True, "mode": "local", "action": "keep"}
        }
    },
    "Clean Visuals": {
        "description": "Turn off overlay hotkeys for both apps while leaving windows running.",
        "apps": {
            "soundcard": {"hotkeys_enabled": False, "mode": "local", "action": "keep"},
            "g502v": {"hotkeys_enabled": False, "mode": "local", "action": "keep"}
        }
    },
    "Full Control": {
        "description": "Everything responsive: Soundcard and G502V hotkeys enabled.",
        "apps": {
            "soundcard": {"hotkeys_enabled": True, "mode": "local", "action": "keep"},
            "g502v": {"hotkeys_enabled": True, "mode": "local", "action": "keep"}
        }
    },
    "OBS Safe / Low Motion": {
        "description": "Reduce accidental input lights/movement while keeping apps open for OBS capture.",
        "apps": {
            "soundcard": {"hotkeys_enabled": False, "mode": "local", "action": "keep"},
            "g502v": {"hotkeys_enabled": False, "mode": "local", "action": "keep"}
        }
    }
}

def normalize_action(value: Any) -> str:
    action = str(value or "keep").strip().lower()
    return action if action in PROFILE_ACTIONS else "keep"

def action_label(action: str) -> str:
    return normalize_action(action).title()

def ensure_default_profiles() -> list[Path]:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, payload in DEFAULT_PROFILES.items():
        path = PROFILES_DIR / f"{safe_profile_filename(name)}.json"
        if not path.exists():
            data = {"name": name, **payload}
            path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            written.append(path)
    return written

def safe_profile_filename(name: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "profile"

def load_profiles() -> dict[str, dict[str, Any]]:
    ensure_default_profiles()
    profiles: dict[str, dict[str, Any]] = {}
    for path in sorted(PROFILES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            name = str(data.get("name") or path.stem)
            # Backward-compatible profile normalization.
            apps = data.get("apps")
            if isinstance(apps, dict):
                for _app_id, settings in apps.items():
                    if isinstance(settings, dict):
                        settings["action"] = normalize_action(settings.get("action", "keep"))
            profiles[name] = data
        except Exception:
            continue
    return profiles

def save_profile(name: str, description: str, app_settings: dict[str, Any]) -> Path:
    ensure_default_profiles()
    normalized: dict[str, Any] = {}
    for app_id, settings in (app_settings or {}).items():
        if not isinstance(settings, dict):
            continue
        normalized[str(app_id)] = {
            "hotkeys_enabled": bool(settings.get("hotkeys_enabled", True)),
            "mode": str(settings.get("mode", "local")),
            "action": normalize_action(settings.get("action", "keep")),
        }
        if isinstance(settings.get("hotkey_map"), dict):
            normalized[str(app_id)]["hotkey_map"] = settings["hotkey_map"]

    data = {
        "name": name,
        "description": description,
        "apps": normalized,
    }
    path = PROFILES_DIR / f"{safe_profile_filename(name)}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path

def is_default_profile(name: str) -> bool:
    return name in DEFAULT_PROFILES

def delete_profile(name: str) -> dict[str, Any]:
    ensure_default_profiles()
    if is_default_profile(name):
        return {"ok": False, "error": f"Built-in profile cannot be deleted: {name}", "deleted": ""}
    path = PROFILES_DIR / f"{safe_profile_filename(name)}.json"
    if not path.exists():
        return {"ok": False, "error": f"Profile not found: {name}", "deleted": ""}
    path.unlink()
    return {"ok": True, "deleted": str(path)}

def profile_app_settings(
    g502v_enabled: bool = True,
    soundcard_enabled: bool = True,
    g502v_action: str = "keep",
    soundcard_action: str = "keep",
) -> dict[str, Any]:
    return {
        "g502v": {
            "hotkeys_enabled": bool(g502v_enabled),
            "mode": "local",
            "action": normalize_action(g502v_action),
        },
        "soundcard": {
            "hotkeys_enabled": bool(soundcard_enabled),
            "mode": "local",
            "action": normalize_action(soundcard_action),
        },
    }

def default_settings_for_app(app_id: str) -> dict[str, Any]:
    return {
        "hotkeys_enabled": True,
        "mode": "local",
        "action": "keep",
    }

def expand_profile_for_apps(profile: dict[str, Any], apps: dict[str, Any] | list[str] | tuple[str, ...] | None) -> dict[str, Any]:
    """Return a profile copy that includes every currently active app.

    Existing profiles may only list g502v/soundcard. When additional
    adapters are enabled, they appear in Studio Profiles with Keep by default.
    """
    data = dict(profile or {})
    app_map: dict[str, Any] = {}

    existing = data.get("apps") if isinstance(data.get("apps"), dict) else {}
    for app_id, settings in existing.items():
        if isinstance(settings, dict):
            app_map[str(app_id)] = {
                "hotkeys_enabled": bool(settings.get("hotkeys_enabled", True)),
                "mode": str(settings.get("mode", "local")),
                "action": normalize_action(settings.get("action", "keep")),
            }
            if isinstance(settings.get("hotkey_map"), dict):
                app_map[str(app_id)]["hotkey_map"] = settings["hotkey_map"]

    if isinstance(apps, dict):
        app_ids = list(apps.keys())
    elif apps is None:
        app_ids = []
    else:
        app_ids = [str(item) for item in apps]

    for app_id in app_ids:
        app_map.setdefault(str(app_id), default_settings_for_app(str(app_id)))

    data["apps"] = app_map
    return data

def profile_summary(profile: dict[str, Any], app_ids: list[str] | None = None) -> list[dict[str, str]]:
    expanded = expand_profile_for_apps(profile, app_ids or [])
    rows: list[dict[str, str]] = []
    for app_id, settings in (expanded.get("apps") or {}).items():
        action = normalize_action(settings.get("action", "keep")) if isinstance(settings, dict) else "keep"
        rows.append({
            "app_id": str(app_id),
            "hotkeys": "ON" if settings.get("hotkeys_enabled", True) else "OFF",
            "mode": str(settings.get("mode", "local")),
            "action": action_label(action),
        })
    return rows

def apply_app_action(app: Any, action: str) -> str:
    action = normalize_action(action)
    try:
        if action == "keep":
            return ""
        if action == "launch":
            return app.launch()
        if action == "close":
            return app.close()
        if action == "restart":
            return app.restart()
        if action == "pause":
            return app.pause_park()
        if action == "resume":
            return app.resume()
        return ""
    except Exception as exc:
        return f"{action_label(action)} failed for {getattr(app, 'display_name', 'app')}: {exc}"

def apply_profile(
    profile_name: str,
    apps: dict[str, Any],
    launch_apps: bool = False,
    *,
    run_actions: bool | None = None,
) -> dict[str, Any]:
    """Apply a saved Studio Profile.

    Compatibility note:
    - Older callers used the name ``launch_apps`` for what the UI now calls
      "Run Actions".  Keep accepting it, but make the behavior explicit.
    - When run_actions is False, this only writes control/hotkey files.
    - When run_actions is True, it also runs each saved per-app action.
    """
    if run_actions is None:
        run_actions = bool(launch_apps)
    else:
        run_actions = bool(run_actions)

    profiles = load_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        return {"ok": False, "error": f"Profile not found: {profile_name}", "applied": []}

    profile = expand_profile_for_apps(profile, apps)

    applied = []
    missing = []
    for app_id, settings in (profile.get("apps") or {}).items():
        app = apps.get(app_id)
        if not app:
            missing.append(app_id)
            continue

        hotkeys_enabled = bool(settings.get("hotkeys_enabled", True))
        mode = str(settings.get("mode", "local"))
        profile_action = normalize_action(settings.get("action", "keep"))
        effective_action = profile_action if run_actions else "keep"

        hotkey_map = settings.get("hotkey_map") if isinstance(settings.get("hotkey_map"), dict) else {}
        payload = build_control_payload(app, hotkeys_enabled=hotkeys_enabled, hotkey_map=hotkey_map, mode=mode)
        paths = write_app_control(app, payload)

        action_message = apply_app_action(app, effective_action) if run_actions else ""

        applied.append({
            "app_id": app_id,
            "display_name": app.display_name,
            "hotkeys_enabled": hotkeys_enabled,
            "mode": mode,
            "action": profile_action,
            "effective_action": effective_action,
            "run_actions": run_actions,
            "action_message": action_message,
            # Backward-compatible key used by earlier GUI/profile status code.
            "launch_message": action_message if effective_action == "launch" else "",
            "written": [str(p) for p in paths],
        })

    USER_DATA.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROFILE_PATH.write_text(json.dumps({
        "active_profile": profile_name,
        "profile": profile,
        "applied": applied,
        "missing": missing,
        "launch_apps": run_actions,
        "run_actions": run_actions,
    }, indent=2, sort_keys=True), encoding="utf-8")

    return {
        "ok": True,
        "profile": profile_name,
        "applied": applied,
        "missing": missing,
        "launch_apps": run_actions,
        "run_actions": run_actions,
    }

def active_profile_name() -> str:
    try:
        data = json.loads(ACTIVE_PROFILE_PATH.read_text(encoding="utf-8"))
        return str(data.get("active_profile", ""))
    except Exception:
        return ""
