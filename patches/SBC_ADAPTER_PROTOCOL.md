# SBC Adapter Control Protocol v1

Streamer Board & Console controls apps by writing local JSON files. No sockets,
no HTTP, no network, and no tight polling loops.

## Control files

```text
<target app>/sbc_control.json
<target app>/<app_id>.control.json
Streamer_Board_Console/user_data/app_controls/<app_id>.control.json
```

## Example

```json
{
  "protocol": "SBC_ADAPTER_CONTROL_V1",
  "app_id": "soundcard",
  "hotkeys_enabled": false,
  "hotkey_map": {
    "move_up": "i",
    "move_down": "k",
    "move_left": "j",
    "move_right": "l"
  },
  "mode": "local"
}
```
