# How 2 Integrate Apps with Streamer Board & Console

This guide explains how another app can be made template-capable for Streamer Board & Console.

## 1. Minimal adapter template

Each app starts with a JSON template in `adapter_templates/`.

Required fields:

```json
{
  "app_id": "my_app",
  "display_name": "My App",
  "default_path": "~/My-App",
  "launch_mode": "shell",
  "entry_file": "launch_my_app.sh",
  "settings_files": [],
  "control_file": "user_data/app_controls/my_app.control.json",
  "supports": {
    "launch_close": true,
    "restart": true,
    "resource_monitor": true,
    "pause_park_suspend": true,
    "hotkeys_toggle": false,
    "hotkey_remap": false,
    "local_live_toggle": false,
    "theme_sync": false,
    "emoji_sync": false
  },
  "default_hotkeys": [],
  "notes": "Describe anything the user must know before enabling."
}
```

## 2. Launch script expectation

The simplest integration is a shell launcher:

```bash
#!/usr/bin/env bash
cd "$(dirname "$0")"
./run_your_app_here.sh
```

Make it executable:

```bash
chmod +x launch_my_app.sh
```

Then set:

```json
"launch_mode": "shell",
"entry_file": "launch_my_app.sh"
```

## 3. Native control files

SBC writes app control JSON files to:

```text
user_data/app_controls/<app_id>.control.json
```

Native apps can optionally read this file to support hotkey toggles, remapping, local/live mode, theme sync, or emoji sync.

Basic control payload shape:

```json
{
  "protocol": "SBC_ADAPTER_CONTROL_V1",
  "app_id": "my_app",
  "hotkeys_enabled": true,
  "mode": "local",
  "hotkey_map": {},
  "updated_at": 1234567890.0
}
```

## 4. App-side bridge idea

Inside the app, poll the control file every second or when the file timestamp changes:

```python
import json
from pathlib import Path

control = Path("sbc_control.json")
if control.exists():
    data = json.loads(control.read_text())
    hotkeys_enabled = bool(data.get("hotkeys_enabled", True))
```

For stronger integration, copy `patches/sbc_app_bridge.py` into the app folder and adapt the app's input loop to call it.

## 5. Recommended integration stages

1. Template only: launch/close/resource monitor.
2. Native bridge: app reads `sbc_control.json`.
3. Hotkeys: support `hotkeys_enabled`.
4. Remap: support `hotkey_map`.
5. Local/live mode: support `mode`.
6. Theme/emoji sync when useful.

## 6. Safety rules

- Keep templates inactive until the path and entry script are confirmed.
- Never make SBC guess destructive actions.
- Close/Restart/Pause actions should be visible in the profile action table.
- Treat `Keep` as strict: do not launch, close, restart, pause, or resume.
- Use Backup / Migrate before large adapter changes.
