#!/usr/bin/env python3
"""Patch Streamer Board Console app_registry.py for repo-safe child identities.

Run from the Streamer Board Console repo root after copying this kit in:

    python3 tools/app_registry_repo_safe_patch.py

This inserts a safe import and rewrites StreamerApp.command() to prefix child
launcher commands with desktop identity exports from sbc_core.desktop_identity.
"""
from __future__ import annotations

from pathlib import Path

path = Path("sbc_core/app_registry.py")
text = path.read_text(encoding="utf-8", errors="replace")

if "import shlex" not in text:
    text = text.replace("import os\n", "import os\nimport shlex\n")

if "from .desktop_identity import shell_prefix_for_app_id" not in text:
    marker = "from .adapter_control import write_app_control, build_control_payload\n"
    text = text.replace(marker, marker + "from .desktop_identity import shell_prefix_for_app_id\n")

start = text.find("    def command(self) -> list[str]:")
if start < 0:
    raise SystemExit("Could not find StreamerApp.command()")

end = text.find("    def _open_log", start)
if end < 0:
    raise SystemExit("Could not find method after StreamerApp.command()")

new_block = r'''    def command(self) -> list[str]:
        prefix = shell_prefix_for_app_id(self.app_id)
        app_path = shlex.quote(str(self.app_path))
        entry = shlex.quote(str(self.entry_file))

        if self.launch_mode == "venv_python":
            return [
                "bash",
                "-lc",
                f"{prefix}cd {app_path} && "
                f"if [ -d venv ]; then source venv/bin/activate; fi && "
                f"python3 {entry}",
            ]

        return ["bash", "-lc", f"{prefix}cd {app_path} && ./{entry}"]

'''

text = text[:start] + new_block + text[end:]
path.write_text(text, encoding="utf-8")
print("Patched sbc_core/app_registry.py for repo-safe desktop identity.")
