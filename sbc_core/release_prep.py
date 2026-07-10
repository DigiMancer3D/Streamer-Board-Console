from __future__ import annotations

import json
import os
import shutil
import stat
import time
import zipfile
import re
from pathlib import Path
from typing import Any

from .paths import APP_ROOT, USER_DATA

EXPORT_DIR = APP_ROOT / "export"
FORMAT_VERSION = "SBC_PUBLIC_RELEASE_EXPORT_V1"
PUBLIC_RELEASE_MARKER = "SBC_PUBLIC_RELEASE_MANIFEST.json"
FRIEND_SHARE_MARKER = "SBC_FRIEND_SHARE_MANIFEST.json"

EXCLUDE_DIR_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "export",
}

EXCLUDE_USER_DATA_DIRS = {
    "backups",
    "board_instances",
    "cache",
    "console_copies",
    "console_instances",
    "logs",
    "web_cache",
    "user_dump",
}

EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
}

EXCLUDE_FILE_NAMES = {
    ".DS_Store",
}

PUBLIC_ROOT_FILES = {
    "README.md",
    "HOW2_INTEGRATE_ADAPTERS.md",
    "requirements.txt",
    "install_kubuntu.sh",
    "install_desktop_entry.sh",
    "launch_streamer_board_console.sh",
    "launch_streamer_board_console_rescue.sh",
    "launch_pin_board.sh",
    "streamer_board_console.py",
    "pin_board_instance.py",
    "icon.png",
}

PUBLIC_DIRS = {
    "adapters",
    "adapter_templates",
    "boards",
    "patches",
    "sbc_core",
    "tools",
    "user_data",
}


def _now_text() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def package_version() -> str:
    name = APP_ROOT.name
    marker = "Streamer_Board_Console_MVP_"
    if name.startswith(marker):
        return name[len(marker):]
    return "v0_0_0"


def default_release_name() -> str:
    return f"Streamer_Board_Console_GITHUB_UPLOAD_{package_version()}"


def default_release_dir() -> Path:
    return EXPORT_DIR / default_release_name()


def is_public_distribution(root: str | Path | None = None) -> bool:
    """Return True when this copy is a public/share distribution.

    The active developer checkout keeps the GitHub upload builder visible.
    Generated public/share copies include root marker manifests, so the GUI
    hides the developer-only GitHub upload button there.

    Overrides:
    - SBC_PUBLIC_DISTRIBUTION=1 forces public/share mode.
    - SBC_SHOW_GITHUB_BUILDER=1 forces the developer button visible.
    """
    show_override = os.environ.get("SBC_SHOW_GITHUB_BUILDER", "").strip().lower()
    if show_override in {"1", "true", "yes", "on"}:
        return False

    public_override = os.environ.get("SBC_PUBLIC_DISTRIBUTION", "").strip().lower()
    if public_override in {"1", "true", "yes", "on"}:
        return True

    folder = Path(root).expanduser() if root else APP_ROOT
    return (folder / PUBLIC_RELEASE_MARKER).exists() or (folder / FRIEND_SHARE_MARKER).exists()


def _is_excluded(path: Path, rel: Path) -> bool:
    parts = rel.parts
    if any(part in EXCLUDE_DIR_NAMES for part in parts):
        return True
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.suffix in EXCLUDE_FILE_SUFFIXES:
        return True
    if parts and parts[0] == "user_data" and len(parts) >= 2 and parts[1] in EXCLUDE_USER_DATA_DIRS:
        return True
    # Do not publish local console-copy records or generated zip exports.
    if path.suffix == ".zip" and path.parent == APP_ROOT:
        return True
    return False


def _safe_leaf(value: str) -> str:
    out = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value)).strip("_")
    while "__" in out:
        out = out.replace("__", "_")
    return out or "app"


def _private_markers() -> list[str]:
    markers = []
    home = os.environ.get("HOME", "").strip()
    user = os.environ.get("USER", "").strip()
    if home:
        markers.append(home)
    if user:
        markers.append(f"/home/{user}")
    return sorted(set(m for m in markers if m), key=len, reverse=True)


def _sanitize_text_for_release(text: str) -> str:
    data = str(text)
    home = os.environ.get("HOME", "").strip()
    user = os.environ.get("USER", "").strip()
    for marker in _private_markers():
        data = data.replace(marker, "~")
    if user:
        data = data.replace(user, "$USER")
    if home:
        data = data.replace(home, "~")
    data = re.sub(r"/home/[^/\s'\"]+", "~", data)
    data = data.replace("$HOME/<redacted_path>", "~/SBC_APPS/configure_app_path")
    data = data.replace("<redacted_path>", "configure_app_path")
    data = re.sub(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "<email-redacted>", data)
    return data


def _sanitize_default_path(value: Any, app_id: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return raw
    raw = _sanitize_text_for_release(raw)
    if "<redacted_path>" in raw or raw in {"~", "$HOME", "$HOME/<redacted_path>"}:
        return f"~/SBC_APPS/{_safe_leaf(app_id or 'custom_app')}"
    raw = raw.replace("$HOME/", "~/")
    return raw


def _sanitize_json_for_release(value: Any, parent_key: str = "", app_id: str = "") -> Any:
    if isinstance(value, dict):
        local_app_id = str(value.get("app_id") or app_id or "")
        out: dict[str, Any] = {}
        for key, item in value.items():
            skey = str(key)
            if skey == "written":
                out[skey] = []
            elif skey in {"app_root", "user_data", "release_dir", "backup_path"}:
                out[skey] = "<local-path-omitted>"
            elif skey == "default_path":
                out[skey] = _sanitize_default_path(item, local_app_id)
            else:
                out[skey] = _sanitize_json_for_release(item, skey, local_app_id)
        return out
    if isinstance(value, list):
        return [_sanitize_json_for_release(item, parent_key, app_id) for item in value]
    if isinstance(value, str):
        return _sanitize_text_for_release(value)
    return value


def _copy_release_file(src: Path, dest: Path, rel: Path) -> None:
    """Copy a public/share file, sanitizing JSON/text that may contain local paths."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix.lower()
    if suffix in {".json", ".sboard"}:
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            data = _sanitize_json_for_release(data)
            dest.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return
        except Exception:
            pass
    if suffix in {".md", ".txt", ".sh", ".desktop", ".cfg", ".ini", ".toml", ".yaml", ".yml"}:
        try:
            dest.write_text(_sanitize_text_for_release(src.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
            try:
                dest.chmod(src.stat().st_mode)
            except Exception:
                pass
            return
        except Exception:
            pass
    shutil.copy2(src, dest)


def _copy_public_tree(dest: Path) -> tuple[list[str], list[str]]:
    copied: list[str] = []
    skipped: list[str] = []

    for item in sorted(APP_ROOT.iterdir(), key=lambda p: p.name.lower()):
        rel = Path(item.name)
        if item.name.startswith(".") and item.name not in {".gitignore"}:
            skipped.append(str(rel))
            continue
        if item.is_file():
            if item.name.startswith("CHANGELOG_") or item.name in PUBLIC_ROOT_FILES or item.name == ".gitignore":
                if _is_excluded(item, rel):
                    skipped.append(str(rel))
                    continue
                out = dest / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                _copy_release_file(item, out, rel)
                copied.append(str(rel))
            else:
                skipped.append(str(rel))
            continue

        if item.is_dir():
            if item.name not in PUBLIC_DIRS:
                skipped.append(str(rel))
                continue
            for path in sorted(item.rglob("*")):
                r = path.relative_to(APP_ROOT)
                if _is_excluded(path, r):
                    if path.is_file():
                        skipped.append(str(r))
                    continue
                if path.is_dir():
                    continue
                out = dest / r
                out.parent.mkdir(parents=True, exist_ok=True)
                _copy_release_file(path, out, r)
                copied.append(str(r))

    return copied, skipped


def _write_text(path: Path, text: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap_dedent(text), encoding="utf-8")
    if executable:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def textwrap_dedent(text: str) -> str:
    import textwrap
    return textwrap.dedent(text).lstrip("\n").rstrip() + "\n"


def _write_release_docs(dest: Path, manifest: dict[str, Any]) -> list[str]:
    written: list[str] = []
    version = manifest.get("package_version", package_version())

    docs: dict[str, str] = {
        "PUBLIC_RELEASE_CHECKLIST.md": f"""
        # Streamer Board & Console Public Release Checklist ({version})

        Use this folder as the GitHub upload/source folder for the public release.

        ## Before publishing

        1. Run `./install_kubuntu.sh` on a fresh local copy.
        2. Run `./tools/sbc_selftest.sh`.
        3. Run `./tools/sbc_release_prep.py --inspect export/Streamer_Board_Console_GITHUB_UPLOAD_{version}` if you rebuilt the export.
        4. Confirm no private runtime folders are present: `user_data/logs`, `user_data/cache`, `user_data/backups`, `user_data/console_copies`, or `user_data/console_instances`.
        5. Confirm the public adapters are only the safe default core adapters unless intentionally shipping more.
        6. Confirm `HOW2_INTEGRATE_ADAPTERS.md` is present.

        ## Public repo suggestion

        Upload the contents of this folder to a clean GitHub repo. Do not upload old test folders, `.venv`, local logs, or generated console-copy data.
        """,
        "GITHUB_UPLOAD_NOTES.md": f"""
        # GitHub Upload Notes ({version})

        This export was generated by Streamer Board & Console release prep.

        ## What is included

        - Main controller app
        - Pin Board app
        - Core `sbc_core/` modules
        - Public tools and selftests
        - Adapter protocol docs and patch helpers
        - Baseline Soundcard and G502V adapters
        - Default profile/user-data files needed for first launch

        ## What is intentionally excluded

        - `.venv/`
        - Python `__pycache__/` folders
        - Local logs/cache/backups
        - Console Copier runtime instances and `.sbconsole` files
        - Pin Board live runtime state
        - Generated `export/` folders
        """,
        "UPDATE_ORIGINAL_APP_REPOS.md": """
        # Updating Related App Repositories for SBC Support

        These notes are for updating the companion app repositories so they work well with Streamer Board & Console.

        ## Soundcard

        Repo: `$GITHUB_USER/soundcard`

        Minimum public update:

        - Include `sbc_app_bridge.py` or document how SBC copies it in.
        - Keep `soundcard.py` compatible with `SBC_ADAPTER_CONTROL_V1`.
        - Keep `soundcard.control.json` and `sbc_control.json` ignored by Git because they are local runtime files.
        - Keep the app launcher venv-aware.

        SBC-side helper:

        ```bash
        ./tools/soundcard_adapter_safe_cycle.sh
        ```

        ## G502V

        Repo: `$GITHUB_USER/G502V`

        Minimum public update:

        - Include or document `sbc_app_bridge.py` support.
        - Keep `g502viz.py` compatible with `SBC_ADAPTER_CONTROL_V1`.
        - Keep `g502v.control.json` and `sbc_control.json` ignored by Git.
        - Keep the yaw-direction fix based on movement delta rather than absolute cursor position.

        SBC-side helpers:

        ```bash
        ./tools/g502v_adapter_safe_cycle.sh
        ./tools/g502v_yaw_direction_safe_cycle.sh
        ```

        ## Template-only apps

        Bitninja Mocap Lite, Deck Card Widget, and SWAR can start as template-only apps. They only need a stable launch script path. Native hotkey/bridge support can be added later.
        """,
        "RELEASE_NOTES_v0_4_5.md": """
        # Streamer Board & Console v0.4.5 Release Notes

        v0.4.5 adds the public-release preparation workflow.

        Highlights:

        - New Release Prep tooling.
        - GitHub upload folder generation.
        - Public release checklist and upload notes.
        - Companion app update notes for Soundcard, G502V, Bitninja, Deck Card Widget, and SWAR.
        - Cleaner exports that exclude logs, cache, backups, console-copy runtime data, and generated files.
        """,
    }

    for rel, text in docs.items():
        _write_text(dest / rel, text)
        written.append(rel)

    gitignore = """
    .venv/
    __pycache__/
    *.pyc
    *.pyo
    *.log
    .DS_Store

    export/
    user_data/logs/
    user_data/cache/
    user_data/backups/
    user_data/board_instances/
    user_data/console_copies/
    user_data/console_instances/
    user_data/web_cache/
user_data/user_dump/
    """
    _write_text(dest / ".gitignore", gitignore)
    written.append(".gitignore")

    update_dir = dest / "external_app_updates"
    external_docs = {
        "soundcard/SOUNDCARD_SBC_UPDATE.md": """
        # Soundcard SBC Update Notes

        Use these notes when preparing the public Soundcard repo for Streamer Board & Console integration.

        Recommended checks:

        ```bash
        cd /path/to/Streamer_Board_Console
        ./tools/soundcard_adapter_safe_cycle.sh
        ./tools/sbc_adapter_doctor.py
        ```

        Runtime control files such as `sbc_control.json` and `soundcard.control.json` should stay local and ignored by Git.
        """,
        "g502v/G502V_SBC_UPDATE.md": """
        # G502V SBC Update Notes

        Use these notes when preparing the public G502V repo for Streamer Board & Console integration.

        Recommended checks:

        ```bash
        cd /path/to/Streamer_Board_Console
        ./tools/g502v_adapter_safe_cycle.sh
        ./tools/g502v_yaw_direction_safe_cycle.sh
        ./tools/sbc_adapter_doctor.py
        ```

        Runtime control files such as `sbc_control.json` and `g502v.control.json` should stay local and ignored by Git.
        """,
        "bitninja/BITNINJA_TEMPLATE_UPDATE.md": """
        # Bitninja Mocap Lite Template Update Notes

        For now, SBC can manage Bitninja as a template-driven app using a stable launch script.

        Recommended public repo addition:

        ```bash
        run_bitninja_lite_standard.sh
        ```

        Native local/live controls can be added later through the SBC adapter protocol.
        """,
        "deck_card_widget/DECK_CARD_WIDGET_TEMPLATE_UPDATE.md": """
        # Deck Card Widget Template Update Notes

        For now, SBC can manage Deck Card Widget as a template-driven app using a stable launch script.

        Recommended public repo addition:

        ```bash
        launch_deck_card_widget.sh
        ```

        Emoji/theme syncing can be added later through the SBC adapter protocol.
        """,
        "swar/SWAR_TEMPLATE_UPDATE.md": """
        # SWAR Template Update Notes

        SBC can manage SWAR as one or more template entries when multiple launcher states are useful.

        Examples:

        ```bash
        launch_standard.sh
        launch_reader.sh
        ```

        Each launch state can have its own adapter template if needed.
        """,
    }
    for rel, text in external_docs.items():
        _write_text(update_dir / rel, text)
        written.append(str(Path("external_app_updates") / rel))

    script = """
    #!/usr/bin/env bash
    set -euo pipefail
    cd "$(dirname "$0")"
    echo "== SBC public release verify =="
    python3 -m py_compile streamer_board_console.py pin_board_instance.py sbc_core/*.py tools/*.py patches/sbc_app_bridge.py
    ./tools/sbc_runtime_import_check.py >/tmp/sbc_release_runtime_import_check.json
    ./tools/sbc_gui_smoke_check.py >/tmp/sbc_release_gui_smoke_check.json
    echo "PASS: public release verify"
    """
    _write_text(dest / "tools" / "release_verify.sh", script, executable=True)
    written.append("tools/release_verify.sh")

    return written


def build_github_upload(output_dir: str | Path | None = None, *, clean_first: bool = True) -> dict[str, Any]:
    dest = Path(output_dir).expanduser() if output_dir else default_release_dir()
    if clean_first and dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    copied, skipped = _copy_public_tree(dest)
    manifest = {
        "format": FORMAT_VERSION,
        "created_at": time.time(),
        "created_at_text": _now_text(),
        "app_root": "<local-path-omitted>",
        "user_data": "<local-path-omitted>",
        "package_version": package_version(),
        "release_dir": str(dest),
        "copied_count": len(copied),
        "skipped_count": len(skipped),
        "copied": copied,
        "skipped_sample": skipped[:200],
        "excluded_runtime_dirs": sorted(EXCLUDE_USER_DATA_DIRS),
    }
    written_docs = _write_release_docs(dest, manifest)
    manifest["release_docs"] = written_docs
    (dest / "SBC_PUBLIC_RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return {"ok": True, "release_dir": str(dest), "manifest": manifest, "copied_count": len(copied), "release_docs": written_docs}


def inspect_release_folder(path: str | Path | None = None) -> dict[str, Any]:
    folder = Path(path).expanduser() if path else default_release_dir()
    required = [
        "README.md",
        "PUBLIC_RELEASE_CHECKLIST.md",
        "GITHUB_UPLOAD_NOTES.md",
        "UPDATE_ORIGINAL_APP_REPOS.md",
        "HOW2_INTEGRATE_ADAPTERS.md",
        "SBC_PUBLIC_RELEASE_MANIFEST.json",
        "streamer_board_console.py",
        "sbc_core/release_prep.py",
        "tools/sbc_release_prep.py",
        "tools/release_verify.sh",
    ]
    forbidden = [
        ".venv",
        "export",
        "user_data/logs",
        "user_data/cache",
        "user_data/backups",
        "user_data/console_copies",
        "user_data/console_instances",
        "user_data/board_instances",
        "user_data/user_dump",
    ]
    required_status = {rel: (folder / rel).exists() for rel in required}
    forbidden_status = {rel: (folder / rel).exists() for rel in forbidden}
    pycache_found = [str(p.relative_to(folder)) for p in folder.rglob("__pycache__")] if folder.exists() else []
    pyc_found = [str(p.relative_to(folder)) for p in folder.rglob("*.pyc")] if folder.exists() else []
    ok = folder.exists() and all(required_status.values()) and not any(forbidden_status.values()) and not pycache_found and not pyc_found
    return {
        "ok": ok,
        "release_dir": str(folder),
        "exists": folder.exists(),
        "required": required_status,
        "forbidden_present": {k: v for k, v in forbidden_status.items() if v},
        "pycache_found": pycache_found,
        "pyc_found": pyc_found,
    }


def latest_release_folder() -> Path:
    if default_release_dir().exists():
        return default_release_dir()
    if EXPORT_DIR.exists():
        candidates = sorted(EXPORT_DIR.glob("Streamer_Board_Console_GITHUB_UPLOAD_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0]
    return default_release_dir()


def clean_release_exports() -> dict[str, Any]:
    removed: list[str] = []
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    for path in EXPORT_DIR.glob("Streamer_Board_Console_GITHUB_UPLOAD_*"):
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(str(path))
    return {"ok": True, "removed": removed, "removed_count": len(removed), "export_dir": str(EXPORT_DIR)}


SHARE_FORMAT_VERSION = "SBC_FRIEND_SHARE_BUNDLE_V1"


def default_share_name() -> str:
    return f"Streamer_Board_Console_SHAREABLE_{package_version()}_{time.strftime('%Y%m%d_%H%M%S')}"


def default_share_zip_path() -> Path:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORT_DIR / f"{default_share_name()}.zip"


def latest_share_bundle() -> Path:
    if EXPORT_DIR.exists():
        candidates = sorted(EXPORT_DIR.glob("Streamer_Board_Console_SHAREABLE_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return candidates[0]
    return EXPORT_DIR / f"Streamer_Board_Console_SHAREABLE_{package_version()}_NONE.zip"


def _write_friend_share_docs(dest: Path, manifest: dict[str, Any]) -> list[str]:
    docs: list[str] = []
    version = manifest.get("package_version", package_version())
    readme = f"""
    # Streamer Board & Console Friend Share ({version})

    This zip is meant for sharing a runnable, customizable copy of Streamer Board & Console.

    ## What is included

    - Main Streamer Board & Console app files.
    - Pin Board files.
    - Core modules, tools, adapters, and adapter templates.
    - Safe user customization data such as profiles, app controls, boards, emoji, and settings.

    ## What is excluded

    - `.venv/`
    - Python cache files.
    - Logs, backups, and generated export folders.
    - Console-copy runtime instances.
    - Local cache and live board instance data.
    - Personal absolute launch paths.

    ## First run

    ```bash
    chmod +x install_kubuntu.sh launch_streamer_board_console.sh tools/*.sh tools/*.py
    ./install_kubuntu.sh
    ./launch_streamer_board_console.sh
    ```

    ## Friend setup note

    Profiles and adapters are included, but each friend may need to open the adapter/template editor and update app paths so they point to apps on their own computer.
    """
    _write_text(dest / "FRIEND_SHARE_README.md", readme)
    docs.append("FRIEND_SHARE_README.md")
    return docs


def build_share_bundle(output_zip: str | Path | None = None, *, clean_first: bool = True) -> dict[str, Any]:
    """Build a user-shareable zip with safe custom data and without personal paths."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = Path(output_zip).expanduser() if output_zip else default_share_zip_path()
    if zip_path.exists() and clean_first:
        zip_path.unlink()

    build_root = EXPORT_DIR / f".share_build_{int(time.time())}"
    if build_root.exists():
        shutil.rmtree(build_root)
    share_root = build_root / zip_path.stem

    try:
        share_root.mkdir(parents=True, exist_ok=True)
        copied, skipped = _copy_public_tree(share_root)

        manifest = {
            "format": SHARE_FORMAT_VERSION,
            "created_at": time.time(),
            "created_at_text": _now_text(),
            "package_version": package_version(),
            "zip_name": zip_path.name,
            "copied_count": len(copied),
            "skipped_count": len(skipped),
            "copied": copied,
            "skipped_sample": skipped[:200],
            "privacy": {
                "local_paths_omitted": True,
                "emails_redacted": True,
                "runtime_logs_excluded": True,
                "cache_excluded": True,
                "backups_excluded": True,
                "console_runtime_excluded": True,
            },
        }
        docs = _write_friend_share_docs(share_root, manifest)
        manifest["share_docs"] = docs
        (share_root / "SBC_FRIEND_SHARE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        zip_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for path in sorted(share_root.rglob("*")):
                if path.is_file():
                    z.write(path, path.relative_to(build_root))

        inspect = inspect_share_bundle(zip_path)
        return {
            "ok": bool(inspect.get("ok")),
            "zip_path": str(zip_path),
            "copied_count": len(copied),
            "skipped_count": len(skipped),
            "sanitized_files": [rel for rel in copied if rel.endswith((".json", ".md", ".txt", ".sh", ".desktop"))],
            "manifest": manifest,
            "inspect": inspect,
        }
    finally:
        if build_root.exists():
            shutil.rmtree(build_root)


def inspect_share_bundle(path: str | Path | None = None) -> dict[str, Any]:
    zip_path = Path(path).expanduser() if path else latest_share_bundle()
    if not zip_path.exists():
        return {"ok": False, "exists": False, "zip_path": str(zip_path), "error": "share zip not found"}

    required_suffixes = [
        "README.md",
        "FRIEND_SHARE_README.md",
        "SBC_FRIEND_SHARE_MANIFEST.json",
        "streamer_board_console.py",
        "sbc_core/studio_profiles.py",
        "sbc_core/release_prep.py",
        "tools/sbc_release_prep.py",
    ]
    forbidden_parts = [
        ".venv/",
        "__pycache__/",
        "/logs/",
        "/cache/",
        "/backups/",
        "/console_copies/",
        "/console_instances/",
        "/board_instances/",
        "/user_dump/",
        "/export/",
    ]

    private_marker_hits: list[str] = []
    forbidden_present: list[str] = []
    manifest: dict[str, Any] = {}

    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        file_names = [name for name in names if not name.endswith("/")]
        required_status = {rel: any(name.endswith(rel) for name in file_names) for rel in required_suffixes}

        for name in file_names:
            normalized = "/" + name
            if any(part in normalized for part in forbidden_parts):
                forbidden_present.append(name)

            if name.endswith("SBC_FRIEND_SHARE_MANIFEST.json"):
                try:
                    manifest = json.loads(z.read(name).decode("utf-8"))
                except Exception as exc:
                    manifest = {"error": str(exc)}

            if name.endswith((".json", ".md", ".txt", ".sh", ".desktop")):
                try:
                    text = z.read(name).decode("utf-8", errors="replace")
                except Exception:
                    continue
                markers = []
                if re.search(r"/home/[^/\s'\"]+", text):
                    markers.append("/home/<user>")
                if re.search(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text):
                    markers.append("<email>")
                if "$HOME/<redacted_path>" in text:
                    markers.append("$HOME/<redacted_path>")
                if markers:
                    private_marker_hits.append(f"{name}: {', '.join(sorted(set(markers)))}")

    ok = (
        bool(file_names)
        and all(required_status.values())
        and not forbidden_present
        and not private_marker_hits
        and manifest.get("format") == SHARE_FORMAT_VERSION
    )
    return {
        "ok": ok,
        "exists": True,
        "zip_path": str(zip_path),
        "file_count": len(file_names),
        "manifest": manifest,
        "required": required_status,
        "forbidden_present": forbidden_present[:100],
        "private_marker_hits": private_marker_hits[:100],
    }
