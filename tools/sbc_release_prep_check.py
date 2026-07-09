#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.release_prep import build_github_upload, inspect_release_folder, latest_release_folder, clean_release_exports, default_release_dir, build_share_bundle, inspect_share_bundle, latest_share_bundle, default_share_zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build or inspect Streamer Board & Console GitHub exports and friend-share bundles.")
    parser.add_argument("--build", nargs="?", const="", help="Build GitHub upload folder. Optional output folder path.")
    parser.add_argument("--share", nargs="?", const="", help="Build friend-share zip. Optional output zip path.")
    parser.add_argument("--inspect-share", nargs="?", const="", help="Inspect friend-share zip. Optional zip path; defaults to latest share zip.")
    parser.add_argument("--inspect", nargs="?", const="", help="Inspect release folder. Optional folder path; defaults to latest/default export.")
    parser.add_argument("--clean", action="store_true", help="Remove generated GitHub upload export folders.")
    parser.add_argument("--default-path", action="store_true", help="Print the default GitHub upload folder path.")
    parser.add_argument("--default-share-path", action="store_true", help="Print the default friend-share zip path.")
    args = parser.parse_args()

    if args.default_path:
        print(json.dumps({"tool": "sbc_release_prep", "default_release_dir": str(default_release_dir())}, indent=2, sort_keys=True))
        return 0

    if args.default_share_path:
        print(json.dumps({"tool": "sbc_release_prep", "default_share_zip": str(default_share_zip_path())}, indent=2, sort_keys=True))
        return 0

    if args.clean:
        print(json.dumps({"tool": "sbc_release_prep", "clean_result": clean_release_exports()}, indent=2, sort_keys=True))
        return 0

    if args.build is not None:
        output = args.build or None
        result = build_github_upload(output)
        print(json.dumps({"tool": "sbc_release_prep", "build_result": result}, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1

    if args.share is not None:
        output = args.share or None
        result = build_share_bundle(output)
        print(json.dumps({"tool": "sbc_release_prep", "share_result": result}, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1

    if args.inspect_share is not None:
        path = args.inspect_share or latest_share_bundle()
        result = inspect_share_bundle(path)
        print(json.dumps({"tool": "sbc_release_prep", "inspect_share_result": result}, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1

    if args.inspect is not None:
        path = args.inspect or latest_release_folder()
        result = inspect_release_folder(path)
        print(json.dumps({"tool": "sbc_release_prep", "inspect_result": result}, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1

    # Friendly default: inspect latest if present, otherwise build default.
    latest = latest_release_folder()
    if latest.exists():
        result = inspect_release_folder(latest)
        print(json.dumps({"tool": "sbc_release_prep", "inspect_result": result}, indent=2, sort_keys=True))
        return 0 if result.get("ok") else 1

    result = build_github_upload()
    print(json.dumps({"tool": "sbc_release_prep", "build_result": result}, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1

if __name__ == "__main__":
    raise SystemExit(main())
