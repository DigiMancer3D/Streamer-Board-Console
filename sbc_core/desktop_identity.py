from __future__ import annotations

import os
import shlex
from pathlib import Path

# Public-safe desktop identity mapping. No user paths.
# The values match the tested KDE/Plasma WM_CLASS second values.
APP_DESKTOP_IDENTITY = {
    "deck_card_widget": {"tk_class": "Dcpdeckreader"},
    "swar": {"qt_app_name": "Dcpdeckreader", "qt_display_name": "SWAR Reader", "qt_desktop_file": "swar-reader"},
    "swar_v0_6_0_rc1_r2": {"qt_app_name": "Swarstandard", "qt_display_name": "SWAR Standard", "qt_desktop_file": "swar-standard"},
    "g502v": {"tk_class": "Definethyio"},
    "soundcard": {"tk_class": "Definethyio"},
}


def identity_helper_dir() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local/share"
    return base / "digimancer_desktop_identity_py"


def child_identity_env(app_id: str, base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    spec = APP_DESKTOP_IDENTITY.get(str(app_id), {})
    helper = identity_helper_dir()

    if not spec:
        return env

    if "tk_class" in spec:
        env["DIGIMANCER_TK_CLASS"] = spec["tk_class"]
    if "qt_app_name" in spec:
        env["DIGIMANCER_QT_APP_NAME"] = spec["qt_app_name"]
        env["DIGIMANCER_QT_DISPLAY_NAME"] = spec.get("qt_display_name", spec["qt_app_name"])
        env["DIGIMANCER_QT_DESKTOP_FILE"] = spec.get("qt_desktop_file", str(app_id))

    env["PYTHONPATH"] = str(helper) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def shell_prefix_for_app_id(app_id: str) -> str:
    spec = APP_DESKTOP_IDENTITY.get(str(app_id), {})
    if not spec:
        return ""
    helper = identity_helper_dir()
    parts = []
    if "tk_class" in spec:
        parts.append(f"export DIGIMANCER_TK_CLASS={shlex.quote(spec['tk_class'])}")
    if "qt_app_name" in spec:
        parts.append(f"export DIGIMANCER_QT_APP_NAME={shlex.quote(spec['qt_app_name'])}")
        parts.append(f"export DIGIMANCER_QT_DISPLAY_NAME={shlex.quote(spec.get('qt_display_name', spec['qt_app_name']))}")
        parts.append(f"export DIGIMANCER_QT_DESKTOP_FILE={shlex.quote(spec.get('qt_desktop_file', str(app_id)))}")
    parts.append(f"export PYTHONPATH={shlex.quote(str(helper))}:\"${{PYTHONPATH:-}}\"")
    return "; ".join(parts) + "; "
