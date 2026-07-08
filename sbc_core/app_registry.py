from __future__ import annotations
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import psutil

from .paths import ADAPTER_DIR, APP_ROOT, LOG_DIR, expand_user_path
from .adapter_control import write_app_control, build_control_payload

@dataclass
class StreamerApp:
    app_id: str
    display_name: str
    default_path: str
    launch_mode: str
    entry_file: str
    settings_files: list[str]
    control_file: str
    supports: dict[str, Any]
    default_hotkeys: list[dict[str, str]]
    process: subprocess.Popen | None = field(default=None, repr=False)
    suspended: bool = False
    log_handle: Any = field(default=None, repr=False)

    @property
    def app_path(self) -> Path:
        return expand_user_path(self.default_path)

    @property
    def pid(self) -> int | None:
        if self.process and self.process.poll() is None:
            return self.process.pid
        pids = self.external_pids()
        return pids[0] if pids else None

    def external_pids(self) -> list[int]:
        """Find already-running app processes not owned by this StreamerApp object.

        v0.3.4: This is deliberately defensive. Earlier builds used
        psutil.process_iter(attrs=[...]), which can raise while the iterator
        is fetching process info. That could surface as a Tk callback traceback
        during resource refresh if a process exits at just the wrong time.
        """
        now = time.time()
        cached_at = float(getattr(self, "_external_pid_cache_at", 0.0) or 0.0)
        cached = list(getattr(self, "_external_pid_cache", []) or [])
        if now - cached_at < 1.25:
            return cached

        out: list[int] = []
        try:
            app_path = self.app_path.resolve()
        except Exception:
            app_path = self.app_path

        entry = self.entry_file
        current_pid = os.getpid()

        try:
            iterator = psutil.process_iter()
        except Exception:
            iterator = []

        for proc in iterator:
            try:
                pid = int(getattr(proc, "pid", 0) or 0)
                if pid <= 0 or pid == current_pid:
                    continue

                try:
                    cmdline = proc.cmdline()
                except Exception:
                    cmdline = []
                cmd = " ".join(str(part) for part in cmdline)
                if entry not in cmd:
                    continue

                cwd_ok = False
                try:
                    cwd = proc.cwd()
                    if cwd:
                        cwd_ok = Path(cwd).resolve() == app_path
                except Exception:
                    cwd_ok = False

                cmd_ok = str(app_path) in cmd
                if cwd_ok or cmd_ok:
                    out.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue

        out = sorted(set(out))
        self._external_pid_cache = out
        self._external_pid_cache_at = now
        return out

    @property
    def log_path(self) -> Path:
        return LOG_DIR / f"{self.app_id}.log"

    def command(self) -> list[str]:
        if self.launch_mode == "venv_python":
            script = self.entry_file
            return [
                "bash",
                "-lc",
                f'cd "{self.app_path}" && '
                f'if [ -d venv ]; then source venv/bin/activate; fi && '
                f'python3 "{script}"'
            ]
        return ["bash", "-lc", f'cd "{self.app_path}" && ./"{self.entry_file}"']

    def _open_log(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.log_handle = self.log_path.open("ab", buffering=0)
        stamp = f"\n\n--- {self.display_name} launch {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n".encode("utf-8")
        self.log_handle.write(stamp)
        return self.log_handle

    def log_tail(self, lines: int = 40) -> str:
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")
            return "\n".join(text.splitlines()[-lines:])
        except Exception:
            return ""

    def launch(self) -> str:
        if self.pid:
            return f"{self.display_name} is already running."
        if not self.app_path.exists():
            return f"Path missing: {self.app_path}"

        log = self._open_log()
        self.process = subprocess.Popen(
            self.command(),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.suspended = False

        # Fast-exit detection catches broken patches/import errors.
        time.sleep(0.45)
        rc = self.process.poll()
        if rc is not None:
            tail = self.log_tail(12)
            self.process = None
            msg = f"{self.display_name} exited immediately with code {rc}. See log: {self.log_path}"
            if tail:
                msg += "\nLast log lines:\n" + tail
            return msg

        return f"Launched {self.display_name}. Logs: {self.log_path}"

    def _process_tree(self) -> list[psutil.Process]:
        if not self.pid:
            return []
        try:
            proc = psutil.Process(self.pid)
            return [proc] + proc.children(recursive=True)
        except Exception:
            return []

    def close(self, timeout: float = 4.0) -> str:
        if not self.pid:
            return f"{self.display_name} is not running."

        procs = self._process_tree()
        if not procs:
            self.process = None
            return f"{self.display_name} is not running."

        for proc in reversed(procs):
            try:
                proc.terminate()
            except Exception:
                pass

        _gone, alive = psutil.wait_procs(procs, timeout=timeout)
        if alive:
            for proc in alive:
                try:
                    proc.kill()
                except Exception:
                    pass
            psutil.wait_procs(alive, timeout=1.0)
            self.process = None
            self.suspended = False
            return f"Force-killed stuck {self.display_name} after close timeout."

        self.process = None
        self.suspended = False
        return f"Closed {self.display_name}."

    def force_kill(self) -> str:
        if not self.pid:
            return f"{self.display_name} is not running."
        procs = self._process_tree()
        for proc in reversed(procs):
            try:
                proc.kill()
            except Exception:
                pass
        try:
            psutil.wait_procs(procs, timeout=1.0)
        except Exception:
            pass
        self.process = None
        self.suspended = False
        return f"Force-killed {self.display_name}."

    def restart(self) -> str:
        msg = self.close()
        self.process = None
        launch_msg = self.launch()
        return msg + "\n" + launch_msg

    def pause_park(self) -> str:
        if not self.pid:
            return f"{self.display_name} is not running."
        try:
            for item in self._process_tree():
                item.suspend()
            self.suspended = True
            return f"Pause & Park applied to {self.display_name}. OBS capture may freeze or break, which is expected."
        except Exception as exc:
            return f"Pause & Park failed for {self.display_name}: {exc}"

    def resume(self) -> str:
        if not self.pid:
            return f"{self.display_name} is not running."
        try:
            for item in self._process_tree():
                item.resume()
            self.suspended = False
            return f"Resumed {self.display_name}."
        except Exception as exc:
            return f"Resume failed for {self.display_name}: {exc}"

    def write_control(self, hotkeys_enabled: bool | None = None, hotkey_map: dict[str, str] | None = None) -> Path:
        rel = Path(self.control_file)
        central_path = APP_ROOT / rel if not rel.is_absolute() else rel
        enabled = True if hotkeys_enabled is None else bool(hotkeys_enabled)
        payload = build_control_payload(self, hotkeys_enabled=enabled, hotkey_map=hotkey_map or {}, mode="local")
        write_app_control(self, payload)
        return central_path

def load_apps() -> dict[str, StreamerApp]:
    apps: dict[str, StreamerApp] = {}
    for path in sorted(ADAPTER_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        app = StreamerApp(
            app_id=data["app_id"],
            display_name=data["display_name"],
            default_path=data["default_path"],
            launch_mode=data.get("launch_mode", "venv_python"),
            entry_file=data["entry_file"],
            settings_files=data.get("settings_files", []),
            control_file=data.get("control_file", f"user_data/app_controls/{data['app_id']}.control.json"),
            supports=data.get("supports", {}),
            default_hotkeys=data.get("default_hotkeys", []),
        )
        apps[app.app_id] = app
    return apps
