from __future__ import annotations

import time
import uuid
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from .paths import APP_ROOT, BOARD_INSTANCE_DIR, BOARD_COMMAND_DIR
from .storage import read_json, write_json

STALE_SECONDS = 10.0

@dataclass
class BoardInstance:
    instance_id: str
    pid: int | None
    title: str
    controller_title: str
    output_title: str
    board_path: str
    heartbeat: float
    status_path: Path
    running: bool

    @property
    def display_name(self) -> str:
        short = self.instance_id[:8]
        return self.title or f"Pin Board {short}"

def ensure_dirs() -> None:
    BOARD_INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    BOARD_COMMAND_DIR.mkdir(parents=True, exist_ok=True)

def new_instance_id() -> str:
    return uuid.uuid4().hex[:12]

def status_file(instance_id: str) -> Path:
    ensure_dirs()
    return BOARD_INSTANCE_DIR / f"{instance_id}.status.json"

def command_file(instance_id: str) -> Path:
    ensure_dirs()
    return BOARD_COMMAND_DIR / f"{instance_id}.command.json"

def pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        return psutil.pid_exists(int(pid)) and psutil.Process(int(pid)).is_running()
    except Exception:
        return False

def scan_board_instances(include_stale: bool = False) -> list[BoardInstance]:
    ensure_dirs()
    now = time.time()
    out: list[BoardInstance] = []

    for path in sorted(BOARD_INSTANCE_DIR.glob("*.status.json")):
        data = read_json(path, {})
        instance_id = str(data.get("instance_id") or path.name.split(".")[0])
        pid_raw = data.get("pid")
        try:
            pid = int(pid_raw) if pid_raw else None
        except Exception:
            pid = None

        heartbeat = float(data.get("heartbeat", 0.0) or 0.0)
        running = pid_running(pid)
        stale = (now - heartbeat) > STALE_SECONDS

        if stale and not include_stale:
            continue

        out.append(BoardInstance(
            instance_id=instance_id,
            pid=pid,
            title=str(data.get("title", f"Pin Board {instance_id[:8]}")),
            controller_title=str(data.get("controller_title", "")),
            output_title=str(data.get("output_title", "")),
            board_path=str(data.get("board_path", "")),
            heartbeat=heartbeat,
            status_path=path,
            running=bool(running and not stale),
        ))

    return out

def launch_board(board_path: str = "", delete_board_after_load: bool = False) -> tuple[str, subprocess.Popen]:
    ensure_dirs()
    instance_id = new_instance_id()
    script = APP_ROOT / "pin_board_instance.py"

    cmd = [sys.executable, str(script), "--instance-id", instance_id]
    if board_path:
        cmd.extend(["--board", board_path])
    if delete_board_after_load:
        cmd.append("--delete-board-after-load")

    proc = subprocess.Popen(cmd)
    return instance_id, proc

def send_board_command(instance_id: str, command: str, payload: dict[str, Any] | None = None) -> Path:
    path = command_file(instance_id)
    current = read_json(path, {})
    seq = int(current.get("seq", 0) or 0) + 1

    write_json(path, {
        "seq": seq,
        "created_at": time.time(),
        "command": command,
        "payload": payload or {},
    })
    return path

def read_board_status(instance_id: str) -> dict[str, Any]:
    return read_json(status_file(instance_id), {})

def kill_board_with_mem(instance_id: str) -> dict[str, Any]:
    """Snapshot, kill, relaunch, and remove temp snapshot after load.

    This is console-side so it can rescue board windows that no longer
    process commands. v0.1.3 boards publish a full snapshot in status.
    """
    status = read_board_status(instance_id)
    pid = status.get("pid")
    snapshot = status.get("snapshot") or {}

    if not snapshot:
        return {
            "passed": False,
            "error": "No board snapshot found. Use v0.1.3 board instances for Kill w/Mem.",
            "old_instance_id": instance_id,
        }

    tmp_dir = BOARD_INSTANCE_DIR / "snapshots"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"killmem_{instance_id}_{int(time.time())}.sboard"
    write_json(tmp_path, snapshot)

    killed = False
    if pid:
        try:
            proc = psutil.Process(int(pid))
            for child in proc.children(recursive=True):
                try:
                    child.kill()
                except Exception:
                    pass
            proc.kill()
            killed = True
        except Exception:
            killed = False

    new_id, proc = launch_board(tmp_path.as_posix(), delete_board_after_load=True)

    return {
        "passed": True,
        "old_instance_id": instance_id,
        "old_pid": pid,
        "killed": killed,
        "snapshot": tmp_path.as_posix(),
        "new_instance_id": new_id,
        "new_pid": proc.pid,
    }
