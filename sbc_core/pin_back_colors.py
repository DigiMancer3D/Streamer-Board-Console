from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from .paths import USER_DATA
from .storage import read_json, write_json

DEFAULT_C1 = "#00ff00"
DEFAULT_C2 = "#ff00ff"  # OBS-friendly magenta chroma backer.
STATE_FILE = USER_DATA / "pin_back_colors.json"


def _clamp_channel(value: Any) -> int:
    try:
        return max(0, min(255, int(float(value))))
    except Exception:
        return 0


def rgb_to_hex(r: Any, g: Any, b: Any) -> str:
    return f"#{_clamp_channel(r):02x}{_clamp_channel(g):02x}{_clamp_channel(b):02x}"


def hex_to_rgb(value: str, fallback: str = DEFAULT_C1) -> tuple[int, int, int]:
    value = normalize_hex_color(value, fallback=fallback)
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def normalize_hex_color(value: Any, fallback: str = DEFAULT_C1) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    if text.startswith("rgb"):
        nums = "".join(ch if ch.isdigit() or ch == "," else " " for ch in text).replace(" ", ",")
        parts = [p for p in nums.split(",") if p.strip()]
        if len(parts) >= 3:
            return rgb_to_hex(parts[0], parts[1], parts[2])
    if not text.startswith("#"):
        text = "#" + text
    if len(text) == 4:
        text = "#" + "".join(ch * 2 for ch in text[1:])
    if len(text) != 7:
        text = fallback
    try:
        int(text[1:], 16)
    except Exception:
        text = fallback
    return str(text).lower()


def default_state() -> dict[str, Any]:
    return {
        "version": "pin_back_colors_v1",
        "c1": DEFAULT_C1,
        "c2": DEFAULT_C2,
        "default_pin_back": DEFAULT_C1,
        "default_source": "c1",
        "updated_at": time.time(),
    }


def read_pin_back_state() -> dict[str, Any]:
    data = read_json(STATE_FILE, {})
    if not isinstance(data, dict):
        data = {}
    state = default_state()
    state.update(data)
    state["c1"] = normalize_hex_color(state.get("c1"), DEFAULT_C1)
    state["c2"] = normalize_hex_color(state.get("c2"), DEFAULT_C2)
    state["default_pin_back"] = normalize_hex_color(state.get("default_pin_back"), state["c1"])
    return state


def write_pin_back_state(state: dict[str, Any]) -> dict[str, Any]:
    merged = default_state()
    merged.update(state or {})
    merged["c1"] = normalize_hex_color(merged.get("c1"), DEFAULT_C1)
    merged["c2"] = normalize_hex_color(merged.get("c2"), DEFAULT_C2)
    merged["default_pin_back"] = normalize_hex_color(merged.get("default_pin_back"), merged["c1"])
    merged["updated_at"] = time.time()
    write_json(STATE_FILE, merged)
    return merged


def get_c1() -> str:
    return read_pin_back_state()["c1"]


def get_c2() -> str:
    return read_pin_back_state()["c2"]


def set_c1(color: Any) -> str:
    state = read_pin_back_state()
    state["c1"] = normalize_hex_color(color, DEFAULT_C1)
    write_pin_back_state(state)
    return state["c1"]


def set_c2(color: Any) -> str:
    state = read_pin_back_state()
    state["c2"] = normalize_hex_color(color, DEFAULT_C2)
    write_pin_back_state(state)
    return state["c2"]


def get_default_pin_back() -> str:
    return read_pin_back_state()["default_pin_back"]


def set_default_pin_back(color: Any, source: str = "custom") -> str:
    state = read_pin_back_state()
    state["default_pin_back"] = normalize_hex_color(color, state.get("default_pin_back", DEFAULT_C1))
    state["default_source"] = str(source or "custom")
    write_pin_back_state(state)
    return state["default_pin_back"]


def reset_palette(use: str = "c1") -> dict[str, Any]:
    state = default_state()
    use = str(use or "c1").lower()
    if use == "c2":
        state["default_pin_back"] = DEFAULT_C2
        state["default_source"] = "c2"
    else:
        state["default_pin_back"] = DEFAULT_C1
        state["default_source"] = "c1"
    return write_pin_back_state(state)


class CycleCodeDetector:
    """Detect quick checkbox toggle helper codes.

    A phase is a burst of 2+ clicks with each click no more than about one
    second apart. Phases can be chained by waiting roughly 2-3 seconds between
    bursts. The detector intentionally ignores single clicks so normal C1/C2
    behavior stays immediate.
    """

    CODE_MAP = {
        (2, 2): "SOS",
        (3, 3): "Light-Tower",
        (4, 2, 2): "Reset Colors",
        (4, 3, 2): "Default C2",
        (5, 4, 2): "Use C1",
        (5, 5, 2): "Use C2",
        (5, 5, 5): "Reboot 2",
        (2, 5, 3): "Reboot End EP 2",
    }

    def __init__(self, tk_owner: Any, callback: Callable[[str, tuple[int, ...], str], None]):
        self.tk_owner = tk_owner
        self.callback = callback
        self._state: dict[str, dict[str, Any]] = {}
        self.click_gap_ms = 990
        self.trailing_buffer_ms = 90
        self.sequence_idle_ms = 3600

    def click(self, source: str) -> None:
        now = time.monotonic()
        state = self._state.setdefault(source, {"clicks": [], "phases": [], "burst_job": None, "seq_job": None})
        clicks = state["clicks"]
        if clicks and (now - clicks[-1]) > ((self.click_gap_ms + self.trailing_buffer_ms) / 1000.0):
            self._finalize_burst(source)
            state = self._state[source]
            clicks = state["clicks"]
        clicks.append(now)
        self._cancel_job(state.get("burst_job"))
        state["burst_job"] = self.tk_owner.after(self.click_gap_ms + self.trailing_buffer_ms, lambda s=source: self._finalize_burst(s))

    def _cancel_job(self, job: Any) -> None:
        if not job:
            return
        try:
            self.tk_owner.after_cancel(job)
        except Exception:
            pass

    def _finalize_burst(self, source: str) -> None:
        state = self._state.setdefault(source, {"clicks": [], "phases": [], "burst_job": None, "seq_job": None})
        clicks = state.get("clicks", [])
        state["clicks"] = []
        state["burst_job"] = None
        count = len(clicks)
        if count < 2:
            return
        phases = list(state.get("phases", []))
        phases.append(count)
        phases = phases[-3:]
        state["phases"] = phases
        self._cancel_job(state.get("seq_job"))
        state["seq_job"] = self.tk_owner.after(self.sequence_idle_ms, lambda s=source: self._finalize_sequence(s))

    def _finalize_sequence(self, source: str) -> None:
        state = self._state.setdefault(source, {"clicks": [], "phases": [], "burst_job": None, "seq_job": None})
        phases = tuple(int(x) for x in state.get("phases", []))
        state["phases"] = []
        state["seq_job"] = None
        name = self.CODE_MAP.get(phases)
        if name:
            self.callback(name, phases, source)

class RGBSelectorManager:
    """Single reusable RGB selector window.

    target is an arbitrary dict, for example:
      {"kind": "board", "board_id": "...", "label": "Pin Board ..."}
    """

    def __init__(
        self,
        root: Any,
        apply_callback: Callable[[dict[str, Any], str, bool], None],
        status_callback: Callable[[str], None] | None = None,
        force_close_callback: Callable[[], None] | None = None,
    ):
        self.root = root
        self.apply_callback = apply_callback
        self.status_callback = status_callback
        self.force_close_callback = force_close_callback
        self.target: dict[str, Any] | None = None
        self.pending_target: dict[str, Any] | None = None
        self.window = None
        self.r_var = None
        self.g_var = None
        self.b_var = None
        self.hex_var = None
        self.target_var = None
        self.preview = None
        self.keep_open = False
        self._updating = False

    def is_open(self) -> bool:
        try:
            return bool(self.window and self.window.winfo_exists())
        except Exception:
            return False

    def request(self, target: dict[str, Any], color: Any, keep_open: bool = False) -> None:
        self.pending_target = dict(target or {})
        self.target = dict(target or {})
        self.keep_open = bool(keep_open or self.keep_open)
        self._ensure_window()
        self.set_color(color)
        self._update_target_label()
        try:
            self.window.deiconify()
            self.window.lift()
            self.window.focus_force()
        except Exception:
            pass

    def set_keep_open(self, enabled: bool) -> None:
        self.keep_open = bool(enabled)
        if enabled:
            target = self.pending_target or self.target or {"kind": "default", "label": "Default Pin Back"}
            color = target.get("color") or get_default_pin_back()
            self.request(target, color, keep_open=True)
        else:
            self.close(cancel=True)

    def set_color(self, color: Any) -> None:
        if not self.is_open():
            return
        color = normalize_hex_color(color, get_default_pin_back())
        r, g, b = hex_to_rgb(color)
        self._updating = True
        try:
            self.r_var.set(r)
            self.g_var.set(g)
            self.b_var.set(b)
            self.hex_var.set(color)
            self.preview.configure(bg=color)
        finally:
            self._updating = False

    def color(self) -> str:
        if not self.is_open():
            return get_default_pin_back()
        return rgb_to_hex(self.r_var.get(), self.g_var.get(), self.b_var.get())

    def close(self, cancel: bool = True) -> None:
        if not self.is_open():
            return
        try:
            self.window.destroy()
        except Exception:
            pass
        self.window = None
        if cancel and self.force_close_callback:
            self.force_close_callback()

    def _ensure_window(self) -> None:
        if self.is_open():
            return
        import tkinter as tk
        from tkinter import ttk

        self.window = tk.Toplevel(self.root)
        self.window.title("Pin Back RGB Selector")
        self.window.geometry("380x270+180+180")
        self.window.protocol("WM_DELETE_WINDOW", lambda: self.close(cancel=True))

        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill="both", expand=True)

        self.target_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.target_var, font=("TkDefaultFont", 11, "bold")).pack(anchor="w")

        self.hex_var = tk.StringVar(value=get_default_pin_back())
        self.r_var = tk.IntVar(value=0)
        self.g_var = tk.IntVar(value=255)
        self.b_var = tk.IntVar(value=0)

        for label, var in (("R", self.r_var), ("G", self.g_var), ("B", self.b_var)):
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=3).pack(side="left")
            scale = ttk.Scale(row, from_=0, to=255, variable=var, command=lambda _v: self._from_sliders())
            scale.pack(side="left", fill="x", expand=True, padx=4)
            spin = ttk.Spinbox(row, from_=0, to=255, textvariable=var, width=5, command=self._from_sliders)
            spin.pack(side="left")
            spin.bind("<Return>", lambda _e: self._from_sliders())
            spin.bind("<FocusOut>", lambda _e: self._from_sliders())

        hex_row = ttk.Frame(frame)
        hex_row.pack(fill="x", pady=4)
        ttk.Label(hex_row, text="Hex:").pack(side="left")
        hex_entry = ttk.Entry(hex_row, textvariable=self.hex_var, width=10)
        hex_entry.pack(side="left", padx=4)
        hex_entry.bind("<Return>", lambda _e: self._from_hex())
        hex_entry.bind("<FocusOut>", lambda _e: self._from_hex())
        self.preview = tk.Label(hex_row, text="      ", bg=get_default_pin_back(), relief="sunken")
        self.preview.pack(side="left", padx=8)

        palette = ttk.Frame(frame)
        palette.pack(fill="x", pady=4)
        ttk.Button(palette, text="Load C1", command=lambda: self.set_color(get_c1())).pack(side="left", padx=2)
        ttk.Button(palette, text="Load C2", command=lambda: self.set_color(get_c2())).pack(side="left", padx=2)
        ttk.Button(palette, text="Save as C1", command=self._save_c1).pack(side="left", padx=2)
        ttk.Button(palette, text="Save as C2", command=self._save_c2).pack(side="left", padx=2)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Apply", command=lambda: self.apply(close_after=False)).pack(side="left", padx=2)
        ttk.Button(buttons, text="Apply + Close", command=lambda: self.apply(close_after=True)).pack(side="left", padx=2)
        ttk.Button(buttons, text="Cancel", command=lambda: self.close(cancel=True)).pack(side="left", padx=2)

        self._update_target_label()

    def _update_target_label(self) -> None:
        if self.target_var is None:
            return
        label = "Default Pin Back"
        if self.target:
            label = str(self.target.get("label") or self.target.get("board_id") or self.target.get("kind") or label)
        self.target_var.set(f"Target: {label}")

    def _from_sliders(self) -> None:
        if self._updating or not self.is_open():
            return
        color = rgb_to_hex(self.r_var.get(), self.g_var.get(), self.b_var.get())
        self.hex_var.set(color)
        self.preview.configure(bg=color)

    def _from_hex(self) -> None:
        if self._updating or not self.is_open():
            return
        self.set_color(self.hex_var.get())

    def _save_c1(self) -> None:
        color = set_c1(self.color())
        if self.status_callback:
            self.status_callback(f"Saved {color} as Pin Back C1.")

    def _save_c2(self) -> None:
        color = set_c2(self.color())
        if self.status_callback:
            self.status_callback(f"Saved {color} as Pin Back C2.")

    def apply(self, close_after: bool = False) -> None:
        if not self.is_open():
            return
        target = dict(self.target or self.pending_target or {"kind": "default", "label": "Default Pin Back"})
        color = self.color()
        self.apply_callback(target, color, close_after)
        if close_after or not self.keep_open:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None
            if close_after and self.force_close_callback:
                self.force_close_callback()
