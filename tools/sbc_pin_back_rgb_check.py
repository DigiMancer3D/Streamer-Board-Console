#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"PASS: {message}")
    else:
        print(f"FAIL: {message}")
        failures.append(message)


def contains(path: Path, text: str) -> bool:
    return text in path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    failures: list[str] = []
    console = APP_ROOT / "streamer_board_console.py"
    board = APP_ROOT / "pin_board_instance.py"
    core = APP_ROOT / "sbc_core" / "pin_back_colors.py"

    require(console.exists(), "console file exists", failures)
    require(board.exists(), "pin board instance file exists", failures)
    require(core.exists(), "pin back color core module exists", failures)

    if console.exists():
        require(contains(console, '"Pin Back (RGB)"'), "console has selected-board Pin Back button", failures)
        require(contains(console, '"Pin Backs (RBG)"'), "console has all-boards Pin Backs button", failures)
        require(contains(console, 'broadcast_pin_back_color'), "console can broadcast pin back color", failures)
        require(contains(console, '"set_pin_back"'), "console sends set_pin_back commands", failures)

    if board.exists():
        require(contains(board, '"Pin Back (RGB)"'), "pin board controller has Pin Back button", failures)
        require(contains(board, 'set_pin_back_color'), "pin board can set own pin back", failures)
        require(contains(board, '"set_pin_back"'), "pin board receives set_pin_back command", failures)
        require(contains(board, '"pin_back"'), "pin board publishes pin_back status", failures)

    if core.exists():
        sys.path.insert(0, str(APP_ROOT))
        from sbc_core.pin_back_colors import DEFAULT_C1, DEFAULT_C2, normalize_hex_color, rgb_to_hex, hex_to_rgb, CycleCodeDetector

        require(DEFAULT_C1 == "#00ff00", "C1 default is green", failures)
        require(DEFAULT_C2 == "#ff00ff", "C2 default is OBS magenta", failures)
        require(normalize_hex_color("00FF00") == "#00ff00", "hex normalization works", failures)
        require(rgb_to_hex(255, 0, 255) == "#ff00ff", "rgb_to_hex works", failures)
        require(hex_to_rgb("#00ff00") == (0, 255, 0), "hex_to_rgb works", failures)
        require(CycleCodeDetector.CODE_MAP.get((2, 2)) == "SOS", "SOS cycle code present", failures)
        require(CycleCodeDetector.CODE_MAP.get((3, 3)) == "Light-Tower", "Light-Tower cycle code present", failures)
        require(CycleCodeDetector.CODE_MAP.get((4, 2, 2)) == "Reset Colors", "Reset Colors cycle code present", failures)
        require(CycleCodeDetector.CODE_MAP.get((4, 3, 2)) == "Default C2", "Default C2 cycle code present", failures)
        require(CycleCodeDetector.CODE_MAP.get((5, 4, 2)) == "Use C1", "Use C1 cycle code present", failures)
        require(CycleCodeDetector.CODE_MAP.get((5, 5, 2)) == "Use C2", "Use C2 cycle code present", failures)
        require(CycleCodeDetector.CODE_MAP.get((5, 5, 5)) == "Reboot 2", "Reboot 2 cycle code present", failures)
        require(CycleCodeDetector.CODE_MAP.get((2, 5, 3)) == "Reboot End EP 2", "Reboot End EP 2 cycle code present", failures)

    if failures:
        print("\nOverall: FAIL")
        return 1
    print("\nOverall: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
