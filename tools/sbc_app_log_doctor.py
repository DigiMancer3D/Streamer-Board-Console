#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]

def read_tail(path: Path, lines: int = 120) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])

def classify(text: str) -> list[str]:
    out = []
    if "Traceback (most recent call last)" in text:
        out.append("traceback_detected")
    if "SyntaxError" in text:
        out.append("syntax_error")
    if "IndentationError" in text:
        out.append("indentation_error")
    if "NameError" in text:
        out.append("name_error")
    if "ModuleNotFoundError" in text:
        out.append("module_not_found")
    if "SBCAppBridge" in text or "sbc_app_bridge" in text:
        out.append("sbc_bridge_related")
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("app", nargs="?", default="soundcard")
    args = parser.parse_args()

    log_path = APP_ROOT / "user_data" / "logs" / f"{args.app}.log"
    tail = read_tail(log_path)
    report = {
        "tool": "sbc_app_log_doctor",
        "app": args.app,
        "log_path": str(log_path),
        "exists": log_path.exists(),
        "classifications": classify(tail),
        "tail": tail,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
