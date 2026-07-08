#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import py_compile
from pathlib import Path

KEYWORDS = [
    "bind", "keyboard", "hotkey", "key", "press", "release",
    "on_key", "load_settings", "save_settings", "key_force",
    "sbc", "SBCAppBridge"
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default="~/sound card")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).expanduser()
    source = app_dir / "soundcard.py"
    report = {
        "tool": "inspect_soundcard_adapter",
        "app_dir": str(app_dir),
        "source": str(source),
        "exists": source.exists(),
        "compile_ok": False,
        "functions": [],
        "classes": [],
        "keyword_lines": [],
        "backups": [str(p) for p in sorted(app_dir.glob("soundcard.py.bak_sbc_*"))[-8:]],
    }

    if not source.exists():
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

    try:
        py_compile.compile(str(source), doraise=True)
        report["compile_ok"] = True
    except Exception as exc:
        report["compile_error"] = str(exc)

    text = source.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                report["functions"].append({"name": node.name, "lineno": node.lineno})
            elif isinstance(node, ast.ClassDef):
                report["classes"].append({"name": node.name, "lineno": node.lineno})
    except Exception as exc:
        report["ast_error"] = str(exc)

    for idx, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        if any(k.lower() in low for k in KEYWORDS):
            clean = line.strip()
            if clean:
                report["keyword_lines"].append({"line": idx, "text": clean[:220]})

    report["keyword_lines"] = report["keyword_lines"][:180]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
