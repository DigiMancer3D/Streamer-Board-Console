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

PATCH_MARKER = "G502V_YAW_DIRECTION_DELTA_V1"

def backup(path: Path) -> Path:
    out = path.with_suffix(path.suffix + f".bak_yaw_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, out)
    return out

def compile_text_ok(text: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "g502viz_yaw_candidate.py"
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
        if len(ws) <= len(indent) and (
            stripped.startswith("def ")
            or stripped.startswith("class ")
            or stripped.startswith("if __name__")
        ):
            end = j
            break
    return start, end, indent

def inject_state(lines: list[str]) -> tuple[list[str], str]:
    if any("_last_yaw_screen_xy" in line for line in lines):
        return lines, "yaw movement state already present"

    # Prefer inserting near the mouse handoff fields.
    insert_after = -1
    for i, line in enumerate(lines):
        if "self._latest_mouse_xy = None" in line:
            insert_after = i
            break
    if insert_after < 0:
        for i, line in enumerate(lines):
            if "self.yaw_current_angle" in line:
                insert_after = i
                break
    if insert_after < 0:
        return lines, "could not inject yaw movement state; anchor not found"

    indent = leading_ws(lines[insert_after])
    insert = [
        f"{indent}self._last_yaw_screen_xy = None\n",
        f"{indent}self._yaw_motion_deadzone_px = 1.5\n",
    ]
    return lines[:insert_after+1] + insert + lines[insert_after+1:], "injected yaw movement state"

def replace_update_yaw(lines: list[str]) -> tuple[list[str], str]:
    block = find_def_block(lines, "update_yaw_from_screen_xy")
    if not block:
        return lines, "could not replace update_yaw_from_screen_xy; method not found"

    start, end, indent = block
    inner = indent + "    "
    new_block = [
        f"{indent}def update_yaw_from_screen_xy(self, x, y):\n",
        f"{inner}\"\"\"Update yaw dot from mouse movement direction, not cursor location.\n",
        f"{inner}\n",
        f"{inner}{PATCH_MARKER}\n",
        f"{inner}The previous implementation pointed at the absolute cursor position\n",
        f"{inner}relative to the ring center. This version uses the movement delta\n",
        f"{inner}between the newest and previous global mouse coordinates, so one\n",
        f"{inner}north/southwest/etc. movement immediately moves the dot to that\n",
        f"{inner}direction and then sticks there until a new movement direction arrives.\n",
        f"{inner}\"\"\"\n",
        f"{inner}if not self.yaw_visible or not self.yaw_dot_visible or not hasattr(self, \"yaw_dot\"):\n",
        f"{inner}    return\n",
        f"{inner}try:\n",
        f"{inner}    prev = getattr(self, \"_last_yaw_screen_xy\", None)\n",
        f"{inner}    self._last_yaw_screen_xy = (x, y)\n",
        f"{inner}    if prev is None:\n",
        f"{inner}        return\n",
        f"{inner}\n",
        f"{inner}    dx = x - prev[0]\n",
        f"{inner}    dy = y - prev[1]\n",
        f"{inner}    deadzone = float(getattr(self, \"_yaw_motion_deadzone_px\", 1.5))\n",
        f"{inner}    if (dx * dx + dy * dy) < (deadzone * deadzone):\n",
        f"{inner}        return\n",
        f"{inner}\n",
        f"{inner}    angle = math.atan2(dy, dx)\n",
        f"{inner}    self.yaw_current_angle = angle\n",
        f"{inner}\n",
        f"{inner}    dot_x = self.yaw_center_x + math.cos(angle) * self.yaw_ring_radius\n",
        f"{inner}    dot_y = self.yaw_center_y + math.sin(angle) * self.yaw_ring_radius\n",
        f"{inner}\n",
        f"{inner}    self.canvas.coords(\n",
        f"{inner}        self.yaw_dot,\n",
        f"{inner}        dot_x - self.yaw_dot_size/2, dot_y - self.yaw_dot_size/2,\n",
        f"{inner}        dot_x + self.yaw_dot_size/2, dot_y + self.yaw_dot_size/2\n",
        f"{inner}    )\n",
        f"{inner}except Exception:\n",
        f"{inner}    pass\n",
    ]
    return lines[:start] + new_block + lines[end:], "replaced yaw update with movement-direction delta mode"

def reset_baseline_on_visibility(lines: list[str]) -> tuple[list[str], str]:
    # Make show/hide/visibility changes reset the baseline so first movement after
    # toggling does not use a stale coordinate.
    marker = "# Reset yaw motion baseline after visibility/settings changes"
    if any(marker in line for line in lines):
        return lines, "yaw baseline reset already present"

    block = find_def_block(lines, "update_yaw_visibility")
    if not block:
        return lines, "could not patch update_yaw_visibility; method not found"

    start, end, indent = block
    body_indent = indent + "    "
    insert_at = end
    insert = [
        f"{body_indent}{marker}\n",
        f"{body_indent}try:\n",
        f"{body_indent}    self._last_yaw_screen_xy = None\n",
        f"{body_indent}except Exception:\n",
        f"{body_indent}    pass\n",
    ]
    return lines[:insert_at] + insert + lines[insert_at:], "patched yaw baseline reset"

def patch_source(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    lines = text.splitlines(keepends=True)

    if PATCH_MARKER in text:
        notes.append("yaw direction delta patch already present")
        return text, notes

    lines, note = inject_state(lines)
    notes.append(note)

    lines, note = replace_update_yaw(lines)
    notes.append(note)

    lines, note = reset_baseline_on_visibility(lines)
    notes.append(note)

    return "".join(lines), notes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default="~/g502 vis")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    app_dir = Path(args.app_dir).expanduser()
    source = app_dir / "g502viz.py"

    report = {
        "tool": "patch_g502v_yaw_direction",
        "app_dir": str(app_dir),
        "source": str(source),
        "apply": args.apply,
        "passed": False,
        "notes": [],
    }

    if not source.exists():
        report["notes"].append("g502viz.py not found")
        print(json.dumps(report, indent=2))
        return 1

    source_ok, source_err = compile_file_ok(source)
    report["source_compile_ok_before"] = source_ok
    report["source_compile_error_before"] = source_err

    original = source.read_text(encoding="utf-8", errors="ignore")
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
        source.write_text(new_text, encoding="utf-8")
        report["backup"] = str(backup_path)
        report["passed"] = True
    else:
        report["passed"] = True
        report["notes"].append("dry run only; rerun with --apply")

    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
