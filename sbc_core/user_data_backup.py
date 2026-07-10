from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path
from typing import Any

from .paths import USER_DATA, APP_ROOT

BACKUP_DIR = USER_DATA / "backups"

INCLUDE_DIRS = [
    "profiles",
    "boards",
    "imported_images",
    "app_controls",
    "console_copies",
    "user_dump",
]

INCLUDE_FILES = [
    "current.emoji",
    "active_studio_profile.json",
    "startup_studio_profile.json",
    "sbc_settings.json",
]

# v0.3.8: adapter template work lives outside user_data, so backups must
# preserve it or every new release folder starts with the default templates.
INCLUDE_APP_DIRS = [
    "adapter_templates",
    "adapters",
]

CORE_ADAPTER_FILES = {
    "g502v.json",
    "soundcard.json",
}

# Runtime/noisy/transient data stays out of backups by default.
EXCLUDE_TOP_LEVEL = {
    "logs",
    "cache",
    "web_cache",
    "board_instances",
    "console_instances",
    "backups",
    "__pycache__",
}

MANIFEST_NAME = "sbc_backup_manifest.json"
FORMAT_VERSION = "SBC_USER_DATA_BACKUP_V2"

def timestamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

def backup_default_path() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR / f"sbc_user_data_backup_{timestamp()}.zip"

def _iter_user_data_items() -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []
    USER_DATA.mkdir(parents=True, exist_ok=True)

    for filename in INCLUDE_FILES:
        path = USER_DATA / filename
        if path.exists() and path.is_file():
            items.append((path, f"user_data/{filename}"))

    for dirname in INCLUDE_DIRS:
        dpath = USER_DATA / dirname
        if not dpath.exists():
            continue
        for path in sorted(dpath.rglob("*")):
            if path.is_file():
                rel = path.relative_to(USER_DATA).as_posix()
                parts = rel.split("/")
                if parts and parts[0] in EXCLUDE_TOP_LEVEL:
                    continue
                items.append((path, f"user_data/{rel}"))

    return items

def _iter_adapter_items() -> list[tuple[Path, str]]:
    items: list[tuple[Path, str]] = []

    template_dir = APP_ROOT / "adapter_templates"
    if template_dir.exists():
        for path in sorted(template_dir.glob("*.json")):
            if path.is_file():
                items.append((path, f"adapter_templates/{path.name}"))

    adapter_dir = APP_ROOT / "adapters"
    if adapter_dir.exists():
        for path in sorted(adapter_dir.glob("*.json")):
            if not path.is_file():
                continue
            # Preserve enabled/custom adapters, but do not overwrite the core adapters
            # from a future release with old core adapter files.
            if path.name in CORE_ADAPTER_FILES:
                continue
            items.append((path, f"adapters/{path.name}"))

    return items

def _iter_backup_items() -> list[tuple[Path, str]]:
    seen: set[str] = set()
    out: list[tuple[Path, str]] = []
    for path, rel in _iter_user_data_items() + _iter_adapter_items():
        if rel in seen:
            continue
        seen.add(rel)
        out.append((path, rel))
    return out

def create_backup(dest: str | Path | None = None) -> dict[str, Any]:
    out = Path(dest).expanduser() if dest else backup_default_path()
    out.parent.mkdir(parents=True, exist_ok=True)

    items = _iter_backup_items()
    manifest = {
        "tool": "sbc_user_data_backup",
        "format": FORMAT_VERSION,
        "created_at": time.time(),
        "created_at_text": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app_root": str(APP_ROOT),
        "user_data": str(USER_DATA),
        "include_dirs": INCLUDE_DIRS,
        "include_files": INCLUDE_FILES,
        "include_app_dirs": INCLUDE_APP_DIRS,
        "core_adapter_files_excluded": sorted(CORE_ADAPTER_FILES),
        "excluded_top_level": sorted(EXCLUDE_TOP_LEVEL),
        "item_count": len(items),
        "items": [rel for _path, rel in items],
    }

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True))
        for path, rel in items:
            z.write(path, rel)

    return {
        "ok": True,
        "backup_path": str(out),
        "item_count": len(items),
        "manifest": manifest,
    }

def inspect_backup(zip_path: str | Path) -> dict[str, Any]:
    path = Path(zip_path).expanduser()
    if not path.exists():
        return {"ok": False, "error": f"Backup not found: {path}", "backup_path": str(path)}

    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        manifest = {}
        if MANIFEST_NAME in names:
            try:
                manifest = json.loads(z.read(MANIFEST_NAME).decode("utf-8"))
            except Exception as exc:
                manifest = {"error": str(exc)}
        items = [n for n in names if not n.endswith("/") and n != MANIFEST_NAME]

    return {
        "ok": True,
        "backup_path": str(path),
        "manifest": manifest,
        "item_count": len(items),
        "items": items,
    }

def _safe_json_leaf_path(member: str, prefix: str) -> bool:
    if not member.startswith(prefix + "/"):
        return False
    rel = member[len(prefix) + 1:]
    if not rel or rel.startswith("/") or rel.startswith("\\"):
        return False
    parts = Path(rel).parts
    if ".." in parts:
        return False
    # Keep adapter backups simple and auditable: JSON files only.
    return len(parts) == 1 and parts[0].endswith(".json")

def _is_safe_member(member: str) -> bool:
    if member.startswith("user_data/"):
        rel = member[len("user_data/"):]
        if not rel or rel.startswith("/") or rel.startswith("\\"):
            return False
        parts = Path(rel).parts
        if ".." in parts:
            return False
        if parts and parts[0] in EXCLUDE_TOP_LEVEL:
            return False
        if parts and parts[0] not in set(INCLUDE_DIRS + INCLUDE_FILES):
            return False
        return True

    if _safe_json_leaf_path(member, "adapter_templates"):
        return True

    if _safe_json_leaf_path(member, "adapters"):
        name = Path(member).name
        return name not in CORE_ADAPTER_FILES

    return False

def _dest_for_member(member: str) -> tuple[Path, str]:
    if member.startswith("user_data/"):
        rel = member[len("user_data/"):]
        return USER_DATA / rel, rel
    if member.startswith("adapter_templates/"):
        rel = member
        return APP_ROOT / rel, rel
    if member.startswith("adapters/"):
        rel = member
        return APP_ROOT / rel, rel
    raise ValueError(f"Unsupported backup member: {member}")

def import_backup(zip_path: str | Path, overwrite: bool = True, make_preimport_backup: bool = True, dry_run: bool = False) -> dict[str, Any]:
    path = Path(zip_path).expanduser()
    if not path.exists():
        return {"ok": False, "error": f"Backup not found: {path}", "backup_path": str(path)}

    preimport = None
    if make_preimport_backup and not dry_run:
        preimport = create_backup(BACKUP_DIR / f"pre_import_user_data_{timestamp()}.zip")

    copied: list[str] = []
    skipped: list[str] = []
    rejected: list[str] = []

    with zipfile.ZipFile(path) as z:
        for member in z.namelist():
            if member.endswith("/") or member == MANIFEST_NAME:
                continue
            if not _is_safe_member(member):
                rejected.append(member)
                continue

            dest, rel = _dest_for_member(member)
            if dest.exists() and not overwrite:
                skipped.append(rel)
                continue

            copied.append(rel)
            if dry_run:
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(member) as src, dest.open("wb") as dst:
                shutil_copyfileobj(src, dst)

    return {
        "ok": True,
        "backup_path": str(path),
        "dry_run": dry_run,
        "overwrite": overwrite,
        "preimport_backup": preimport.get("backup_path") if isinstance(preimport, dict) else "",
        "copied": copied,
        "skipped": skipped,
        "rejected": rejected,
        "copied_count": len(copied),
        "skipped_count": len(skipped),
        "rejected_count": len(rejected),
    }

def shutil_copyfileobj(src, dst, length: int = 1024 * 1024) -> None:
    while True:
        buf = src.read(length)
        if not buf:
            break
        dst.write(buf)

def list_local_backups() -> dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backups = []
    for path in sorted(BACKUP_DIR.glob("*.zip")):
        try:
            stat = path.stat()
            backups.append({
                "path": str(path),
                "name": path.name,
                "size_bytes": stat.st_size,
                "modified": stat.st_mtime,
            })
        except Exception:
            continue
    return {
        "ok": True,
        "backup_dir": str(BACKUP_DIR),
        "backups": backups,
        "count": len(backups),
    }
