#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import py_compile
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

APP_ID = "soundcard"
MARKER = "SBC_ADAPTER_CONTROL_V1"

def backup(path: Path) -> Path:
    out = path.with_suffix(path.suffix + f".bak_sbc_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, out)
    return out

def compile_text_ok(text: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "soundcard_candidate.py"
        tmp.write_text(text, encoding="utf-8")
        try:
            py_compile.compile(str(tmp), doraise=True)
            return True, ""
        except Exception as exc:
            return False, str(exc)

def compile_file_ok(path: Path) -> tuple[bool, str]:
    try:
        py_compile.compile(str(path), doraise=True)
        return True, ""
    except Exception as exc:
        return False, str(exc)

def leading_ws(line: str) -> str:
    return line[:len(line) - len(line.lstrip(" \t"))]

def insert_after_imports(lines: list[str]) -> tuple[list[str], str]:
    if any("from sbc_app_bridge import" in line for line in lines):
        return lines, "bridge imports already present"

    last_import_idx = -1
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            last_import_idx = i
            continue
        # keep scanning through comments/blank lines near imports
        if last_import_idx >= 0 and stripped and not stripped.startswith("#"):
            break

    insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0
    import_lines = [
        "from pathlib import Path\n",
        "from sbc_app_bridge import SBCAppBridge, SBC_ADAPTER_CONTROL_V1\n",
    ]
    return lines[:insert_at] + import_lines + lines[insert_at:], "injected bridge imports"

def find_line_index(lines: list[str], needle: str) -> int:
    for i, line in enumerate(lines):
        if needle in line:
            return i
    return -1

def inject_bridge_init(lines: list[str]) -> tuple[list[str], str]:
    if any("self.sbc_bridge = SBCAppBridge" in line for line in lines):
        return lines, "bridge init already present"

    idx = find_line_index(lines, "self.load_settings()")
    if idx < 0:
        return lines, "could not inject bridge init automatically; self.load_settings() not found"

    indent = leading_ws(lines[idx])
    insert = [
        f"{indent}self.sbc_bridge = SBCAppBridge('soundcard', Path(__file__).parent, default_hotkey_map={{'move_up':'w','move_down':'s','move_left':'a','move_right':'d'}})\n",
        f"{indent}self.sbc_bridge.write_support({{'hotkeys_toggle': True, 'hotkey_remap': True, 'local_live_toggle': False}})\n",
    ]
    return lines[:idx+1] + insert + lines[idx+1:], "injected bridge init"

def find_def_block(lines: list[str], def_name: str) -> tuple[int, int, str] | None:
    pattern = re.compile(rf"^(?P<indent>\s*)def\s+{re.escape(def_name)}\s*\(")
    start = -1
    indent = ""
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            start = i
            indent = m.group("indent")
            break
    if start < 0:
        return None

    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if not stripped:
            continue
        ws = leading_ws(lines[j])
        if len(ws) <= len(indent) and (stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("if __name__")):
            end = j
            break
    return start, end, indent

def replace_method(lines: list[str], def_name: str, body_lines: list[str]) -> tuple[list[str], str]:
    block = find_def_block(lines, def_name)
    if not block:
        return lines, f"could not auto-patch {def_name}; method not found"
    start, end, indent = block
    inner = indent + "    "
    new_block = [f"{indent}def {def_name}(self, event):\n"]
    new_block.extend([inner + line + "\n" for line in body_lines])
    return lines[:start] + new_block + lines[end:], f"patched {def_name}"

def patch_source(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    if MARKER in text and "SBCAppBridge" in text:
        notes.append("entry already appears to contain SBC bridge marker")
        return text, notes

    lines = text.splitlines(keepends=True)

    lines, note = insert_after_imports(lines)
    notes.append(note)

    lines, note = inject_bridge_init(lines)
    notes.append(note)

    press_body = [
        "if hasattr(self, 'sbc_bridge') and not self.sbc_bridge.hotkeys_enabled():",
        "    return",
        "mapping = self.sbc_bridge.hotkey_map() if hasattr(self, 'sbc_bridge') else {}",
        "key = event.keysym.lower()",
        "action_keys = {",
        "    str(mapping.get('move_up', 'w')).lower(): 'w',",
        "    str(mapping.get('move_left', 'a')).lower(): 'a',",
        "    str(mapping.get('move_down', 's')).lower(): 's',",
        "    str(mapping.get('move_right', 'd')).lower(): 'd',",
        "}",
        "if key in action_keys and hasattr(self, 'key_force'):",
        "    self.key_force[action_keys[key]] = 1",
    ]
    lines, note = replace_method(lines, "on_key_press", press_body)
    notes.append(note)

    release_body = [
        "mapping = self.sbc_bridge.hotkey_map() if hasattr(self, 'sbc_bridge') else {}",
        "key = event.keysym.lower()",
        "action_keys = {",
        "    str(mapping.get('move_up', 'w')).lower(): 'w',",
        "    str(mapping.get('move_left', 'a')).lower(): 'a',",
        "    str(mapping.get('move_down', 's')).lower(): 's',",
        "    str(mapping.get('move_right', 'd')).lower(): 'd',",
        "}",
        "if key in action_keys and hasattr(self, 'key_force'):",
        "    self.key_force[action_keys[key]] = 0",
    ]
    lines, note = replace_method(lines, "on_key_release", release_body)
    notes.append(note)

    return "".join(lines), notes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default="~/sound card")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true", help="Patch even if source already has bridge markers.")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).expanduser()
    source = app_dir / "soundcard.py"
    bridge_src = APP_ROOT / "patches" / "sbc_app_bridge.py"

    report = {
        "app": APP_ID,
        "app_dir": str(app_dir),
        "source": str(source),
        "apply": args.apply,
        "passed": False,
        "notes": [],
    }

    if not source.exists():
        report["notes"].append("soundcard.py not found")
        print(json.dumps(report, indent=2))
        return 1

    source_ok, source_err = compile_file_ok(source)
    report["source_compile_ok_before"] = source_ok
    report["source_compile_error_before"] = source_err

    original = source.read_text(encoding="utf-8", errors="ignore")
    if not args.force and MARKER in original and "SBCAppBridge" in original:
        report["notes"].append("source already appears patched; use --force only after backup/restore if needed")
        report["passed"] = source_ok
        print(json.dumps(report, indent=2))
        return 0 if source_ok else 1

    new_text, notes = patch_source(original)
    report["notes"].extend(notes)

    ok, err = compile_text_ok(new_text)
    report["candidate_compile_ok"] = ok
    report["candidate_compile_error"] = err

    if not ok:
        report["passed"] = False
        report["notes"].append("candidate did not compile; source was not modified")
        print(json.dumps(report, indent=2))
        return 1

    if args.apply:
        backup_path = backup(source)
        shutil.copy2(bridge_src, app_dir / "sbc_app_bridge.py")
        source.write_text(new_text, encoding="utf-8")
        support = {
            "protocol": MARKER,
            "app_id": APP_ID,
            "supports": {"hotkeys_toggle": True, "hotkey_remap": True, "local_live_toggle": False},
            "patched_by": "patch_soundcard_adapter.py",
        }
        (app_dir / "sbc_adapter_support.json").write_text(json.dumps(support, indent=2), encoding="utf-8")
        report["backup"] = str(backup_path)
        report["passed"] = True
    else:
        report["passed"] = True
        report["notes"].append("dry run only; rerun with --apply")

    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
