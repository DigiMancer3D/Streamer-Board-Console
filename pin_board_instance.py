#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import time
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from sbc_core.image_cache import PinImageState, StickyImageRenderer
from sbc_core.storage import read_json, write_json
from sbc_core.paths import BOARD_DIR
from sbc_core.board_registry import status_file, command_file
from sbc_core.ui_wrap import FlowFrame
from sbc_core.pin_back_colors import (
    DEFAULT_C1,
    DEFAULT_C2,
    CycleCodeDetector,
    RGBSelectorManager,
    get_c1,
    get_c2,
    get_default_pin_back,
    normalize_hex_color,
    reset_palette,
    set_default_pin_back,
)

ANIMATION_PRESETS = ["pulse", "float", "slow-spin", "shake", "fade-in-out", "slide-left-right"]

class PinBoardApp:
    def __init__(self, board_path: Path | None = None, instance_id: str | None = None, delete_board_after_load: bool = False):
        self.instance_id = instance_id or uuid.uuid4().hex[:12]
        self.capture_w = 1920
        self.capture_h = 1080
        self.output_scale = 0.5
        self.chroma_key = get_default_pin_back()
        self.resource_mode = "Static"
        self.anim_fps = 0
        self.locked = False
        self.controller_topmost = False
        self.output_topmost = False
        self.output_topmost_armed = False
        self.board_path = board_path
        self.delete_board_after_load = delete_board_after_load
        self.pins: list[PinImageState] = []
        self.selected_id: str | None = None
        self.renderer = StickyImageRenderer()
        self.output_image_refs = []
        self.drag_start = None
        self.anim_phase = 0.0
        self.animation_job = None
        self.last_command_seq = 0

        self.root = tk.Tk()
        self.root.title(f"Streamer Board - Controller - {self.instance_id}")
        self.root.geometry("1120x760+180+120")
        self.root.minsize(720, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.close_instance)

        self.pin_back_rgb = RGBSelectorManager(
            self.root,
            self.apply_pin_back_rgb_target,
            status_callback=self.set_pin_back_status,
            force_close_callback=self.clear_pin_back_force_flag,
        )
        self.pin_back_cycle_detector = CycleCodeDetector(self.root, self.handle_pin_back_cycle_code)

        self.output = tk.Toplevel(self.root)
        self.output.title(f"Streamer Board - Output - {self.instance_id}")
        self.output.geometry(f"{int(self.capture_w*self.output_scale)}x{int(self.capture_h*self.output_scale)}+80+80")
        self.output.protocol("WM_DELETE_WINDOW", self.close_instance)
        self.output.bind("<Configure>", self.output_configure)

        self._build_ui()
        if board_path and board_path.exists():
            self.load_board(board_path)
            if self.delete_board_after_load:
                try:
                    board_path.unlink()
                except Exception:
                    pass
        else:
            self.redraw_all()

        self.rise_to_top(short=True)
        self.write_status()
        self.root.after(1000, self.heartbeat_tick)
        self.root.after(350, self.command_tick)

    def _build_ui(self):
        self.output_canvas = tk.Canvas(
            self.output,
            width=int(self.capture_w * self.output_scale),
            height=int(self.capture_h * self.output_scale),
            bg=self.chroma_key,
            highlightthickness=0,
        )
        self.output_canvas.pack(fill="both", expand=True)

        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        top = FlowFrame(main)
        top.pack(fill="x")
        top.add_button("Add Image", self.add_image)
        top.add_button("Save Board", self.save_board_as)
        top.add_button("Load Board", self.load_board_dialog)
        top.add_button("Clear Cache", self.clear_cache)
        top.add_button("Screen Lock", self.toggle_lock)
        top.add_button("Emergency Freeze", self.emergency_freeze)
        top.add_button("Rise Controller", lambda: self.rise_to_top(short=True))
        top.add_button("Rise Pin-Out", self.rise_output)
        top.add_button("Pin Back (RGB)", self.open_pin_back_rgb)

        pin_back_group = top.add_group()
        self.pin_back_c1_var = tk.BooleanVar(value=False)
        self.pin_back_c2_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(pin_back_group, text="C1", variable=self.pin_back_c1_var, command=lambda: self.pin_back_palette_click("c1")).pack(side="left", padx=2)
        ttk.Checkbutton(pin_back_group, text="C2", variable=self.pin_back_c2_var, command=lambda: self.pin_back_palette_click("c2")).pack(side="left", padx=2)
        self.pin_back_force_rgb_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(pin_back_group, text="Force RGB Selector", variable=self.pin_back_force_rgb_var, command=self.pin_back_force_rgb_changed).pack(side="left", padx=6)

        topmost_group = top.add_group()
        self.topmost_var = tk.BooleanVar(value=self.controller_topmost)
        ttk.Checkbutton(topmost_group, text="Controller Always on Top", variable=self.topmost_var, command=self.toggle_topmost).pack(side="left")

        mode_group = top.add_group("Resource Mode:")
        self.resource_var = tk.StringVar(value=self.resource_mode)
        self.resource_combo = ttk.Combobox(mode_group, textvariable=self.resource_var, values=["Static", "Light", "Normal", "Performance"], width=13, state="readonly")
        self.resource_combo.pack(side="left")
        self.resource_combo.bind("<<ComboboxSelected>>", lambda _e: self.set_resource_mode(self.resource_var.get()))

        self.controller_canvas = tk.Canvas(main, bg="#202020", height=430, highlightthickness=1, highlightbackground="#666666")
        self.controller_canvas.pack(fill="both", expand=True, pady=8)
        self.controller_canvas.bind("<Button-1>", self.controller_click)
        self.controller_canvas.bind("<B1-Motion>", self.controller_drag)
        self.controller_canvas.bind("<ButtonRelease-1>", self.controller_release)
        self.controller_canvas.bind("<Button-3>", self.canvas_context_menu)

        controls = ttk.LabelFrame(main, text="Selected Pin Controls", padding=8)
        controls.pack(fill="x")

        control_flow = FlowFrame(controls)
        control_flow.pack(fill="x")

        pick_group = control_flow.add_group("Pin:")
        self.pin_select_var = tk.StringVar(value="")
        self.pin_select = ttk.Combobox(pick_group, textvariable=self.pin_select_var, values=[], width=28, state="readonly")
        self.pin_select.pack(side="left")
        self.pin_select.bind("<<ComboboxSelected>>", lambda _e: self.select_by_name())

        self.vars = {}
        specs = [
            ("x", "X", 0, 0, 3840),
            ("y", "Y", 0, 0, 2160),
            ("z", "Z", 10, -999, 999),
            ("scale", "Scale", 1.0, 0.05, 5.0),
            ("rotation", "Rotation", 0.0, -360, 360),
            ("opacity", "Opacity", 1.0, 0.0, 1.0),
            ("brightness", "Brightness", 1.0, 0.0, 3.0),
            ("saturation", "Saturation", 1.0, 0.0, 3.0),
        ]
        for key, label, default, frm, to in specs:
            group = control_flow.add_group(label + ":")
            var = tk.DoubleVar(value=default)
            self.vars[key] = var
            inc = 0.05 if key not in ("x", "y", "z", "rotation") else 1
            spin = ttk.Spinbox(group, from_=frm, to=to, increment=inc, textvariable=var, width=7, command=self.apply_controls)
            spin.pack(side="left")
            spin.bind("<Return>", lambda _e: self.apply_controls())
            spin.bind("<FocusOut>", lambda _e: self.apply_controls())

        control_flow.add_button("Nudge ↑", lambda: self.nudge(0, -5))
        control_flow.add_button("Nudge ↓", lambda: self.nudge(0, 5))
        control_flow.add_button("Nudge ←", lambda: self.nudge(-5, 0))
        control_flow.add_button("Nudge →", lambda: self.nudge(5, 0))

        flip_group = control_flow.add_group()
        self.flip_x_var = tk.BooleanVar(value=False)
        self.flip_y_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(flip_group, text="Flip X", variable=self.flip_x_var, command=self.apply_controls).pack(side="left", padx=2)
        ttk.Checkbutton(flip_group, text="Flip Y", variable=self.flip_y_var, command=self.apply_controls).pack(side="left", padx=2)

        anim_group = control_flow.add_group("Animation Mix:")
        self.anim_vars = {}
        for name in ANIMATION_PRESETS:
            var = tk.BooleanVar(value=False)
            self.anim_vars[name] = var
            ttk.Checkbutton(anim_group, text=name, variable=var, command=self.apply_controls).pack(side="left", padx=1)

    def set_pin_back_status(self, message: str):
        try:
            self.root.title(f"Streamer Board - Controller - {self.instance_id} | {message}")
            self.root.after(2400, lambda: self.root.title(f"Streamer Board - Controller - {self.instance_id}"))
        except Exception:
            pass

    def clear_pin_back_force_flag(self):
        try:
            if hasattr(self, "pin_back_force_rgb_var"):
                self.pin_back_force_rgb_var.set(False)
        except Exception:
            pass

    def set_pin_back_color(self, color: str, source: str = "custom"):
        color = normalize_hex_color(color, DEFAULT_C1)
        self.chroma_key = color
        try:
            self.output_canvas.configure(bg=self.chroma_key)
        except Exception:
            pass
        self.redraw_all()
        self.write_status()
        self.set_pin_back_status(f"Pin Back {color} ({source})")

    def open_pin_back_rgb(self):
        target = {
            "kind": "pin_board_instance",
            "instance_id": self.instance_id,
            "label": f"Pin Board {self.instance_id}",
            "color": self.chroma_key,
        }
        self.pin_back_rgb.request(target, self.chroma_key, keep_open=bool(self.pin_back_force_rgb_var.get()))

    def apply_pin_back_rgb_target(self, target: dict, color: str, close_after: bool = False):
        self.set_pin_back_color(color, "RGB selector")

    def pin_back_palette_click(self, palette_name: str):
        self.pin_back_cycle_detector.click(f"pin-back-{palette_name}")
        color = get_c1() if palette_name == "c1" else get_c2()
        if self.pin_back_rgb.is_open():
            self.pin_back_rgb.set_color(color)
            return
        self.set_pin_back_color(color, palette_name.upper())

    def pin_back_force_rgb_changed(self):
        self.pin_back_cycle_detector.click("pin-back-force")
        enabled = bool(self.pin_back_force_rgb_var.get())
        self.pin_back_rgb.set_keep_open(enabled)
        if enabled and not self.pin_back_rgb.target:
            self.open_pin_back_rgb()

    def handle_pin_back_cycle_code(self, name: str, phases: tuple[int, ...], source: str):
        c1 = get_c1()
        c2 = get_c2()
        if name == "SOS":
            self.pin_back_force_rgb_var.set(False)
            self.pin_back_rgb.close(cancel=False)
            self.set_pin_back_status("RGB selector SOS: closed.")
        elif name == "Light-Tower":
            self.pin_back_force_rgb_var.set(True)
            self.open_pin_back_rgb()
            self.set_pin_back_status("RGB selector Light-Tower: forced on until pick.")
        elif name == "Reset Colors":
            set_default_pin_back(DEFAULT_C1, "c1-default")
            self.set_pin_back_color(DEFAULT_C1, "Reset Colors")
        elif name == "Default C2":
            set_default_pin_back(DEFAULT_C2, "c2-default")
            self.set_pin_back_color(DEFAULT_C2, "Default C2")
        elif name == "Use C1":
            set_default_pin_back(c1, "c1")
            self.set_pin_back_color(c1, "Use C1")
        elif name == "Use C2":
            set_default_pin_back(c2, "c2")
            self.set_pin_back_color(c2, "Use C2")
        elif name == "Reboot 2":
            reset_palette("c2")
            self.set_pin_back_color(DEFAULT_C2, "Reboot 2")
        elif name == "Reboot End EP 2":
            reset_palette("c2")
            self.set_pin_back_color(DEFAULT_C2, "Reboot End EP 2")

    def toggle_topmost(self):
        self.controller_topmost = bool(self.topmost_var.get())
        self.root.attributes("-topmost", self.controller_topmost)
        self.write_status()

    def rise_to_top(self, short: bool = True):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            if short and not self.controller_topmost:
                self.root.attributes("-topmost", True)
                self.root.after(1600, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass
        self.write_status()

    def rise_output(self):
        try:
            self.output.deiconify()
            self.output.lift()
            self.output.focus_force()
            self.output.attributes("-topmost", True)
            self.output_topmost = True
            self.output_topmost_armed = False
            self.root.after(1400, self.arm_output_topmost_release)
        except Exception:
            pass
        self.write_status()

    def arm_output_topmost_release(self):
        self.output_topmost_armed = True

    def output_configure(self, _event=None):
        if self.output_topmost and self.output_topmost_armed:
            try:
                self.output.attributes("-topmost", False)
            except Exception:
                pass
            self.output_topmost = False
            self.output_topmost_armed = False
            self.write_status()

    def set_resource_mode(self, mode: str):
        self.resource_mode = mode
        self.anim_fps = {"Static": 0, "Light": 6, "Normal": 15, "Performance": 24}.get(mode, 0)
        if self.anim_fps <= 0 and self.animation_job is not None:
            try:
                self.root.after_cancel(self.animation_job)
            except Exception:
                pass
            self.animation_job = None
        self.write_status()
        self.schedule_animation_tick()

    def schedule_animation_tick(self):
        if self.anim_fps <= 0:
            return
        if self.animation_job is not None:
            return
        delay = int(1000 / max(1, self.anim_fps))
        self.animation_job = self.root.after(delay, self.animation_tick)

    def animation_tick(self):
        self.animation_job = None
        if self.anim_fps <= 0:
            return
        self.anim_phase += 1.0 / max(1, self.anim_fps)
        if any(pin.animation_mix for pin in self.pins):
            self.redraw_output()
        self.schedule_animation_tick()

    def selected_pin(self) -> PinImageState | None:
        for pin in self.pins:
            if pin.id == self.selected_id:
                return pin
        return None

    def add_image(self):
        path = filedialog.askopenfilename(
            title="Add pin image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.gif"), ("All files", "*.*")]
        )
        if not path:
            return
        pin = PinImageState(id=str(uuid.uuid4())[:8], name=Path(path).name, path=path)
        self.pins.append(pin)
        self.selected_id = pin.id
        self.refresh_pin_dropdown()
        self.load_pin_controls()
        self.redraw_all()
        self.write_status()

    def refresh_pin_dropdown(self):
        values = [f"{pin.name} [{pin.id}]" for pin in sorted(self.pins, key=lambda p: p.z)]
        self.pin_select.configure(values=values)
        pin = self.selected_pin()
        if pin:
            self.pin_select_var.set(f"{pin.name} [{pin.id}]")
        elif values:
            self.pin_select_var.set(values[0])
        else:
            self.pin_select_var.set("")

    def select_by_name(self):
        value = self.pin_select_var.get()
        if "[" in value and "]" in value:
            self.selected_id = value.rsplit("[", 1)[1].rstrip("]")
            self.load_pin_controls()
            self.redraw_all()
            self.write_status()

    def select_pin_id(self, pin_id: str):
        if any(pin.id == pin_id for pin in self.pins):
            self.selected_id = pin_id
            self.refresh_pin_dropdown()
            self.load_pin_controls()
            self.redraw_all()
            self.write_status()

    def load_pin_controls(self):
        pin = self.selected_pin()
        if not pin:
            return
        for key, var in self.vars.items():
            var.set(getattr(pin, key))
        self.flip_x_var.set(pin.flip_x)
        self.flip_y_var.set(pin.flip_y)
        active = set(pin.animation_mix or [])
        for name, var in self.anim_vars.items():
            var.set(name in active)

    def apply_controls(self):
        pin = self.selected_pin()
        if not pin:
            return
        try:
            for key, var in self.vars.items():
                value = var.get()
                if key == "z":
                    value = int(value)
                setattr(pin, key, value)
            pin.flip_x = self.flip_x_var.get()
            pin.flip_y = self.flip_y_var.get()
            pin.animation_mix = [name for name, var in self.anim_vars.items() if var.get()]
            self.renderer.clear()
            self.refresh_pin_dropdown()
            self.redraw_all()
            self.write_status()
        except Exception as exc:
            messagebox.showerror("Control error", str(exc))

    def nudge(self, dx, dy):
        pin = self.selected_pin()
        if not pin:
            return
        pin.x += dx
        pin.y += dy
        self.load_pin_controls()
        self.redraw_all()
        self.write_status()

    def controller_click(self, event):
        if self.locked:
            return
        hit = self.find_pin_at_controller(event.x, event.y)
        if hit:
            self.selected_id = hit.id
            self.drag_start = (event.x, event.y, hit.x, hit.y)
            self.refresh_pin_dropdown()
            self.load_pin_controls()
            self.redraw_all()
            self.write_status()

    def controller_drag(self, event):
        if self.locked or not self.drag_start:
            return
        pin = self.selected_pin()
        if not pin:
            return
        sx, sy, px, py = self.drag_start
        scale = self.controller_scale()
        pin.x = px + (event.x - sx) / scale
        pin.y = py + (event.y - sy) / scale
        self.load_pin_controls()
        self.redraw_all()
        self.write_status()

    def controller_release(self, _event):
        self.drag_start = None

    def canvas_context_menu(self, event):
        hit = self.find_pin_at_controller(event.x, event.y)
        menu = tk.Menu(self.root, tearoff=0)
        if hit:
            self.selected_id = hit.id
            self.refresh_pin_dropdown()
            self.load_pin_controls()
            menu.add_command(label=f"Select {hit.name}", command=lambda: self.select_pin_id(hit.id))
            menu.add_separator()
            menu.add_command(label="Nudge ↑", command=lambda: self.nudge(0, -5))
            menu.add_command(label="Nudge ↓", command=lambda: self.nudge(0, 5))
            menu.add_command(label="Nudge ←", command=lambda: self.nudge(-5, 0))
            menu.add_command(label="Nudge →", command=lambda: self.nudge(5, 0))
            menu.add_separator()
        menu.add_command(label="Rise Controller", command=lambda: self.rise_to_top(short=True))
        menu.add_command(label="Rise Pin-Out", command=self.rise_output)
        menu.add_command(label="Emergency Freeze", command=self.emergency_freeze)
        menu.add_command(label="Screen Lock", command=self.toggle_lock)
        menu.tk_popup(event.x_root, event.y_root)

    def controller_scale(self):
        w = max(1, self.controller_canvas.winfo_width())
        h = max(1, self.controller_canvas.winfo_height())
        total_w = self.capture_w * 2.25
        total_h = self.capture_h * 2.25
        return min(w / total_w, h / total_h)

    def board_to_controller(self, x, y):
        scale = self.controller_scale()
        total_w = self.capture_w * 2.25
        total_h = self.capture_h * 2.25
        ox = (self.controller_canvas.winfo_width() - total_w * scale) / 2
        oy = (self.controller_canvas.winfo_height() - total_h * scale) / 2
        return ox + (x + self.capture_w * 0.625) * scale, oy + (y + self.capture_h * 0.625) * scale

    def find_pin_at_controller(self, cx, cy):
        for pin in sorted(self.pins, key=lambda p: p.z, reverse=True):
            px, py = self.board_to_controller(pin.x, pin.y)
            if abs(cx - px) < 20 and abs(cy - py) < 20:
                return pin
        return None

    def animation_offsets(self, pin):
        ox = oy = rot = scale = 0.0
        opacity_mult = 1.0
        mix = pin.animation_mix or []
        if "float" in mix:
            import math
            oy += math.sin(self.anim_phase * 2.0) * 8
        if "shake" in mix:
            import math
            ox += math.sin(self.anim_phase * 30.0) * 3
        if "slide-left-right" in mix:
            import math
            ox += math.sin(self.anim_phase * 1.5) * 20
        if "slow-spin" in mix:
            rot += (self.anim_phase * 20) % 360
        if "pulse" in mix:
            import math
            scale += (math.sin(self.anim_phase * 3.0) * 0.04)
        if "fade-in-out" in mix:
            import math
            opacity_mult = 0.65 + ((math.sin(self.anim_phase * 2.0) + 1) * 0.175)
        return ox, oy, rot, scale, opacity_mult

    def redraw_output(self):
        self.output_image_refs = []
        self.output_canvas.delete("all")
        self.output_canvas.configure(bg=self.chroma_key)
        for pin in sorted(self.pins, key=lambda p: p.z):
            try:
                temp = PinImageState.from_dict(pin.to_dict())
                ox, oy, rot, scale_add, opacity_mult = self.animation_offsets(pin)
                temp.rotation += rot
                temp.scale = max(0.01, temp.scale + scale_add)
                temp.opacity = max(0.0, min(1.0, temp.opacity * opacity_mult))
                use_cache = not bool(pin.animation_mix)
                img = self.renderer.render(temp, self.output_scale, use_cache=use_cache)
                self.output_image_refs.append(img)
                self.output_canvas.create_image(
                    (pin.x + ox) * self.output_scale,
                    (pin.y + oy) * self.output_scale,
                    image=img,
                    anchor="center",
                )
            except Exception:
                continue

    def redraw_controller(self):
        c = self.controller_canvas
        c.delete("all")
        scale = self.controller_scale()
        total_w = self.capture_w * 2.25
        total_h = self.capture_h * 2.25
        ox = (c.winfo_width() - total_w * scale) / 2
        oy = (c.winfo_height() - total_h * scale) / 2
        cap_x = ox + self.capture_w * 0.625 * scale
        cap_y = oy + self.capture_h * 0.625 * scale
        cap_w = self.capture_w * scale
        cap_h = self.capture_h * scale

        c.create_rectangle(ox, oy, ox + total_w * scale, oy + total_h * scale, outline="#555555")
        c.create_rectangle(cap_x, cap_y, cap_x + cap_w, cap_y + cap_h, outline="#ffcc00", width=2)
        c.create_text(cap_x + 8, cap_y + 8, text=f"OBS CAPTURE ZONE 1920x1080 | {self.instance_id}", anchor="nw", fill="#ffcc00")

        for i in range(0, self.capture_w + 1, 240):
            x = cap_x + i * scale
            c.create_line(x, cap_y, x, cap_y + 10, fill="#ffcc00")
        for i in range(0, self.capture_h + 1, 135):
            y = cap_y + i * scale
            c.create_line(cap_x, y, cap_x + 10, y, fill="#ffcc00")

        for pin in sorted(self.pins, key=lambda p: p.z):
            px, py = self.board_to_controller(pin.x, pin.y)
            color = "#00ffff" if pin.id == self.selected_id else "#ffffff"
            c.create_oval(px - 6, py - 6, px + 6, py + 6, outline=color, width=2)
            c.create_text(px + 8, py, text=pin.name, anchor="w", fill=color)

        if self.locked:
            c.create_text(c.winfo_width() - 20, 20, text="LOCKED", anchor="ne", fill="#ff4444", font=("TkDefaultFont", 14, "bold"))

    def redraw_all(self):
        self.redraw_output()
        self.redraw_controller()

    def clear_cache(self):
        self.renderer.clear()
        self.redraw_all()

    def toggle_lock(self):
        self.locked = not self.locked
        self.redraw_controller()
        self.write_status()

    def emergency_freeze(self):
        for pin in self.pins:
            pin.animation_mix = []
        self.set_resource_mode("Static")
        self.resource_var.set("Static")
        self.load_pin_controls()
        self.redraw_all()
        self.write_status()

    def board_payload(self):
        return {
            "version": "0.1.4-mvp",
            "capture": {
                "width": self.capture_w,
                "height": self.capture_h,
                "output_scale": self.output_scale,
                "chroma_key": self.chroma_key,
                "pin_back": self.chroma_key
            },
            "resource_mode": self.resource_mode,
            "pins": [pin.to_dict() for pin in self.pins]
        }

    def save_board_as(self):
        path = filedialog.asksaveasfilename(
            title="Save board",
            initialdir=BOARD_DIR,
            defaultextension=".sboard",
            filetypes=[("Streamer Board", "*.sboard"), ("JSON", "*.json")]
        )
        if not path:
            return
        self.board_path = Path(path)
        write_json(self.board_path, self.board_payload())
        self.write_status()

    def load_board_dialog(self):
        path = filedialog.askopenfilename(
            title="Load board",
            initialdir=BOARD_DIR,
            filetypes=[("Streamer Board", "*.sboard"), ("JSON", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.load_board(Path(path))

    def load_board(self, path: Path):
        data = read_json(path, {})
        cap = data.get("capture", {})
        self.capture_w = int(cap.get("width", self.capture_w))
        self.capture_h = int(cap.get("height", self.capture_h))
        self.output_scale = float(cap.get("output_scale", self.output_scale))
        self.chroma_key = normalize_hex_color(cap.get("pin_back", cap.get("chroma_key", self.chroma_key)), get_default_pin_back())
        self.resource_mode = data.get("resource_mode", "Static")
        self.resource_var.set(self.resource_mode)
        self.set_resource_mode(self.resource_mode)
        self.pins = [PinImageState.from_dict(item) for item in data.get("pins", [])]
        self.selected_id = self.pins[0].id if self.pins else None
        self.board_path = path
        self.output_canvas.configure(
            width=int(self.capture_w * self.output_scale),
            height=int(self.capture_h * self.output_scale),
            bg=self.chroma_key,
        )
        self.output.geometry(f"{int(self.capture_w*self.output_scale)}x{int(self.capture_h*self.output_scale)}")
        self.refresh_pin_dropdown()
        self.load_pin_controls()
        self.redraw_all()
        self.write_status()

    def status_payload(self):
        return {
            "version": "0.1.3-mvp",
            "instance_id": self.instance_id,
            "pid": os.getpid(),
            "title": f"Pin Board {self.instance_id}",
            "controller_title": self.root.title(),
            "output_title": self.output.title(),
            "board_path": str(self.board_path or ""),
            "heartbeat": time.time(),
            "resource_mode": self.resource_mode,
            "pin_back": self.chroma_key,
            "chroma_key": self.chroma_key,
            "locked": self.locked,
            "controller_topmost": self.controller_topmost,
            "output_topmost": self.output_topmost,
            "selected_id": self.selected_id,
            "pin_count": len(self.pins),
            "snapshot": self.board_payload(),
            "pins": [
                {"id": pin.id, "name": pin.name, "x": pin.x, "y": pin.y, "z": pin.z}
                for pin in sorted(self.pins, key=lambda p: p.z)
            ],
        }

    def write_status(self):
        write_json(status_file(self.instance_id), self.status_payload())

    def heartbeat_tick(self):
        self.write_status()
        self.root.after(1000, self.heartbeat_tick)

    def command_tick(self):
        data = read_json(command_file(self.instance_id), {})
        seq = int(data.get("seq", 0) or 0)
        if seq > self.last_command_seq:
            self.last_command_seq = seq
            self.apply_command(str(data.get("command", "")), data.get("payload", {}) or {})
        self.root.after(350, self.command_tick)

    def apply_command(self, command: str, payload: dict):
        if command == "rise_to_top":
            self.rise_to_top(short=True)
        elif command == "rise_output":
            self.rise_output()
        elif command == "set_topmost":
            self.controller_topmost = bool(payload.get("enabled", True))
            self.topmost_var.set(self.controller_topmost)
            self.root.attributes("-topmost", self.controller_topmost)
        elif command == "emergency_freeze":
            self.emergency_freeze()
        elif command == "toggle_lock":
            self.locked = bool(payload.get("locked", not self.locked))
            self.redraw_controller()
            self.write_status()
        elif command == "set_resource_mode":
            mode = str(payload.get("mode", "Static"))
            self.resource_var.set(mode)
            self.set_resource_mode(mode)
        elif command == "select_pin":
            self.select_pin_id(str(payload.get("pin_id", "")))
        elif command == "nudge":
            self.select_pin_id(str(payload.get("pin_id", self.selected_id or "")))
            self.nudge(float(payload.get("dx", 0)), float(payload.get("dy", 0)))
        elif command == "set_pin_back":
            self.set_pin_back_color(str(payload.get("color", self.chroma_key)), str(payload.get("source", "console")))
        elif command == "pin_back_helper":
            self.handle_pin_back_cycle_code(str(payload.get("name", "")), tuple(payload.get("phases", [])), "console-command")
        elif command == "close":
            self.close_instance()

    def close_instance(self):
        try:
            payload = self.status_payload()
            payload["heartbeat"] = 0
            payload["closed_at"] = time.time()
            write_json(status_file(self.instance_id), payload)
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.controller_canvas.bind("<Configure>", lambda _e: self.redraw_controller())
        self.root.mainloop()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", default="")
    parser.add_argument("--instance-id", default="")
    parser.add_argument("--delete-board-after-load", action="store_true")
    args = parser.parse_args()
    board_path = Path(args.board).expanduser() if args.board else None
    app = PinBoardApp(board_path, args.instance_id or None, args.delete_board_after_load)
    app.run()

if __name__ == "__main__":
    main()
