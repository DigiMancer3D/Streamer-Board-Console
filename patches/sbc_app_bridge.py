#!/usr/bin/env python3
"""SBC App Bridge v1: local-file app adapter control."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

SBC_ADAPTER_CONTROL_V1 = True

class SBCAppBridge:
    def __init__(
        self,
        app_id: str,
        app_dir: str | Path | None = None,
        *,
        poll_interval: float = 0.50,
        default_hotkey_map: dict[str, Any] | None = None,
    ):
        self.app_id = app_id
        self.app_dir = Path(app_dir) if app_dir is not None else Path.cwd()
        self.poll_interval = max(0.10, float(poll_interval))
        self.default_hotkey_map = default_hotkey_map or {}
        self._last_poll = 0.0
        self._last_mtime = -1.0
        self._control = {
            "protocol": "SBC_ADAPTER_CONTROL_V1",
            "app_id": app_id,
            "hotkeys_enabled": True,
            "hotkey_map": dict(self.default_hotkey_map),
            "mode": "local",
        }

    @property
    def generic_control_path(self) -> Path:
        return self.app_dir / "sbc_control.json"

    @property
    def app_control_path(self) -> Path:
        return self.app_dir / f"{self.app_id}.control.json"

    @property
    def support_path(self) -> Path:
        return self.app_dir / "sbc_adapter_support.json"

    def write_support(self, supports: dict[str, Any] | None = None) -> None:
        payload = {
            "protocol": "SBC_ADAPTER_CONTROL_V1",
            "app_id": self.app_id,
            "bridge_file": "sbc_app_bridge.py",
            "control_files": ["sbc_control.json", f"{self.app_id}.control.json"],
            "supports": supports or {
                "hotkeys_toggle": True,
                "hotkey_remap": True,
                "local_live_toggle": False,
            },
            "updated_at": time.time(),
        }
        try:
            self.support_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass

    def _pick_control_path(self) -> Path | None:
        if self.app_control_path.exists():
            return self.app_control_path
        if self.generic_control_path.exists():
            return self.generic_control_path
        return None

    def poll(self, force: bool = False) -> dict[str, Any]:
        now = time.time()
        if not force and now - self._last_poll < self.poll_interval:
            return self._control

        self._last_poll = now
        path = self._pick_control_path()
        if not path:
            return self._control

        try:
            mtime = path.stat().st_mtime
            if not force and mtime == self._last_mtime:
                return self._control
            self._last_mtime = mtime
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._control.update(data)
        except Exception:
            pass

        return self._control

    def hotkeys_enabled(self) -> bool:
        return bool(self.poll().get("hotkeys_enabled", True))

    def mode(self) -> str:
        return str(self.poll().get("mode", "local"))

    def hotkey_map(self) -> dict[str, Any]:
        data = self.poll()
        current = dict(self.default_hotkey_map)
        extra = data.get("hotkey_map", {})
        if isinstance(extra, dict):
            current.update(extra)
        return current

    def key_for(self, action: str, default: str) -> str:
        return str(self.hotkey_map().get(action, default)).lower()

    def control_snapshot(self) -> dict[str, Any]:
        return dict(self.poll(force=True))
