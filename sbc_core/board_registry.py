from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from .paths import APP_ROOT, BOARD_INSTANCE_DIR, BOARD_COMMAND_DIR
from .storage import read_json, write_json

STALE_SECONDS = 10.0
LAUNCH_GRACE_SECONDS = 45.0
DEFAULT_MAX_SLOTS = 64


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
    slot: int = 0
    capture_key: str = ""
    window_class: str = ""

    @property
    def display_name(self) -> str:
        if self.slot > 0:
            return f"Pin Board Slot {self.slot:02d}"
        short = self.instance_id[:8]
        return self.title or f"Pin Board {short}"


def ensure_dirs() -> None:
    BOARD_INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    BOARD_COMMAND_DIR.mkdir(parents=True, exist_ok=True)


def new_instance_id() -> str:
    return uuid.uuid4().hex[:12]


def normalize_slot(value: Any, fallback: int = 0) -> int:
    try:
        slot = int(value)
    except Exception:
        return fallback
    return slot if slot > 0 else fallback


def stable_slot_token(slot: int) -> str:
    """Return a deterministic non-secret token for a Pin Board slot."""
    slot = normalize_slot(slot, 1)
    seed = f"SBC_PIN_BOARD_SLOT_V1:{slot}".encode("utf-8")
    return hashlib.blake2s(seed, digest_size=4).hexdigest().upper()


def capture_key_for_slot(slot: int) -> str:
    slot = normalize_slot(slot, 1)
    return f"PB{slot:02d}-{stable_slot_token(slot)}"


def controller_title_for_slot(slot: int) -> str:
    return f"SBC Pin Board Controller {capture_key_for_slot(slot)}"


def output_title_for_slot(slot: int) -> str:
    return f"SBC Pin Board Output {capture_key_for_slot(slot)}"


def window_class_for_slot(slot: int) -> str:
    slot = normalize_slot(slot, 1)
    return f"SbcPinBoardSlot{slot:02d}"


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


def _status_rows() -> list[tuple[Path, dict[str, Any]]]:
    ensure_dirs()
    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(BOARD_INSTANCE_DIR.glob("*.status.json")):
        data = read_json(path, {})
        if isinstance(data, dict):
            rows.append((path, data))
    return rows


def active_slots(exclude_instance_id: str = "") -> set[int]:
    now = time.time()
    used: set[int] = set()
    for path, data in _status_rows():
        instance_id = str(data.get("instance_id") or path.name.split(".")[0])
        if exclude_instance_id and instance_id == exclude_instance_id:
            continue
        pid_raw = data.get("pid")
        try:
            pid = int(pid_raw) if pid_raw else None
        except Exception:
            pid = None
        heartbeat = float(data.get("heartbeat", 0.0) or 0.0)
        slot = normalize_slot(data.get("slot"), 0)
        if slot <= 0:
            continue
        age = now - heartbeat
        launching = bool(data.get("launching")) and age <= LAUNCH_GRACE_SECONDS
        if pid_running(pid) and (age <= STALE_SECONDS or launching):
            used.add(slot)
    return used


def allocate_board_slot(preferred_slot: int | None = None, *, exclude_instance_id: str = "") -> int:
    used = active_slots(exclude_instance_id=exclude_instance_id)
    preferred = normalize_slot(preferred_slot, 0)
    if preferred > 0 and preferred not in used:
        return preferred

    try:
        max_slots = max(1, int(os.environ.get("SBC_MAX_PIN_BOARD_SLOTS", DEFAULT_MAX_SLOTS)))
    except Exception:
        max_slots = DEFAULT_MAX_SLOTS

    for slot in range(1, max_slots + 1):
        if slot not in used:
            return slot
    raise RuntimeError(f"No free Pin Board slot is available (1-{max_slots}).")


def scan_board_instances(include_stale: bool = False) -> list[BoardInstance]:
    ensure_dirs()
    now = time.time()
    out: list[BoardInstance] = []

    for path, data in _status_rows():
        instance_id = str(data.get("instance_id") or path.name.split(".")[0])
        pid_raw = data.get("pid")
        try:
            pid = int(pid_raw) if pid_raw else None
        except Exception:
            pid = None
        heartbeat = float(data.get("heartbeat", 0.0) or 0.0)
        running_pid = pid_running(pid)
        age = now - heartbeat
        stale = age > STALE_SECONDS
        launching = bool(data.get("launching")) and age <= LAUNCH_GRACE_SECONDS
        running = bool(running_pid and (not stale or launching))
        if not include_stale and not running:
            continue

        slot = normalize_slot(data.get("slot"), 0)
        capture_key = str(data.get("capture_key") or (capture_key_for_slot(slot) if slot else ""))
        window_class = str(data.get("window_class") or (window_class_for_slot(slot) if slot else ""))
        out.append(BoardInstance(
            instance_id=instance_id,
            pid=pid,
            title=str(data.get("title", f"Pin Board {instance_id[:8]}")),
            controller_title=str(data.get("controller_title", "")),
            output_title=str(data.get("output_title", "")),
            board_path=str(data.get("board_path", "")),
            heartbeat=heartbeat,
            status_path=path,
            running=running,
            slot=slot,
            capture_key=capture_key,
            window_class=window_class,
        ))

    out.sort(key=lambda board: (board.slot if board.slot > 0 else 999999, board.instance_id))
    return out


def _placeholder_status(instance_id: str, slot: int, pid: int, board_path: str) -> dict[str, Any]:
    controller_title = controller_title_for_slot(slot)
    output_title = output_title_for_slot(slot)
    capture_key = capture_key_for_slot(slot)
    return {
        "version": "0.1.5-mvp",
        "instance_id": instance_id,
        "pid": pid,
        "slot": slot,
        "capture_key": capture_key,
        "window_class": window_class_for_slot(slot),
        "title": f"Pin Board Slot {slot:02d}",
        "controller_title": controller_title,
        "output_title": output_title,
        "board_path": board_path,
        "heartbeat": time.time(),
        "launching": True,
        "pin_count": 0,
        "pins": [],
    }


def launch_board(
    board_path: str = "",
    delete_board_after_load: bool = False,
    preferred_slot: int | None = None,
) -> tuple[str, subprocess.Popen]:
    ensure_dirs()
    instance_id = new_instance_id()
    slot = allocate_board_slot(preferred_slot)
    script = APP_ROOT / "pin_board_instance.py"
    cmd = [
        sys.executable,
        str(script),
        "--instance-id",
        instance_id,
        "--slot",
        str(slot),
    ]
    if board_path:
        cmd.extend(["--board", board_path])
    if delete_board_after_load:
        cmd.append("--delete-board-after-load")

    env = dict(os.environ)
    env["SBC_PIN_BOARD_SLOT"] = str(slot)
    env["SBC_PIN_CAPTURE_KEY"] = capture_key_for_slot(slot)
    env["SBC_PIN_CONTROLLER_TITLE"] = controller_title_for_slot(slot)
    env["SBC_PIN_OUTPUT_TITLE"] = output_title_for_slot(slot)
    # The installed Tk identity shim reads this before Tk() is created.
    # A slot-specific class gives KDE/OBS a stable target across relaunches.
    env["DIGIMANCER_TK_CLASS"] = window_class_for_slot(slot)

    proc = subprocess.Popen(cmd, env=env)
    write_json(status_file(instance_id), _placeholder_status(instance_id, slot, proc.pid, board_path))
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
    data = read_json(status_file(instance_id), {})
    return data if isinstance(data, dict) else {}


def _kill_process_tree(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        proc = psutil.Process(int(pid))
        for child in proc.children(recursive=True):
            try:
                child.kill()
            except Exception:
                pass
        proc.kill()
        try:
            proc.wait(timeout=2.0)
        except Exception:
            pass
        return True
    except Exception:
        return False


def _remove_runtime_files(instance_id: str) -> None:
    for path in (status_file(instance_id), command_file(instance_id)):
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


def kill_board_with_mem(instance_id: str) -> dict[str, Any]:
    """Snapshot, kill, and relaunch a board in the same stable OBS slot."""
    status = read_board_status(instance_id)
    pid = status.get("pid")
    slot = normalize_slot(status.get("slot"), 0)
    snapshot = status.get("snapshot") or {}
    if not snapshot:
        return {
            "passed": False,
            "error": "No board snapshot found. The Pin Board must publish a current snapshot before Kill w/Mem.",
            "old_instance_id": instance_id,
        }

    tmp_dir = BOARD_INSTANCE_DIR / "snapshots"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"killmem_{instance_id}_{int(time.time())}.sboard"
    write_json(tmp_path, snapshot)

    killed = _kill_process_tree(int(pid) if pid else None)
    _remove_runtime_files(instance_id)

    try:
        new_id, proc = launch_board(
            tmp_path.as_posix(),
            delete_board_after_load=True,
            preferred_slot=slot or None,
        )
    except Exception as exc:
        return {
            "passed": False,
            "error": f"Board was stopped but relaunch failed: {exc}",
            "old_instance_id": instance_id,
            "old_pid": pid,
            "killed": killed,
            "slot": slot,
            "snapshot": tmp_path.as_posix(),
        }

    return {
        "passed": True,
        "old_instance_id": instance_id,
        "old_pid": pid,
        "killed": killed,
        "snapshot": tmp_path.as_posix(),
        "new_instance_id": new_id,
        "new_pid": proc.pid,
        "slot": slot,
        "capture_key": capture_key_for_slot(slot) if slot else "",
    }
