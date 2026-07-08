from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .paths import APP_ROOT, USER_DATA, ADAPTER_DIR, TEMPLATE_DIR

FORMAT_VERSION = "SBC_CONSOLE_INSTANCE_V1"
CONSOLE_COPIES_DIR = USER_DATA / "console_copies"
CONSOLE_INSTANCES_DIR = USER_DATA / "console_instances"

USER_DATA_FILES = [
    "current.emoji",
    "active_studio_profile.json",
    "startup_studio_profile.json",
    "sbc_settings.json",
]

USER_DATA_DIRS = [
    "profiles",
    "boards",
    "imported_images",
    "app_controls",
]

def _now() -> int:
    return int(time.time())

def epoch_hex(epoch: int | None = None) -> str:
    return format(int(epoch if epoch is not None else _now()), "x")

def console_file_path(console_id: str) -> Path:
    return CONSOLE_COPIES_DIR / f"{console_id}.sbconsole"

def instance_root(console_id: str) -> Path:
    return CONSOLE_INSTANCES_DIR / console_id

def safe_name(value: str) -> str:
    text = str(value or "").strip()
    return text or "Streamer Console Copy"

def _copy_file(src: Path, dest: Path) -> bool:
    if src.exists() and src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True
    return False

def _copy_tree(src: Path, dest: Path, *, json_only: bool = False) -> int:
    copied = 0
    if not src.exists() or not src.is_dir():
        return copied
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if json_only and path.suffix != ".json":
            continue
        rel = path.relative_to(src)
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        copied += 1
    return copied

def _remove_path(path: Path) -> None:
    try:
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    except Exception:
        pass

def create_console_copy(name: str = "", clone_current: bool = True) -> dict[str, Any]:
    created_epoch = _now()
    cid = epoch_hex(created_epoch)
    root = instance_root(cid)
    data_root = root / "user_data"
    adapter_dir = root / "adapters"
    template_dir = root / "adapter_templates"

    CONSOLE_COPIES_DIR.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    adapter_dir.mkdir(parents=True, exist_ok=True)
    template_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []

    if clone_current:
        for filename in USER_DATA_FILES:
            if _copy_file(USER_DATA / filename, data_root / filename):
                copied.append(f"user_data/{filename}")

        for dirname in USER_DATA_DIRS:
            count = _copy_tree(USER_DATA / dirname, data_root / dirname)
            if count:
                copied.append(f"user_data/{dirname}/ ({count} files)")

        adapter_count = _copy_tree(ADAPTER_DIR, adapter_dir, json_only=True)
        template_count = _copy_tree(TEMPLATE_DIR, template_dir, json_only=True)
        if adapter_count:
            copied.append(f"adapters/ ({adapter_count} files)")
        if template_count:
            copied.append(f"adapter_templates/ ({template_count} files)")

    payload = {
        "format": FORMAT_VERSION,
        "console_id": cid,
        "name": safe_name(name),
        "created_epoch": created_epoch,
        "created_epoch_hex": cid,
        "created_at_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(created_epoch)),
        "app_root": str(APP_ROOT),
        "data_root": str(data_root),
        "adapter_dir": str(adapter_dir),
        "template_dir": str(template_dir),
        "console_root": str(root),
        "clone_current": bool(clone_current),
        "copied": copied,
        "notes": "Launch with SBC_USER_DATA/SBC_ADAPTER_DIR/SBC_TEMPLATE_DIR for an isolated console copy.",
    }

    path = console_file_path(cid)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    return {"ok": True, "console_id": cid, "console_file": str(path), "console": payload}

def validate_console_data(data: dict[str, Any]) -> dict[str, Any]:
    app_root = Path(str(data.get("app_root", ""))).expanduser()
    data_root = Path(str(data.get("data_root", ""))).expanduser()
    adapter_dir = Path(str(data.get("adapter_dir", ""))).expanduser()
    template_dir = Path(str(data.get("template_dir", ""))).expanduser()
    launcher = app_root / "launch_streamer_board_console.sh"

    exists = {
        "data_root": data_root.exists(),
        "adapter_dir": adapter_dir.exists(),
        "template_dir": template_dir.exists(),
        "app_root": app_root.exists(),
        "launcher": launcher.exists(),
    }

    missing = [name for name, ok in exists.items() if not ok]
    suspicious = []
    current_app_root = str(APP_ROOT)
    for key in ("data_root", "adapter_dir", "template_dir", "app_root"):
        value = str(data.get(key, ""))
        if value.startswith("/mnt/data/") and not current_app_root.startswith("/mnt/data/"):
            suspicious.append(key)

    launchable = not missing and not suspicious
    status = "OK"
    if suspicious:
        status = "Invalid packaged selftest path"
    elif missing:
        status = "Missing: " + ", ".join(missing)

    return {
        "ok": launchable,
        "launchable": launchable,
        "status": status,
        "missing": missing,
        "suspicious": suspicious,
        "exists": exists,
        "launcher": str(launcher),
    }

def read_console_file(path_or_id: str | Path) -> dict[str, Any]:
    text = str(path_or_id)
    path = Path(text).expanduser()
    if not path.exists():
        path = console_file_path(text.replace(".sbconsole", ""))
    if not path.exists():
        return {"ok": False, "error": f"Console file not found: {path_or_id}", "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"Console file read error: {exc}", "path": str(path)}

    validation = validate_console_data(data)
    return {
        "ok": True,
        "path": str(path),
        "console": data,
        "exists": validation.get("exists", {}),
        "validation": validation,
    }

def list_console_files(include_invalid: bool = True) -> dict[str, Any]:
    CONSOLE_COPIES_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(CONSOLE_COPIES_DIR.glob("*.sbconsole"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = read_console_file(path)
        data = item.get("console", {}) if item.get("ok") else {}
        validation = item.get("validation", {}) if item.get("ok") else {"launchable": False, "status": item.get("error", "Invalid")}
        if not include_invalid and not validation.get("launchable"):
            continue
        rows.append({
            "console_id": str(data.get("console_id", path.stem)),
            "name": str(data.get("name", path.stem)),
            "console_file": str(path),
            "created_at_text": str(data.get("created_at_text", "")),
            "data_root": str(data.get("data_root", "")),
            "adapter_dir": str(data.get("adapter_dir", "")),
            "template_dir": str(data.get("template_dir", "")),
            "ok": bool(item.get("ok")),
            "launchable": bool(validation.get("launchable", False)),
            "status": str(validation.get("status", "")),
        })

    return {
        "ok": True,
        "console_dir": str(CONSOLE_COPIES_DIR),
        "instance_dir": str(CONSOLE_INSTANCES_DIR),
        "count": len(rows),
        "consoles": rows,
    }

def launch_console_copy(path_or_id: str | Path) -> dict[str, Any]:
    item = read_console_file(path_or_id)
    if not item.get("ok"):
        return item

    data = item["console"]
    validation = item.get("validation", {})
    if not validation.get("launchable", False):
        return {
            "ok": False,
            "error": f"Console copy is not launchable: {validation.get('status', 'Invalid')}",
            "console": data,
            "validation": validation,
        }

    app_root = Path(str(data.get("app_root") or APP_ROOT)).expanduser()
    data_root = Path(str(data.get("data_root", ""))).expanduser()
    log_dir = data_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "console_launcher.log"

    env = os.environ.copy()
    env["SBC_CONSOLE_FILE"] = item["path"]
    env["SBC_USER_DATA"] = str(data.get("data_root", ""))
    env["SBC_ADAPTER_DIR"] = str(data.get("adapter_dir", ""))
    env["SBC_TEMPLATE_DIR"] = str(data.get("template_dir", ""))
    env["SBC_INSTANCE_NAME"] = str(data.get("name") or data.get("console_id") or "Console Copy")
    env.setdefault("SBC_WINDOW_GEOMETRY", "1180x760+140+140")

    with open(log_path, "a", encoding="utf-8") as log:
        log.write("\n\n=== launch console copy ===\n")
        log.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        log.write(f"console_file={item['path']}\n")
        log.write(f"app_root={app_root}\n")
        log.flush()

        proc = subprocess.Popen(
            ["bash", "-lc", f'cd "{app_root}" && ./launch_streamer_board_console.sh'],
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )

    time.sleep(0.75)
    exit_code = proc.poll()
    if exit_code is not None:
        return {
            "ok": False,
            "pid": proc.pid,
            "exit_code": exit_code,
            "console_id": data.get("console_id", ""),
            "console_file": item["path"],
            "log_path": str(log_path),
            "error": f"Console copy exited immediately with code {exit_code}. Check log: {log_path}",
        }

    return {
        "ok": True,
        "pid": proc.pid,
        "console_id": data.get("console_id", ""),
        "console_file": item["path"],
        "log_path": str(log_path),
        "message": f"Launched console copy {data.get('name', data.get('console_id'))} with PID {proc.pid}. Log: {log_path}",
    }

def cleanup_selftest_and_broken_copies() -> dict[str, Any]:
    CONSOLE_COPIES_DIR.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    kept: list[str] = []

    for path in sorted(CONSOLE_COPIES_DIR.glob("*.sbconsole")):
        item = read_console_file(path)
        data = item.get("console", {}) if item.get("ok") else {}
        validation = item.get("validation", {}) if item.get("ok") else {}
        name = str(data.get("name", ""))
        is_selftest = name.startswith("Selftest Console Copy")
        is_mnt = bool(validation.get("suspicious"))
        is_broken_selftest = bool(validation.get("missing")) and is_selftest

        if is_selftest or is_mnt or is_broken_selftest:
            cid = str(data.get("console_id", path.stem))
            console_root = Path(str(data.get("console_root", ""))).expanduser()
            removed.append(str(path))
            _remove_path(path)
            if console_root.exists() and "console_instances" in console_root.parts:
                _remove_path(console_root)
            else:
                _remove_path(instance_root(cid))
        else:
            kept.append(str(path))

    return {
        "ok": True,
        "removed": removed,
        "removed_count": len(removed),
        "kept_count": len(kept),
    }
