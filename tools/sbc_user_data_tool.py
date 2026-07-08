#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from sbc_core.user_data_backup import create_backup, inspect_backup, import_backup, list_local_backups

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", nargs="?", const="", help="Export user data backup. Optional destination zip.")
    parser.add_argument("--inspect", help="Inspect a backup zip.")
    parser.add_argument("--import", dest="import_path", help="Import a backup zip.")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run import without writing files.")
    parser.add_argument("--no-overwrite", action="store_true", help="Skip files that already exist during import.")
    parser.add_argument("--no-preimport-backup", action="store_true", help="Do not create pre-import backup before import.")
    parser.add_argument("--list-local", action="store_true", help="List local backups in user_data/backups.")
    args = parser.parse_args()

    report = {"tool": "sbc_user_data_tool"}

    if args.export is not None:
        dest = args.export if args.export else None
        report["export_result"] = create_backup(dest)

    if args.inspect:
        report["inspect_result"] = inspect_backup(args.inspect)

    if args.import_path:
        report["import_result"] = import_backup(
            args.import_path,
            overwrite=not args.no_overwrite,
            make_preimport_backup=not args.no_preimport_backup,
            dry_run=args.dry_run,
        )

    if args.list_local:
        report["local_backups"] = list_local_backups()

    if not any([args.export is not None, args.inspect, args.import_path, args.list_local]):
        parser.print_help()
        return 2

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
