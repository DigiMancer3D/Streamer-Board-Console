from __future__ import annotations

import json
import os
import shutil
import stat
import time
from pathlib import Path
from typing import Any

from .paths import APP_ROOT, USER_DATA

EXPORT_DIR = APP_ROOT / "export"
FORMAT_VERSION = "SBC_PUBLIC_RELEASE_EXPORT_V1"

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
                shutil.copy2(item, out)
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
                shutil.copy2(path, out)
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

        Repo: `DigiMancer3D/soundcard`

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

        Repo: `DigiMancer3D/G502V`

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
        "app_root": str(APP_ROOT),
        "user_data": str(USER_DATA),
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
