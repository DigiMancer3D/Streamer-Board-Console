from __future__ import annotations
from dataclasses import dataclass
import time
import psutil

@dataclass
class ResourceSnapshot:
    pid: int | None
    running: bool
    rss_mb: float
    cpu_percent: float
    children: int

_CPU_LAST: dict[int, tuple[float, float]] = {}

def _proc_cpu_seconds(proc: psutil.Process) -> float:
    t = proc.cpu_times()
    return float(t.user + t.system)

def _process_cpu_percent(procs: list[psutil.Process]) -> float:
    now = time.time()
    total_percent = 0.0
    alive_pids: set[int] = set()

    for proc in procs:
        try:
            pid = int(proc.pid)
            alive_pids.add(pid)
            cpu_s = _proc_cpu_seconds(proc)
            last = _CPU_LAST.get(pid)
            _CPU_LAST[pid] = (now, cpu_s)
            if not last:
                continue
            last_wall, last_cpu_s = last
            wall_delta = max(0.001, now - last_wall)
            cpu_delta = max(0.0, cpu_s - last_cpu_s)
            total_percent += (cpu_delta / wall_delta) * 100.0
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ProcessLookupError, Exception):
            continue

    for pid in list(_CPU_LAST.keys()):
        if pid not in alive_pids and not psutil.pid_exists(pid):
            _CPU_LAST.pop(pid, None)

    return total_percent

def snapshot_process_tree(pid: int | None) -> ResourceSnapshot:
    if not pid:
        return ResourceSnapshot(None, False, 0.0, 0.0, 0)

    try:
        root = psutil.Process(pid)
        procs = [root] + root.children(recursive=True)
        rss = 0
        alive = 0
        alive_procs: list[psutil.Process] = []

        for proc in procs:
            try:
                if proc.is_running():
                    alive += 1
                    alive_procs.append(proc)
                    rss += proc.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ProcessLookupError, Exception):
                continue

        cpu = _process_cpu_percent(alive_procs)
        return ResourceSnapshot(pid, True, rss / (1024 * 1024), cpu, max(0, alive - 1))
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, ProcessLookupError, Exception):
        return ResourceSnapshot(pid, False, 0.0, 0.0, 0)
