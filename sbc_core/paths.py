from __future__ import annotations

import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

def _env_path(name: str, fallback: Path) -> Path:
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser() if value else fallback

USER_DATA = _env_path("SBC_USER_DATA", APP_ROOT / "user_data")
LOG_DIR = USER_DATA / "logs"
ADAPTER_DIR = _env_path("SBC_ADAPTER_DIR", APP_ROOT / "adapters")
TEMPLATE_DIR = _env_path("SBC_TEMPLATE_DIR", APP_ROOT / "adapter_templates")
BOARD_DIR = USER_DATA / "boards"
CONTROL_DIR = USER_DATA / "app_controls"
BOARD_INSTANCE_DIR = USER_DATA / "board_instances"
BOARD_COMMAND_DIR = BOARD_INSTANCE_DIR / "commands"

SBC_CONSOLE_FILE = os.environ.get("SBC_CONSOLE_FILE", "").strip()

def expand_user_path(value: str) -> Path:
    return Path(value).expanduser()
