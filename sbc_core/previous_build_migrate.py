from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .paths import APP_ROOT, USER_DATA
from .user_data_backup import INCLUDE_DIRS, INCLUDE_FILES, CORE_ADAPTER_FILES, EXCLUDE_TOP_LEVEL

CONSOLE_COPY_DIR = USER_DATA / "console_copies"
CONSOLE_INSTANCE_DIR = USER_DATA / "console_instances"

def find_previous_builds(home: str | Path | None = None) -> dict[str, Any]:
    base = Path(home).expanduser() if home else Path.home()
    current = APP_ROOT.resolve()
    builds = []
    for path in sorted(base.glob("Streamer_Board_Console_MVP_v*")):
        if not path.is_dir():
            continue
        try:
            if path.resolve() == current:
                continue
        except Exception:
            pass
        if not (path / "user_data").exists() and not (path / "adapter_templates").exists():
            continue
        try:
            mtime = path.stat().st_mtime
        except Exception:
            mtime = 0
        builds.append({
            "path": str(path),
            "name": path.name,
            "modified": mtime,
            "has_user_data": (path / "user_data").exists(),
            "has_adapter_templates": (path / "adapter_templates").exists(),
            "has_adapters": (path / "adapters").exists(),
        })
    builds.sort(key=lambda item: item.get("modified", 0), reverse=True)
    return {"ok": True, "builds": builds, "count": len(builds)}

def _iter_previous_items(src_root: Path) -> list[tuple[Path, Path, str]]:
    items: list[tuple[Path, Path, str]] = []

    src_user = src_root / "user_data"
    if src_user.exists():
        for filename in INCLUDE_FILES:
            path = src_user / filename
            if path.is_file():
                items.append((path, USER_DATA / filename, filename))

        for dirname in INCLUDE_DIRS:
            # Console copies are special: they need matching instance roots and path rewriting.
            if dirname == "console_copies":
                continue
            dpath = src_user / dirname
            if not dpath.exists():
                continue
            for path in sorted(dpath.rglob("*")):
                if path.is_file():
                    rel = path.relative_to(src_user)
                    if rel.parts and rel.parts[0] in EXCLUDE_TOP_LEVEL:
                        continue
                    items.append((path, USER_DATA / rel, rel.as_posix()))

    src_templates = src_root / "adapter_templates"
    if src_templates.exists():
        for path in sorted(src_templates.glob("*.json")):
            items.append((path, APP_ROOT / "adapter_templates" / path.name, f"adapter_templates/{path.name}"))

    src_adapters = src_root / "adapters"
    if src_adapters.exists():
        for path in sorted(src_adapters.glob("*.json")):
            if path.name in CORE_ADAPTER_FILES:
                continue
            items.append((path, APP_ROOT / "adapters" / path.name, f"adapters/{path.name}"))

    return items

def _safe_copy_tree(src: Path, dest: Path, *, dry_run: bool) -> int:
    count = 0
    if not src.exists() or not src.is_dir():
        return count
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(src)
        out = dest / rel
        count += 1
        if dry_run:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
    return count

def _looks_packaged_bad(value: str) -> bool:
    return str(value).startswith("/mnt/data/") and not str(APP_ROOT).startswith("/mnt/data/")

def _migrate_console_copies(src_root: Path, *, overwrite: bool, dry_run: bool) -> dict[str, Any]:
    src_console_dir = src_root / "user_data" / "console_copies"
    migrated: list[str] = []
    skipped: list[dict[str, str]] = []
    rewritten: list[str] = []

    if not src_console_dir.exists():
        return {"ok": True, "migrated": migrated, "skipped": skipped, "rewritten": rewritten}

    for src_file in sorted(src_console_dir.glob("*.sbconsole")):
        rel_name = f"console_copies/{src_file.name}"
        try:
            data = json.loads(src_file.read_text(encoding="utf-8"))
        except Exception as exc:
            skipped.append({"item": rel_name, "reason": f"read_error: {exc}"})
            continue

        name = str(data.get("name", ""))
        if name.startswith("Selftest Console Copy"):
            skipped.append({"item": rel_name, "reason": "selftest_console_copy"})
            continue

        if any(_looks_packaged_bad(str(data.get(key, ""))) for key in ("data_root", "adapter_dir", "template_dir", "app_root")):
            skipped.append({"item": rel_name, "reason": "invalid_packaged_path"})
            continue

        cid = str(data.get("console_id") or src_file.stem)
        old_console_root = Path(str(data.get("console_root", ""))).expanduser()
        if not old_console_root.exists():
            # Most older rows pointed into src_root/user_data/console_instances/<id>;
            # reconstruct that path when possible.
            candidate = src_root / "user_data" / "console_instances" / cid
            if candidate.exists():
                old_console_root = candidate

        if not old_console_root.exists():
            skipped.append({"item": rel_name, "reason": "missing_console_instance_root"})
            continue

        new_console_root = USER_DATA / "console_instances" / cid
        new_data_root = new_console_root / "user_data"
        new_adapter_dir = new_console_root / "adapters"
        new_template_dir = new_console_root / "adapter_templates"
        dest_file = USER_DATA / "console_copies" / src_file.name

        if dest_file.exists() and not overwrite:
            skipped.append({"item": rel_name, "reason": "exists_no_overwrite"})
            continue

        migrated.append(rel_name)
        rewritten.append(f"console_instances/{cid}/")
        if dry_run:
            continue

        if new_console_root.exists() and overwrite:
            shutil.rmtree(new_console_root)
        new_console_root.mkdir(parents=True, exist_ok=True)
        _safe_copy_tree(old_console_root, new_console_root, dry_run=False)

        data["app_root"] = str(APP_ROOT)
        data["console_root"] = str(new_console_root)
        data["data_root"] = str(new_data_root)
        data["adapter_dir"] = str(new_adapter_dir)
        data["template_dir"] = str(new_template_dir)
        data["notes"] = "Migrated and re-rooted by SBC previous-build migration."

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    return {"ok": True, "migrated": migrated, "skipped": skipped, "rewritten": rewritten}

def migrate_from_build(src_root: str | Path, overwrite: bool = True, dry_run: bool = False) -> dict[str, Any]:
    src = Path(src_root).expanduser()
    if not src.exists() or not src.is_dir():
        return {"ok": False, "error": f"Previous build folder not found: {src}", "source": str(src)}

    copied: list[str] = []
    skipped: list[str] = []
    for src_path, dest_path, rel in _iter_previous_items(src):
        if dest_path.exists() and not overwrite:
            skipped.append(rel)
            continue
        copied.append(rel)
        if dry_run:
            continue
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dest_path)

    console_copy_result = _migrate_console_copies(src, overwrite=overwrite, dry_run=dry_run)
    copied.extend(console_copy_result.get("migrated", []))

    return {
        "ok": True,
        "source": str(src),
        "dry_run": dry_run,
        "overwrite": overwrite,
        "copied": copied,
        "skipped": skipped,
        "copied_count": len(copied),
        "skipped_count": len(skipped),
        "console_copy_migration": console_copy_result,
    }

def migrate_latest_previous_build(overwrite: bool = True, dry_run: bool = False) -> dict[str, Any]:
    found = find_previous_builds()
    builds = found.get("builds", [])
    if not builds:
        return {"ok": False, "error": "No previous Streamer_Board_Console_MVP_v* folder found.", "found": found}
    result = migrate_from_build(builds[0]["path"], overwrite=overwrite, dry_run=dry_run)
    result["selected_previous_build"] = builds[0]
    return result
