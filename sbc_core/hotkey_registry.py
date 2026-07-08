from __future__ import annotations
from collections import defaultdict
from typing import Any

def collect_hotkeys(apps: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for app_id, app in apps.items():
        for item in app.default_hotkeys:
            rows.append({
                "app_id": app_id,
                "app": app.display_name,
                "key": str(item.get("key", "")).lower(),
                "action_id": str(item.get("action_id") or item.get("id") or item.get("action", "")).lower().replace(" ", "_"),
                "action": str(item.get("action", "")),
            })
    return rows

def find_conflicts(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped = defaultdict(list)
    for row in rows:
        key = row["key"].strip().lower()
        if key:
            grouped[key].append(row)
    return {key: value for key, value in grouped.items() if len(value) > 1}
