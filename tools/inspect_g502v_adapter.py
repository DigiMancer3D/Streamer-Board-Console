#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

KEYWORDS = [
    "bind", "keyboard", "hotkey", "key", "press", "release",
    "mapping", "mappings", "on_key", "listener", "pynput"
]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default="~/g502 vis")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).expanduser()
    source = app_dir / "g502viz.py"
    report = {
        "tool": "inspect_g502v_adapter",
        "app_dir": str(app_dir),
        "source": str(source),
        "exists": source.exists(),
        "functions": [],
        "classes": [],
        "keyword_lines": [],
        "recommendation": "Paste this report back so the next patch can hook G502V safely.",
    }

    if not source.exists():
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1

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
        if any(k in low for k in KEYWORDS):
            clean = line.strip()
            if clean:
                report["keyword_lines"].append({"line": idx, "text": clean[:220]})

    report["keyword_lines"] = report["keyword_lines"][:160]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
