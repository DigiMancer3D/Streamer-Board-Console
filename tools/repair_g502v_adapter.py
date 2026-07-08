#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
import shutil
import time
from pathlib import Path

def compile_ok(path: Path) -> tuple[bool, str]:
    try:
        py_compile.compile(str(path), doraise=True)
        return True, ""
    except Exception as exc:
        return False, str(exc)

def latest_backup(app_dir: Path) -> Path | None:
    backups = sorted(app_dir.glob("g502viz.py.bak_sbc_*"))
    return backups[-1] if backups else None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default="~/g502 vis")
    parser.add_argument("--restore-latest", action="store_true")
    parser.add_argument("--compile-only", action="store_true")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).expanduser()
    source = app_dir / "g502viz.py"
    backup = latest_backup(app_dir)
    report = {
        "tool": "repair_g502v_adapter",
        "app_dir": str(app_dir),
        "source": str(source),
        "source_exists": source.exists(),
        "latest_backup": str(backup) if backup else "",
        "restored": False,
    }

    if not source.exists():
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    ok, err = compile_ok(source)
    report["current_compile_ok"] = ok
    report["current_compile_error"] = err

    if args.compile_only:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if ok else 1

    if args.restore_latest:
        if not backup:
            report["error"] = "No g502viz.py.bak_sbc_* backup found."
            print(json.dumps(report, indent=2, sort_keys=True))
            return 1

        safety = source.with_suffix(source.suffix + f".broken_sbc_{time.strftime('%Y%m%d_%H%M%S')}")
        shutil.copy2(source, safety)
        shutil.copy2(backup, source)
        ok2, err2 = compile_ok(source)
        report["saved_broken_copy"] = str(safety)
        report["restored_from"] = str(backup)
        report["restored"] = True
        report["restored_compile_ok"] = ok2
        report["restored_compile_error"] = err2
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if ok2 else 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
