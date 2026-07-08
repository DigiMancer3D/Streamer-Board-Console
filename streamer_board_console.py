#!/usr/bin/env python3
from __future__ import annotations

import os
import signal
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from sbc_core.app_registry import load_apps
from sbc_core.resource_monitor import snapshot_process_tree
from sbc_core.hotkey_registry import collect_hotkeys, find_conflicts
from sbc_core.doctor import run_doctor
from sbc_core.board_registry import (
    launch_board,
    scan_board_instances,
    send_board_command,
    read_board_status,
    kill_board_with_mem,
)
from sbc_core.ui_wrap import FlowFrame
from sbc_core.tree_utils import tree_select_under_pointer, remember_tree_selection, restore_tree_selection
from sbc_core.adapter_control import default_hotkey_map, write_default_control, native_adapter_status
from sbc_core.studio_profiles import ensure_default_profiles, load_profiles, apply_profile, profile_summary, active_profile_name, save_profile, delete_profile, is_default_profile, profile_app_settings, PROFILE_ACTIONS, normalize_action, action_label, expand_profile_for_apps, default_settings_for_app
from sbc_core.startup_profile import read_startup_config, save_startup_config, clear_startup_config, apply_startup_profile
from sbc_core.user_data_backup import create_backup, inspect_backup, import_backup, list_local_backups, BACKUP_DIR
from sbc_core.adapter_templates import ensure_adapter_templates, list_templates, enable_template, disable_adapter, update_template, create_template_from_path_entry, integration_guide_text
from sbc_core.previous_build_migrate import migrate_latest_previous_build, find_previous_builds
from sbc_core.console_copier import create_console_copy, list_console_files, read_console_file, launch_console_copy, cleanup_selftest_and_broken_copies
from sbc_core.release_prep import build_github_upload, inspect_release_folder, latest_release_folder, clean_release_exports

def json_dump_short(value):
    try:
        return json.dumps(value, sort_keys=True)[:240]
    except Exception:
        return str(value)[:240]

class StreamerBoardConsole:
    def __init__(self):
        self.apps = load_apps()
        self.board_instances = []
        self.board_control_tabs: dict[str, ttk.Frame] = {}
        self.root = tk.Tk()
        self.instance_name = os.environ.get("SBC_INSTANCE_NAME", "").strip()
        self.window_title = "Streamer Board & Console" if not self.instance_name else f"Streamer Board & Console — {self.instance_name}"
        self.root.title(self.window_title)
        self.root.geometry(os.environ.get("SBC_WINDOW_GEOMETRY", "1180x760+80+80"))
        self.root.minsize(760, 520)
        self._shutdown_requested = False
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.status_var = tk.StringVar(value="Ready.")
        self.selected_board_var = tk.StringVar(value="")
        self.dashboard_selected_key = ""
        self.board_selected_key = ""
        self._build_ui()
        self.refresh_all()
        self.root.after(200, self.force_window_visible)
        self.root.after(900, self.force_window_visible)
        self.root.after(700, self.apply_startup_profile_on_launch)
        self.root.after(1800, self.monitor_tick)

    def force_window_visible(self):
        """Rescue controller window if the WM places it off-screen/minimized.

        This is intentionally conservative: force to a safe primary-monitor
        position only when env SBC_FORCE_WINDOW_RESCUE is not disabled.
        """
        if os.environ.get("SBC_FORCE_WINDOW_RESCUE", "1").lower() in ("0", "false", "no"):
            return
        try:
            self.root.deiconify()
            self.root.update_idletasks()

            sw = max(1, int(self.root.winfo_screenwidth()))
            sh = max(1, int(self.root.winfo_screenheight()))
            w = max(760, min(1180, sw - 80 if sw > 900 else sw))
            h = max(520, min(760, sh - 80 if sh > 650 else sh))
            x = int(self.root.winfo_x())
            y = int(self.root.winfo_y())

            offscreen = (x < -50) or (y < -50) or (x > sw - 80) or (y > sh - 80)
            if offscreen or os.environ.get("SBC_ALWAYS_CENTER_WINDOW", "0").lower() in ("1", "true", "yes"):
                self.root.geometry(f"{w}x{h}+80+80")

            self.root.lift()
            try:
                self.root.focus_force()
            except Exception:
                pass

            # Briefly topmost to rescue it from being behind other windows,
            # then return to normal window behavior.
            self.root.attributes("-topmost", True)
            self.root.after(900, lambda: self.root.attributes("-topmost", False))
        except Exception as exc:
            try:
                self.status_var.set(f"Window rescue warning: {exc}")
            except Exception:
                pass

    def shutdown(self):
        self._shutdown_requested = True
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _build_ui(self):
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill="both", expand=True)

        title = ttk.Label(outer, text=self.window_title, font=("TkDefaultFont", 18, "bold"))
        title.pack(anchor="w")

        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True, pady=8)

        self.dashboard_tab = ttk.Frame(self.tabs, padding=8)
        self.apps_tab = ttk.Frame(self.tabs, padding=8)
        self.hotkeys_tab = ttk.Frame(self.tabs, padding=8)
        self.boards_tab = ttk.Frame(self.tabs, padding=8)
        self.profiles_tab = ttk.Frame(self.tabs, padding=8)
        self.data_tab = ttk.Frame(self.tabs, padding=8)
        self.doctor_tab = ttk.Frame(self.tabs, padding=8)
        self.console_tab = ttk.Frame(self.tabs, padding=8)
        self.release_tab = ttk.Frame(self.tabs, padding=8)

        self.tabs.add(self.dashboard_tab, text="Dashboard")
        self.tabs.add(self.apps_tab, text="Apps")
        self.tabs.add(self.hotkeys_tab, text="Hotkeys")
        self.tabs.add(self.boards_tab, text="Pin Boards")
        self.tabs.add(self.profiles_tab, text="Studio Profiles")
        self.tabs.add(self.data_tab, text="Backup / Migrate")
        self.tabs.add(self.doctor_tab, text="Doctor")
        self.tabs.add(self.console_tab, text="Console Copier")
        self.tabs.add(self.release_tab, text="Release Prep")

        self._build_dashboard()
        self._build_apps()
        self._build_hotkeys()
        self._build_boards()
        self._build_profiles()
        self._build_data_tools()
        self._build_doctor()
        self._build_console_copier()
        self._build_release_prep()

        bottom = FlowFrame(outer)
        bottom.pack(fill="x")
        g = bottom.add_group()
        ttk.Label(g, textvariable=self.status_var).pack(side="left")
        bottom.add_button("Emergency Studio Reset", self.emergency_reset)
        bottom.add_button("Refresh", self.refresh_all)

    def _tree(self, parent, cols, headings, height=12):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=cols, show="headings", height=height, selectmode="browse")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        for col, heading in zip(cols, headings):
            tree.heading(col, text=heading)
            tree.column(col, width=150, minwidth=80, anchor="w", stretch=True)

        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def _scrollable_content(self, parent):
        """Create a vertically scrollable content frame for long tabs."""
        container = ttk.Frame(parent)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        content = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def _configure_content(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _configure_canvas(event):
            canvas.itemconfigure(window_id, width=event.width)

        def _scroll(event):
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-3, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(3, "units")
            else:
                delta = getattr(event, "delta", 0)
                if delta:
                    canvas.yview_scroll(int(-1 * (delta / 120)), "units")

        def _bind_scroll(_event=None):
            canvas.bind_all("<MouseWheel>", _scroll)
            canvas.bind_all("<Button-4>", _scroll)
            canvas.bind_all("<Button-5>", _scroll)

        def _unbind_scroll(_event=None):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        content.bind("<Configure>", _configure_content)
        canvas.bind("<Configure>", _configure_canvas)
        canvas.bind("<Enter>", _bind_scroll)
        canvas.bind("<Leave>", _unbind_scroll)
        content.bind("<Enter>", _bind_scroll)
        content.bind("<Leave>", _unbind_scroll)
        return content

    def _build_dashboard(self):
        ttk.Label(
            self.dashboard_tab,
            text="Running app + pin board resource monitor",
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w")

        # Clean dashboard view: no duplicate visible action toolbar here.
        # Right-click rows for hot options.
        self.resource_tree = self._tree(
            self.dashboard_tab,
            ("key", "type", "name", "state", "pid", "ram", "cpu", "children"),
            ("Key", "Type", "Name", "State", "PID", "RAM MB", "CPU %", "Child Procs")
        )
        self.resource_tree.bind("<<TreeviewSelect>>", lambda _e: self.remember_dashboard_selection())
        self.resource_tree.bind("<Button-3>", self.dashboard_context_menu)
        self.resource_tree.bind("<Button-1>", self.dashboard_left_click)

    def _build_apps(self):

        apps_parent = self._scrollable_content(self.apps_tab)
        ttk.Label(
            apps_parent,
            text="Active App Adapters",
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w")

        for _app_id, app in self.apps.items():
            box = ttk.LabelFrame(apps_parent, text=app.display_name, padding=8)
            box.pack(fill="x", pady=6)

            info = ttk.Label(box, text=f"Path: {app.app_path}\nEntry: {app.entry_file}", wraplength=900)
            info.pack(anchor="w")

            bar = FlowFrame(box)
            bar.pack(fill="x", pady=4)
            bar.add_button("Launch", lambda a=app: self.action(a.launch()))
            bar.add_button("Close", lambda a=app: self.action(a.close()))
            bar.add_button("Restart", lambda a=app: self.action(a.restart()))
            bar.add_button("Pause & Park", lambda a=app: self.action(a.pause_park()))
            bar.add_button("Resume", lambda a=app: self.action(a.resume()))
            bar.add_button("Write Hotkeys OFF Control", lambda a=app: self.write_hotkey_control(a, False))
            bar.add_button("Write Hotkeys ON Control", lambda a=app: self.write_hotkey_control(a, True))

        template_box = ttk.LabelFrame(apps_parent, text="Adapter Templates", padding=8)
        template_box.pack(fill="both", expand=True, pady=10)

        ttk.Label(
            template_box,
            text="Templates are inactive until enabled. Use these to stage Bitninja, Deck Card Widget, SWAR, or future streamer tools without breaking the current Soundcard/G502V setup.",
            wraplength=1050
        ).pack(anchor="w", pady=(0, 6))

        bar = FlowFrame(template_box)
        bar.pack(fill="x", pady=4)
        bar.add_button("Refresh Templates", self.refresh_adapter_templates)
        bar.add_button("New Template Entry", self.new_adapter_template_entry)
        bar.add_button("Create Template From Entry", self.create_adapter_template_from_entry)
        bar.add_button("Load Selected Into Editor", self.load_selected_adapter_template)
        bar.add_button("Save Template Path/Entry", self.save_selected_adapter_template)
        bar.add_button("Enable Selected Template", self.enable_selected_adapter_template)
        bar.add_button("Disable Selected Non-Core Adapter", self.disable_selected_adapter_template)
        bar.add_button("How 2 Integrate", self.show_how2_integrate)

        edit = ttk.LabelFrame(template_box, text="Selected Template Path / Entry Editor", padding=6)
        edit.pack(fill="x", pady=6)

        edit_flow = FlowFrame(edit)
        edit_flow.pack(fill="x")
        self.adapter_template_edit_id_var = tk.StringVar(value="")
        self.adapter_template_edit_path_var = tk.StringVar(value="")
        self.adapter_template_edit_entry_var = tk.StringVar(value="")
        id_group = edit_flow.add_group("App ID:")
        ttk.Entry(id_group, textvariable=self.adapter_template_edit_id_var, width=24, state="readonly").pack(side="left")
        path_group = edit_flow.add_group("Path:")
        ttk.Entry(path_group, textvariable=self.adapter_template_edit_path_var, width=48).pack(side="left")
        entry_group = edit_flow.add_group("Entry:")
        ttk.Entry(entry_group, textvariable=self.adapter_template_edit_entry_var, width=28).pack(side="left")

        self.adapter_template_status_var = tk.StringVar(value="Adapter templates ready.")
        ttk.Label(template_box, textvariable=self.adapter_template_status_var, wraplength=1050).pack(anchor="w", pady=4)

        self.adapter_template_tree = self._tree(
            template_box,
            ("app_id", "display", "active", "path_ok", "entry_ok", "path", "entry", "notes"),
            ("App ID", "Display", "Active", "Path OK", "Entry OK", "Path", "Entry", "Notes"),
            height=8,
        )
        self.adapter_template_tree.bind("<<TreeviewSelect>>", lambda _e: self.load_selected_adapter_template())
        self.refresh_adapter_templates()

    def refresh_adapter_templates(self):
        if not hasattr(self, "adapter_template_tree"):
            return
        ensure_adapter_templates()
        result = list_templates()

        for item in self.adapter_template_tree.get_children():
            self.adapter_template_tree.delete(item)

        for row in result.get("templates", []):
            self.adapter_template_tree.insert("", "end", iid=row.get("app_id", ""), values=(
                row.get("app_id", ""),
                row.get("display_name", ""),
                "YES" if row.get("active") else "no",
                "YES" if row.get("app_path_exists") else "no",
                "YES" if row.get("entry_file_exists") else "no",
                row.get("default_path", ""),
                row.get("entry_file", ""),
                row.get("notes", ""),
            ))

        self.adapter_template_status_var.set(
            f"Adapter templates: {result.get('count', 0)} available. Enable one only after confirming path/entry script."
        )

    def selected_adapter_template_id(self) -> str:
        if not hasattr(self, "adapter_template_tree"):
            return ""
        selection = self.adapter_template_tree.selection()
        if not selection:
            return ""
        return str(selection[0])

    def new_adapter_template_entry(self):
        self.adapter_template_edit_id_var.set("(auto)")
        self.adapter_template_edit_path_var.set("")
        self.adapter_template_edit_entry_var.set("")
        if hasattr(self, "adapter_template_tree"):
            for item in self.adapter_template_tree.selection():
                self.adapter_template_tree.selection_remove(item)
        self.adapter_template_status_var.set("New template entry ready. Fill Path and Entry, then click Create Template From Entry.")

    def create_adapter_template_from_entry(self):
        path_value = self.adapter_template_edit_path_var.get().strip()
        entry_value = self.adapter_template_edit_entry_var.get().strip()
        if not path_value or not entry_value:
            self.adapter_template_status_var.set("Fill both Path and Entry before creating a template.")
            return
        result = create_template_from_path_entry(path_value, entry_value)
        if result.get("ok"):
            app_id = result.get("app_id", "")
            self.adapter_template_edit_id_var.set(app_id)
            self.adapter_template_status_var.set(f"Created template {app_id}. Confirm Path OK / Entry OK, then enable when ready.")
        else:
            self.adapter_template_status_var.set(result.get("error", "Template creation failed."))
        self.refresh_adapter_templates()

    def load_selected_adapter_template(self):
        app_id = self.selected_adapter_template_id()
        if not app_id:
            return
        try:
            values = self.adapter_template_tree.item(app_id, "values")
            self.adapter_template_edit_id_var.set(app_id)
            self.adapter_template_edit_path_var.set(str(values[5] if len(values) > 5 else ""))
            self.adapter_template_edit_entry_var.set(str(values[6] if len(values) > 6 else ""))
            self.adapter_template_status_var.set(f"Loaded template into editor: {app_id}")
        except Exception as exc:
            self.adapter_template_status_var.set(f"Template load warning: {exc}")

    def save_selected_adapter_template(self):
        app_id = self.adapter_template_edit_id_var.get().strip() or self.selected_adapter_template_id()
        if not app_id:
            self.adapter_template_status_var.set("Select a template first.")
            return
        path_value = self.adapter_template_edit_path_var.get().strip()
        entry_value = self.adapter_template_edit_entry_var.get().strip()
        result = update_template(app_id, default_path=path_value, entry_file=entry_value)
        if result.get("ok"):
            self.adapter_template_status_var.set(
                f"Saved template {app_id}: Path OK={'YES' if result.get('app_path_exists') else 'no'}, Entry OK={'YES' if result.get('entry_file_exists') else 'no'}"
            )
        else:
            self.adapter_template_status_var.set(result.get("error", "Template save failed."))
        self.refresh_adapter_templates()

    def show_how2_integrate(self):
        win = tk.Toplevel(self.root)
        win.title("How 2 Integrate Apps")
        win.geometry("920x680+120+120")
        frame = ttk.Frame(win, padding=8)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word")
        y = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=y.set)
        text.pack(side="left", fill="both", expand=True)
        y.pack(side="right", fill="y")
        text.insert("1.0", integration_guide_text())
        text.configure(state="disabled")

    def enable_selected_adapter_template(self):
        app_id = self.selected_adapter_template_id()
        if not app_id:
            self.adapter_template_status_var.set("Select an adapter template first.")
            return
        result = enable_template(app_id)
        self.adapter_template_status_var.set(result.get("message") or result.get("error") or str(result))
        self.refresh_adapter_templates()

    def disable_selected_adapter_template(self):
        app_id = self.selected_adapter_template_id()
        if not app_id:
            self.adapter_template_status_var.set("Select an adapter template first.")
            return
        result = disable_adapter(app_id)
        self.adapter_template_status_var.set(result.get("message") or result.get("error") or str(result))
        self.refresh_adapter_templates()

    def _build_hotkeys(self):
        ttk.Label(self.hotkeys_tab, text="Hotkey registry and conflict detector", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        bar = FlowFrame(self.hotkeys_tab)
        bar.pack(fill="x", pady=4)
        bar.add_button("Refresh Conflicts", self.refresh_hotkeys)
        self.hotkey_tree = self._tree(
            self.hotkeys_tab,
            ("status", "key", "app", "action"),
            ("Status", "Key", "App", "Action")
        )

    def _build_boards(self):
        ttk.Label(self.boards_tab, text="Pin Board instance manager", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        ttk.Label(
            self.boards_tab,
            text="Pin Board instances publish heartbeat/status files so the console can track RAM/CPU and send safe local commands.",
            wraplength=950
        ).pack(anchor="w", pady=4)

        bar = FlowFrame(self.boards_tab)
        bar.pack(fill="x", pady=6)
        bar.add_button("Launch New Pin Board", self.launch_pin_board)
        bar.add_button("Refresh Instances", self.refresh_boards)

        pick_group = bar.add_group("Instance:")
        self.board_combo = ttk.Combobox(pick_group, textvariable=self.selected_board_var, values=[], width=34, state="readonly")
        self.board_combo.pack(side="left")
        self.board_combo.bind("<<ComboboxSelected>>", lambda _e: self.board_combo_changed())

        bar.add_button("Rise Controller", self.board_rise_to_top)
        bar.add_button("Rise Pin-Out", self.board_rise_output)
        bar.add_button("Bring-in as Tab", self.bring_board_as_tab)
        bar.add_button("Controller Always Top", lambda: self.board_set_topmost(True))
        bar.add_button("Controller Normal", lambda: self.board_set_topmost(False))
        bar.add_button("Emergency Freeze", self.board_freeze)
        bar.add_button("Kill w/Mem", self.board_kill_with_mem)
        bar.add_button("Close Board", self.board_close)

        self.boards_tree = self._tree(
            self.boards_tab,
            ("id", "state", "pid", "pins", "mode", "controller", "output"),
            ("ID", "State", "PID", "Pins", "Mode", "Controller Window", "Output Window"),
            height=10,
        )
        self.boards_tree.bind("<<TreeviewSelect>>", lambda _e: self.remember_board_selection())
        self.boards_tree.bind("<Button-3>", self.board_context_menu)
        self.boards_tree.bind("<Button-1>", self.board_left_click)

        notes = (
            "Right-click a board row for hot options. Selection is persistent; it changes only when you click another row, "
            "or when that instance closes/stales out."
        )
        ttk.Label(self.boards_tab, text=notes, wraplength=1050).pack(anchor="w", pady=8)

    def _profile_action_values(self):
        return [action_label(action) for action in PROFILE_ACTIONS]

    def _build_profiles(self):

        profiles_parent = self._scrollable_content(self.profiles_tab)
        ensure_default_profiles()

        ttk.Label(
            profiles_parent,
            text="Studio Mode Profiles",
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w")

        ttk.Label(
            profiles_parent,
            text="Use one dynamic profile table for every active adapter. Select a row, edit Hotkeys/Action, then save or apply the profile.",
            wraplength=1050,
        ).pack(anchor="w", pady=4)

        bar = FlowFrame(profiles_parent)
        bar.pack(fill="x", pady=6)

        profile_group = bar.add_group("Profile:")
        self.profile_var = tk.StringVar(value="")
        self.profile_combo = ttk.Combobox(
            profile_group,
            textvariable=self.profile_var,
            values=[],
            width=34,
            state="readonly"
        )
        self.profile_combo.pack(side="left")
        self.profile_combo.bind("<<ComboboxSelected>>", lambda _e: self.profile_changed())

        # Kept internally for backward compatibility; no longer shown as a confusing legacy checkbox.
        self.profile_launch_var = tk.BooleanVar(value=False)

        bar.add_button("Apply Saved Profile", self.apply_selected_profile)
        bar.add_button("Apply Saved + Run Actions", lambda: self.apply_selected_profile(launch_apps=True))
        bar.add_button("Refresh Profiles", self.refresh_profiles)
        bar.add_button("Gaming", lambda: self.apply_named_profile("Gaming"))
        bar.add_button("Clean Visuals", lambda: self.apply_named_profile("Clean Visuals"))
        bar.add_button("Talk / Podcast", lambda: self.apply_named_profile("Talk / Podcast"))

        self.profile_status_var = tk.StringVar(value="Profiles ready.")
        ttk.Label(profiles_parent, textvariable=self.profile_status_var, wraplength=1050).pack(anchor="w", pady=4)

        self.profile_desc_var = tk.StringVar(value="")
        ttk.Label(profiles_parent, textvariable=self.profile_desc_var, wraplength=1050).pack(anchor="w", pady=2)

        # Single source of truth for the visible/editable profile rows.
        self.profile_tree = self._tree(
            profiles_parent,
            ("app_id", "display", "hotkeys", "mode", "action"),
            ("App ID", "Display", "Hotkeys", "Mode", "Action"),
            height=9,
        )
        self.profile_tree.bind("<<TreeviewSelect>>", lambda _e: self.profile_row_selected())
        self.profile_tree.bind("<Button-3>", self.profile_context_menu)
        self.profile_tree.bind("<Double-1>", lambda _e: self.apply_profile_editor_row())

        self.profile_editor_state: dict[str, dict] = {}
        self.profile_editor_selected_app_id_var = tk.StringVar(value="")

        row_editor = ttk.LabelFrame(profiles_parent, text="Selected Row Editor", padding=8)
        row_editor.pack(fill="x", pady=8)

        row_flow = FlowFrame(row_editor)
        row_flow.pack(fill="x")

        selected_group = row_flow.add_group("Selected App:")
        ttk.Label(selected_group, textvariable=self.profile_editor_selected_app_id_var, width=28).pack(side="left")

        hotkey_group = row_flow.add_group("Hotkeys:")
        self.profile_editor_hotkeys_var = tk.StringVar(value="ON")
        ttk.Combobox(hotkey_group, textvariable=self.profile_editor_hotkeys_var, values=["ON", "OFF"], width=6, state="readonly").pack(side="left")

        action_group = row_flow.add_group("Action:")
        self.profile_editor_action_var = tk.StringVar(value="Keep")
        ttk.Combobox(action_group, textvariable=self.profile_editor_action_var, values=self._profile_action_values(), width=10, state="readonly").pack(side="left")

        row_flow.add_button("Update Selected Row", self.apply_profile_editor_row)
        row_flow.add_button("Set All Actions Keep", self.set_profile_editor_all_keep)
        row_flow.add_button("Hotkeys ON", lambda: self.set_selected_profile_row_hotkeys(True))
        row_flow.add_button("Hotkeys OFF", lambda: self.set_selected_profile_row_hotkeys(False))

        meta = ttk.LabelFrame(profiles_parent, text="Profile Name / Description", padding=8)
        meta.pack(fill="x", pady=8)

        meta_flow = FlowFrame(meta)
        meta_flow.pack(fill="x")

        name_group = meta_flow.add_group("Name:")
        self.profile_edit_name_var = tk.StringVar(value="")
        ttk.Entry(name_group, textvariable=self.profile_edit_name_var, width=32).pack(side="left")

        desc_group = meta_flow.add_group("Description:")
        self.profile_edit_desc_var = tk.StringVar(value="")
        ttk.Entry(desc_group, textvariable=self.profile_edit_desc_var, width=68).pack(side="left")

        meta_buttons = FlowFrame(meta)
        meta_buttons.pack(fill="x", pady=(8, 0))
        meta_buttons.add_button("Load Selected Into Editor", self.load_selected_profile_into_editor)
        meta_buttons.add_button("Save / Update Profile", self.save_profile_from_editor)
        meta_buttons.add_button("Delete Custom Profile", self.delete_selected_custom_profile)

        startup = ttk.LabelFrame(profiles_parent, text="Startup Profile", padding=8)
        startup.pack(fill="x", pady=8)

        startup_flow = FlowFrame(startup)
        startup_flow.pack(fill="x")

        self.startup_enabled_var = tk.BooleanVar(value=False)
        self.startup_launch_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(startup_flow.add_group(), text="Auto-apply selected profile when console launches", variable=self.startup_enabled_var).pack(side="left")
        ttk.Checkbutton(startup_flow.add_group(), text="Run startup profile actions", variable=self.startup_launch_var).pack(side="left")
        startup_flow.add_button("Set Selected as Startup", self.set_selected_startup_profile)
        startup_flow.add_button("Apply Startup Now", self.apply_startup_now_ui)
        startup_flow.add_button("Clear Startup", self.clear_startup_profile_ui)
        startup_flow.add_button("Refresh Startup", self.refresh_startup_controls)

        self.startup_status_var = tk.StringVar(value="Startup profile not loaded yet.")
        ttk.Label(startup, textvariable=self.startup_status_var, wraplength=1050).pack(anchor="w", pady=(6, 0))

        help_text = (
            "Right-click a profile row for quick row actions. Keep does not change app process state; Launch starts/detects the app; "
            "Close stops it; Restart closes then launches; Pause uses Pause & Park; Resume unpauses. Built-in profiles can be updated, but not deleted."
        )
        ttk.Label(profiles_parent, text=help_text, wraplength=1050).pack(anchor="w", pady=6)

        self.refresh_profiles()
        self.refresh_startup_controls()

    def refresh_profiles(self):
        self.profiles = load_profiles()
        values = list(self.profiles.keys())

        if not hasattr(self, "profile_combo"):
            return

        self.profile_combo.configure(values=values)
        active = active_profile_name()

        if active and active in values:
            self.profile_var.set(active)
        elif values and self.profile_var.get() not in values:
            self.profile_var.set(values[0])

        self.profile_changed()

    def profile_changed(self):
        if not hasattr(self, "profile_tree"):
            return

        name = self.profile_var.get()
        profile = getattr(self, "profiles", {}).get(name, {})

        self.load_profile_into_editor_state(name, profile, set_name_fields=False)

        desc = profile.get("description", "")
        built_in = "built-in" if is_default_profile(name) else "custom"
        self.profile_desc_var.set(f"{desc}  [{built_in}]" if name else desc)
        if name:
            self.profile_status_var.set(f"Selected profile: {name}")

    def apply_named_profile(self, name: str):
        if hasattr(self, "profile_combo"):
            self.profile_var.set(name)
            self.profile_changed()
        self.apply_selected_profile()

    def apply_selected_profile(self, launch_apps: bool | None = None):
        name = self.profile_var.get()
        if not name:
            self.profile_status_var.set("No profile selected.")
            return

        requested_action_run = bool(launch_apps) if launch_apps is not None else bool(getattr(self, "profile_launch_var", tk.BooleanVar(value=False)).get())
        # Per-app profile actions are strict. This runs saved Launch/Close/Restart/Pause/Resume actions, but never turns Keep into Launch.
        do_launch = False
        result = apply_profile(name, self.apps, launch_apps=do_launch)
        if result.get("ok"):
            applied = result.get("applied", [])
            details = ", ".join(
                f"{item.get('display_name', item.get('app_id'))}={'ON' if item.get('hotkeys_enabled') else 'OFF'}/{action_label(item.get('effective_action', item.get('action', 'keep')))}"
                for item in applied
            )
            action_notes = [item.get("action_message", "") or item.get("launch_message", "") for item in applied if item.get("action_message") or item.get("launch_message")]
            suffix = (" | " + " | ".join(action_notes)) if action_notes else ""
            self.profile_status_var.set(f"Applied saved profile {name}: {details}{suffix}")
            self.status_var.set(f"Applied Studio Profile: {name}{' + actions' if requested_action_run else ''}")
            if hasattr(self, "profile_combo"):
                self.profile_var.set(name)
                self.profile_changed()
            self.refresh_boards()
            self.refresh_resources()
            self.refresh_doctor()
            self.refresh_hotkeys()
        else:
            self.profile_status_var.set(result.get("error", "Profile apply failed."))

    def refresh_startup_controls(self):
        cfg = read_startup_config()
        if hasattr(self, "startup_enabled_var"):
            self.startup_enabled_var.set(bool(cfg.get("enabled", False)))
        if hasattr(self, "startup_launch_var"):
            self.startup_launch_var.set(bool(cfg.get("launch_apps", False)))
        profile = str(cfg.get("profile") or "Gaming")
        state = "enabled" if cfg.get("enabled") else "disabled"
        launch = "run profile actions" if cfg.get("launch_apps") else "do not run profile actions"
        if hasattr(self, "startup_status_var"):
            self.startup_status_var.set(f"Startup profile: {profile} ({state}, {launch}).")

    def set_selected_startup_profile(self):
        name = self.profile_var.get() or "Gaming"
        cfg = save_startup_config(
            name,
            enabled=bool(self.startup_enabled_var.get()),
            launch_apps=bool(self.startup_launch_var.get()),
        )
        state = "enabled" if cfg.get("enabled") else "disabled"
        launch = "run profile actions" if cfg.get("launch_apps") else "do not run profile actions"
        self.startup_status_var.set(f"Saved startup profile: {cfg.get('profile')} ({state}, {launch}).")

    def clear_startup_profile_ui(self):
        cfg = clear_startup_config()
        self.refresh_startup_controls()
        self.startup_status_var.set("Startup profile cleared/disabled.")

    def apply_startup_now_ui(self):
        result = apply_startup_profile(self.apps)
        if result.get("skipped"):
            self.startup_status_var.set(f"Startup apply skipped: {result.get('reason')}")
        elif result.get("ok"):
            profile = result.get("config", {}).get("profile", "")
            self.startup_status_var.set(f"Applied startup profile now: {profile}")
            self.status_var.set(f"Applied startup profile: {profile}")
            self.refresh_boards()
            self.refresh_resources()
            self.refresh_doctor()
            self.refresh_hotkeys()
        else:
            self.startup_status_var.set(f"Startup apply failed: {result.get('reason', 'unknown error')}")

    def apply_startup_profile_on_launch(self):
        cfg = read_startup_config()
        if not cfg.get("enabled", False):
            self.refresh_startup_controls()
            return

        result = apply_startup_profile(self.apps)
        if result.get("ok") and not result.get("skipped"):
            profile = result.get("config", {}).get("profile", "")
            self.status_var.set(f"Auto-applied startup profile: {profile}")
            if hasattr(self, "profile_var"):
                self.profile_var.set(profile)
                self.profile_changed()
            self.refresh_startup_controls()
            self.refresh_resources()
            self.refresh_doctor()
        elif result.get("skipped"):
            self.status_var.set(f"Startup profile skipped: {result.get('reason')}")
            self.refresh_startup_controls()
        else:
            self.status_var.set(f"Startup profile failed: {result.get('reason', 'unknown error')}")
            self.refresh_startup_controls()

    def app_display_name(self, app_id: str) -> str:
        app = self.apps.get(app_id) if isinstance(getattr(self, "apps", None), dict) else None
        return str(getattr(app, "display_name", app_id))

    def load_profile_into_editor_state(self, name: str | None = None, profile: dict | None = None, set_name_fields: bool = False):
        if not hasattr(self, "profile_tree"):
            return

        name = name if name is not None else self.profile_var.get()
        if profile is None:
            profile = getattr(self, "profiles", {}).get(name, {})

        expanded = expand_profile_for_apps(profile, self.apps)
        state: dict[str, dict] = {}
        for app_id in self.apps.keys():
            settings = expanded.get("apps", {}).get(app_id, {})
            if not isinstance(settings, dict):
                settings = {}
            state[app_id] = {
                "hotkeys_enabled": bool(settings.get("hotkeys_enabled", True)),
                "mode": str(settings.get("mode", "local")),
                "action": normalize_action(settings.get("action", "keep")),
            }

        self.profile_editor_state = state

        if set_name_fields:
            self.profile_edit_name_var.set(name or "")
            self.profile_edit_desc_var.set(str(profile.get("description", "")))

        self.refresh_profile_tree()

    # Backward-compatible method name for older checks/docs.
    def load_profile_into_dynamic_editor(self, name: str | None = None, profile: dict | None = None, set_name_fields: bool = False):
        self.load_profile_into_editor_state(name, profile, set_name_fields=set_name_fields)

    def refresh_profile_tree(self):
        if not hasattr(self, "profile_tree"):
            return

        tree = self.profile_tree
        selected = getattr(self, "profile_editor_selected_app_id_var", tk.StringVar(value="")).get()

        for item in tree.get_children():
            tree.delete(item)

        state = getattr(self, "profile_editor_state", {})
        for app_id in self.apps.keys():
            settings = state.get(app_id, default_settings_for_app(app_id))
            tree.insert(
                "",
                "end",
                iid=app_id,
                values=(
                    app_id,
                    self.app_display_name(app_id),
                    "ON" if settings.get("hotkeys_enabled", True) else "OFF",
                    str(settings.get("mode", "local")),
                    action_label(settings.get("action", "keep")),
                ),
            )

        if selected and tree.exists(selected):
            tree.selection_set(selected)
            tree.focus(selected)

    # Backward-compatible method name for older checks/docs.
    def refresh_profile_editor_table(self):
        self.refresh_profile_tree()

    def profile_row_selected(self):
        if not hasattr(self, "profile_tree"):
            return
        selection = self.profile_tree.selection()
        if not selection:
            return
        app_id = str(selection[0])
        state = getattr(self, "profile_editor_state", {})
        settings = state.get(app_id, default_settings_for_app(app_id))
        self.profile_editor_selected_app_id_var.set(app_id)
        self.profile_editor_hotkeys_var.set("ON" if settings.get("hotkeys_enabled", True) else "OFF")
        self.profile_editor_action_var.set(action_label(settings.get("action", "keep")))

    # Backward-compatible method name for older checks/docs.
    def profile_editor_row_selected(self):
        self.profile_row_selected()

    def selected_profile_row_app_id(self) -> str:
        if not hasattr(self, "profile_tree"):
            return ""
        selection = self.profile_tree.selection()
        return str(selection[0]) if selection else ""

    def apply_profile_editor_row(self, silent: bool = False):
        app_id = self.profile_editor_selected_app_id_var.get().strip()
        if not app_id:
            app_id = self.selected_profile_row_app_id()
        if not app_id:
            if not silent:
                self.profile_status_var.set("Select a profile row first.")
            return

        state = getattr(self, "profile_editor_state", {})
        state.setdefault(app_id, default_settings_for_app(app_id))
        state[app_id]["hotkeys_enabled"] = (self.profile_editor_hotkeys_var.get().upper() == "ON")
        state[app_id]["mode"] = "local"
        state[app_id]["action"] = normalize_action(self.profile_editor_action_var.get())
        self.profile_editor_state = state
        self.refresh_profile_tree()

        if hasattr(self, "profile_tree") and self.profile_tree.exists(app_id):
            self.profile_tree.selection_set(app_id)
            self.profile_tree.focus(app_id)

        if not silent:
            self.profile_status_var.set(f"Updated row in profile editor: {app_id}. Save / Update Profile to keep it.")

    def set_profile_editor_all_keep(self):
        state = getattr(self, "profile_editor_state", {})
        if not state:
            self.load_profile_into_editor_state()
            state = getattr(self, "profile_editor_state", {})
        for app_id in self.apps.keys():
            state.setdefault(app_id, default_settings_for_app(app_id))
            state[app_id]["action"] = "keep"
        self.profile_editor_state = state
        self.refresh_profile_tree()
        self.profile_status_var.set("Set all editor actions to Keep. Save / Update Profile to keep it.")

    def set_selected_profile_row_hotkeys(self, enabled: bool):
        app_id = self.profile_editor_selected_app_id_var.get().strip() or self.selected_profile_row_app_id()
        if not app_id:
            self.profile_status_var.set("Select a profile row first.")
            return
        self.profile_editor_hotkeys_var.set("ON" if enabled else "OFF")
        self.apply_profile_editor_row(silent=True)
        self.profile_status_var.set(f"Set {app_id} hotkeys {'ON' if enabled else 'OFF'} in editor.")

    def set_selected_profile_row_action(self, action: str):
        app_id = self.profile_editor_selected_app_id_var.get().strip() or self.selected_profile_row_app_id()
        if not app_id:
            self.profile_status_var.set("Select a profile row first.")
            return
        normalized = normalize_action(action)
        self.profile_editor_action_var.set(action_label(normalized))
        self.apply_profile_editor_row(silent=True)
        self.profile_status_var.set(f"Set {app_id} action to {action_label(normalized)} in editor.")

    def load_selected_profile_into_editor(self):
        name = self.profile_var.get()
        profile = getattr(self, "profiles", {}).get(name, {})
        self.load_profile_into_editor_state(name, profile, set_name_fields=True)
        self.profile_status_var.set(f"Loaded {name} into editor.")

    def save_profile_from_editor(self):
        name = self.profile_edit_name_var.get().strip() or self.profile_var.get().strip()
        if not name:
            self.profile_status_var.set("Enter or select a profile name before saving.")
            return

        # Pull the currently selected row controls into the state before saving.
        if self.profile_editor_selected_app_id_var.get().strip():
            self.apply_profile_editor_row(silent=True)

        desc = self.profile_edit_desc_var.get().strip()
        if not desc:
            current = getattr(self, "profiles", {}).get(self.profile_var.get(), {})
            desc = str(current.get("description", ""))

        state = getattr(self, "profile_editor_state", {})
        if not state:
            current_profile = getattr(self, "profiles", {}).get(self.profile_var.get(), {})
            expanded = expand_profile_for_apps(current_profile, self.apps)
            state = dict(expanded.get("apps", {}))

        app_settings: dict[str, dict] = {}
        for app_id in self.apps.keys():
            settings = dict(state.get(app_id, default_settings_for_app(app_id)))
            settings["hotkeys_enabled"] = bool(settings.get("hotkeys_enabled", True))
            settings["mode"] = str(settings.get("mode", "local"))
            settings["action"] = normalize_action(settings.get("action", "keep"))
            app_settings[app_id] = settings

        path = save_profile(name, desc, app_settings)
        self.refresh_profiles()
        self.profile_var.set(name)
        self.profile_changed()
        self.profile_status_var.set(f"Saved profile: {name} ({path})")

    def delete_selected_custom_profile(self):
        name = self.profile_var.get()
        if not name:
            self.profile_status_var.set("No profile selected.")
            return
        if is_default_profile(name):
            self.profile_status_var.set(f"Built-in profile cannot be deleted: {name}")
            return
        if not messagebox.askyesno("Delete custom profile", f"Delete custom profile '{name}'?"):
            return

        result = delete_profile(name)
        if result.get("ok"):
            self.profile_status_var.set(f"Deleted custom profile: {name}")
            self.profile_var.set("")
            self.refresh_profiles()
        else:
            self.profile_status_var.set(result.get("error", "Delete failed."))

    def profile_context_menu(self, event):
        if hasattr(self, "profile_tree"):
            row = self.profile_tree.identify_row(event.y)
            if row:
                self.profile_tree.selection_set(row)
                self.profile_tree.focus(row)
                self.profile_row_selected()

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Update Selected Row", command=self.apply_profile_editor_row)
        menu.add_command(label="Set Row Hotkeys ON", command=lambda: self.set_selected_profile_row_hotkeys(True))
        menu.add_command(label="Set Row Hotkeys OFF", command=lambda: self.set_selected_profile_row_hotkeys(False))

        action_menu = tk.Menu(menu, tearoff=0)
        for action in PROFILE_ACTIONS:
            action_menu.add_command(
                label=action_label(action),
                command=lambda a=action: self.set_selected_profile_row_action(a),
            )
        menu.add_cascade(label="Set Row Action", menu=action_menu)

        menu.add_separator()
        menu.add_command(label="Save / Update Profile", command=self.save_profile_from_editor)
        menu.add_command(label="Load Selected Into Editor", command=self.load_selected_profile_into_editor)
        menu.add_command(label="Delete Custom Profile", command=self.delete_selected_custom_profile)

        menu.add_separator()
        menu.add_command(label="Apply Saved Profile", command=self.apply_selected_profile)
        menu.add_command(label="Apply Saved + Run Actions", command=lambda: self.apply_selected_profile(launch_apps=True))
        menu.add_command(label="Set Selected as Startup", command=self.set_selected_startup_profile)
        menu.add_command(label="Apply Startup Now", command=self.apply_startup_now_ui)

        menu.add_separator()
        menu.add_command(label="Refresh Profiles", command=self.refresh_profiles)
        menu.add_command(label="Gaming", command=lambda: self.apply_named_profile("Gaming"))
        menu.add_command(label="Clean Visuals", command=lambda: self.apply_named_profile("Clean Visuals"))
        menu.add_command(label="Talk / Podcast", command=lambda: self.apply_named_profile("Talk / Podcast"))
        menu.tk_popup(event.x_root, event.y_root)


    def _build_data_tools(self):
        ttk.Label(
            self.data_tab,
            text="User Data Backup / Migration",
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w")

        ttk.Label(
            self.data_tab,
            text="Export/import custom profiles, app-control files, boards, images, emoji, adapter templates, and enabled non-core adapters between SBC versions. Logs/caches/runtime heartbeats are excluded.",
            wraplength=1050
        ).pack(anchor="w", pady=4)

        bar = FlowFrame(self.data_tab)
        bar.pack(fill="x", pady=6)
        bar.add_button("Export User Data Backup", self.export_user_data_backup_ui)
        bar.add_button("Import User Data Backup", self.import_user_data_backup_ui)
        bar.add_button("Dry-Run Import Backup", self.dry_run_import_user_data_ui)
        bar.add_button("Refresh Backup List", self.refresh_backup_tools)
        bar.add_button("Dry-Run Latest Previous Build", lambda: self.migrate_latest_previous_build_ui(dry_run=True))
        bar.add_button("Migrate Latest Previous Build", lambda: self.migrate_latest_previous_build_ui(dry_run=False))

        self.backup_status_var = tk.StringVar(value="Backup tools ready.")
        ttk.Label(self.data_tab, textvariable=self.backup_status_var, wraplength=1050).pack(anchor="w", pady=4)

        self.backup_tree = self._tree(
            self.data_tab,
            ("name", "size", "modified", "path"),
            ("Backup", "Size KB", "Modified", "Path"),
            height=12,
        )

        self.refresh_backup_tools()

    def refresh_backup_tools(self):
        if not hasattr(self, "backup_tree"):
            return

        result = list_local_backups()
        for item in self.backup_tree.get_children():
            self.backup_tree.delete(item)

        import time as _time
        for entry in result.get("backups", []):
            size_kb = round(float(entry.get("size_bytes", 0)) / 1024.0, 1)
            modified = _time.strftime("%Y-%m-%d %H:%M:%S", _time.localtime(float(entry.get("modified", 0))))
            self.backup_tree.insert("", "end", values=(entry.get("name", ""), size_kb, modified, entry.get("path", "")))

        self.backup_status_var.set(f"Backup folder: {result.get('backup_dir')} | {result.get('count', 0)} backup(s).")

    def export_user_data_backup_ui(self):
        default_name = "sbc_user_data_backup.zip"
        path = filedialog.asksaveasfilename(
            title="Export SBC user data backup",
            defaultextension=".zip",
            initialfile=default_name,
            filetypes=[("ZIP backup", "*.zip"), ("All files", "*.*")]
        )
        if not path:
            return

        result = create_backup(path)
        if result.get("ok"):
            self.backup_status_var.set(f"Exported backup: {result.get('backup_path')} ({result.get('item_count')} item(s))")
        else:
            self.backup_status_var.set(result.get("error", "Backup export failed."))
        self.refresh_backup_tools()

    def _pick_backup_file(self) -> str:
        return filedialog.askopenfilename(
            title="Select SBC user data backup",
            filetypes=[("ZIP backup", "*.zip"), ("All files", "*.*")]
        )

    def dry_run_import_user_data_ui(self):
        path = self._pick_backup_file()
        if not path:
            return

        inspect = inspect_backup(path)
        if not inspect.get("ok"):
            self.backup_status_var.set(inspect.get("error", "Backup inspection failed."))
            return

        result = import_backup(path, dry_run=True, make_preimport_backup=False)
        self.backup_status_var.set(
            f"Dry-run import: {result.get('copied_count')} would copy, {result.get('skipped_count')} skipped, {result.get('rejected_count')} rejected."
        )

    def migrate_latest_previous_build_ui(self, dry_run: bool = False):
        result = migrate_latest_previous_build(dry_run=dry_run)
        if result.get("ok"):
            mode = "Dry-run" if dry_run else "Migrated"
            self.backup_status_var.set(
                f"{mode} latest previous build: {result.get('copied_count', 0)} copied, {result.get('skipped_count', 0)} skipped. Restart console after a real migrate."
            )
            self.refresh_adapter_templates() if hasattr(self, "adapter_template_tree") else None
            self.refresh_backup_tools()
        else:
            found = find_previous_builds()
            self.backup_status_var.set(result.get("error", f"No previous build found. Checked {found.get('count', 0)} folders."))


    def import_user_data_backup_ui(self):
        path = self._pick_backup_file()
        if not path:
            return

        inspect = inspect_backup(path)
        if not inspect.get("ok"):
            self.backup_status_var.set(inspect.get("error", "Backup inspection failed."))
            return

        item_count = inspect.get("item_count", 0)
        if not messagebox.askyesno(
            "Import SBC user data backup",
            f"Import {item_count} user-data item(s) from this backup?\n\nA pre-import backup of current user data will be created first."
        ):
            return

        result = import_backup(path, overwrite=True, make_preimport_backup=True, dry_run=False)
        if result.get("ok"):
            self.backup_status_var.set(
                f"Imported backup: {result.get('copied_count')} copied, {result.get('rejected_count')} rejected. Pre-import backup: {result.get('preimport_backup')}"
            )
            self.refresh_profiles()
            self.refresh_startup_controls()
        else:
            self.backup_status_var.set(result.get("error", "Backup import failed."))
        self.refresh_backup_tools()

    def _build_console_copier(self):
        ttk.Label(
            self.console_tab,
            text="Console Copier / Multi-Instance Manager",
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w")

        ttk.Label(
            self.console_tab,
            text="Create isolated .sbconsole console-copy files. Each copy can have its own user_data, app controls, profiles, adapter templates, and enabled adapters. Use this when you want a second or third Streamer Board & Console setup for a different show/workflow.",
            wraplength=1050
        ).pack(anchor="w", pady=4)

        bar = FlowFrame(self.console_tab)
        bar.pack(fill="x", pady=6)
        bar.add_button("Create Console Copy", self.create_console_copy_ui)
        bar.add_button("Refresh Copies", self.refresh_console_copies)
        bar.add_button("Launch Selected Copy", self.launch_selected_console_copy_ui)
        bar.add_button("Inspect Selected", self.inspect_selected_console_copy_ui)
        bar.add_button("Clean Selftest/Broken Copies", self.cleanup_console_copies_ui)

        editor = ttk.LabelFrame(self.console_tab, text="New Console Copy")
        editor.pack(fill="x", pady=6)
        row = ttk.Frame(editor)
        row.pack(fill="x", padx=6, pady=6)
        ttk.Label(row, text="Name:").pack(side="left")
        self.console_copy_name_var = tk.StringVar(value="Streamer Console Copy")
        ttk.Entry(row, textvariable=self.console_copy_name_var, width=42).pack(side="left", padx=4)
        self.console_copy_clone_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row, text="Clone current profiles/templates/adapters", variable=self.console_copy_clone_var).pack(side="left", padx=8)

        self.console_status_var = tk.StringVar(value="Console Copier ready.")
        ttk.Label(self.console_tab, textvariable=self.console_status_var, wraplength=1050).pack(anchor="w", pady=4)

        self.console_tree = self._tree(
            self.console_tab,
            ("id", "name", "status", "launchable", "created", "data", "file"),
            ("ID", "Name", "Status", "Launchable", "Created", "Data Root", ".sbconsole File"),
            height=12,
        )
        self.console_tree.bind("<Double-1>", lambda _e: self.inspect_selected_console_copy_ui())
        self.refresh_console_copies()

    def selected_console_file(self) -> str:
        if not hasattr(self, "console_tree"):
            return ""
        selected = self.console_tree.selection()
        if not selected:
            return ""
        values = self.console_tree.item(selected[0], "values")
        return str(values[6]) if len(values) >= 7 else ""

    def refresh_console_copies(self):
        if not hasattr(self, "console_tree"):
            return
        result = list_console_files()
        for item in self.console_tree.get_children():
            self.console_tree.delete(item)
        for row in result.get("consoles", []):
            self.console_tree.insert(
                "",
                "end",
                values=(
                    row.get("console_id", ""),
                    row.get("name", ""),
                    row.get("status", ""),
                    "YES" if row.get("launchable") else "no",
                    row.get("created_at_text", ""),
                    row.get("data_root", ""),
                    row.get("console_file", ""),
                ),
            )
        self.console_status_var.set(
            f"Console copies: {result.get('count', 0)} | Folder: {result.get('console_dir', '')}"
        )

    def create_console_copy_ui(self):
        name = self.console_copy_name_var.get() if hasattr(self, "console_copy_name_var") else ""
        clone_current = bool(self.console_copy_clone_var.get()) if hasattr(self, "console_copy_clone_var") else True
        result = create_console_copy(name=name, clone_current=clone_current)
        if result.get("ok"):
            self.console_status_var.set(
                f"Created {result.get('console_id')}. File: {result.get('console_file')}"
            )
        else:
            self.console_status_var.set(result.get("error", "Console copy failed."))
        self.refresh_console_copies()

    def inspect_selected_console_copy_ui(self):
        path = self.selected_console_file()
        if not path:
            self.console_status_var.set("Select a .sbconsole row first.")
            return
        result = read_console_file(path)
        if result.get("ok"):
            data = result.get("console", {})
            exists = result.get("exists", {})
            self.console_status_var.set(
                f"{data.get('name', data.get('console_id'))}: data={exists.get('data_root')}, adapters={exists.get('adapter_dir')}, templates={exists.get('template_dir')} | {path}"
            )
        else:
            self.console_status_var.set(result.get("error", "Console inspect failed."))

    def cleanup_console_copies_ui(self):
        result = cleanup_selftest_and_broken_copies()
        self.console_status_var.set(
            f"Cleaned console copies: removed {result.get('removed_count', 0)}, kept {result.get('kept_count', 0)}."
        )
        self.refresh_console_copies()

    def launch_selected_console_copy_ui(self):
        path = self.selected_console_file()
        if not path:
            self.console_status_var.set("Select a .sbconsole row first.")
            return
        result = launch_console_copy(path)
        if result.get("ok"):
            self.console_status_var.set(result.get("message", "Launched console copy."))
        else:
            self.console_status_var.set(result.get("error", "Console launch failed."))


    def _build_release_prep(self):
        ttk.Label(
            self.release_tab,
            text="Release Prep / GitHub Upload Builder",
            font=("TkDefaultFont", 12, "bold")
        ).pack(anchor="w")

        ttk.Label(
            self.release_tab,
            text="Build a clean public GitHub upload folder. This excludes .venv, logs, cache, backups, console-copy runtime data, and generated export folders. It also writes release notes, public checklists, and companion-app update notes.",
            wraplength=1050,
        ).pack(anchor="w", pady=4)

        bar = FlowFrame(self.release_tab)
        bar.pack(fill="x", pady=6)
        bar.add_button("Build GitHub Upload Folder", self.build_release_prep_ui)
        bar.add_button("Inspect Latest Export", self.inspect_release_prep_ui)
        bar.add_button("Clean Release Exports", self.clean_release_prep_ui)

        self.release_status_var = tk.StringVar(value="Release Prep ready.")
        ttk.Label(self.release_tab, textvariable=self.release_status_var, wraplength=1050).pack(anchor="w", pady=4)

        self.release_tree = self._tree(
            self.release_tab,
            ("item", "detail"),
            ("Item", "Detail"),
            height=16,
        )
        self.refresh_release_prep()

    def _release_tree_set(self, rows):
        if not hasattr(self, "release_tree"):
            return
        for item in self.release_tree.get_children():
            self.release_tree.delete(item)
        for item, detail in rows:
            self.release_tree.insert("", "end", values=(str(item), str(detail)))

    def refresh_release_prep(self):
        folder = latest_release_folder()
        result = inspect_release_folder(folder)
        rows = [
            ("Latest export", result.get("release_dir", str(folder))),
            ("Exists", result.get("exists", False)),
            ("Release OK", result.get("ok", False)),
        ]
        missing = [k for k, v in result.get("required", {}).items() if not v]
        forbidden = result.get("forbidden_present", {})
        rows.append(("Missing required", ", ".join(missing) if missing else "none"))
        rows.append(("Forbidden runtime data", json_dump_short(forbidden) if forbidden else "none"))
        self._release_tree_set(rows)
        self.release_status_var.set(f"Release export: {result.get('release_dir', str(folder))} | OK={result.get('ok', False)}")

    def build_release_prep_ui(self):
        result = build_github_upload()
        if result.get("ok"):
            self.release_status_var.set(
                f"Built GitHub upload folder: {result.get('release_dir')} ({result.get('copied_count', 0)} files copied)."
            )
        else:
            self.release_status_var.set(result.get("error", "Release prep build failed."))
        self.refresh_release_prep()

    def inspect_release_prep_ui(self):
        self.refresh_release_prep()

    def clean_release_prep_ui(self):
        if not messagebox.askyesno("Clean release exports", "Remove generated GitHub upload export folders?"):
            return
        result = clean_release_exports()
        self.release_status_var.set(f"Cleaned release exports: removed {result.get('removed_count', 0)} folder(s).")
        self.refresh_release_prep()

    def _build_doctor(self):
        bar = FlowFrame(self.doctor_tab)
        bar.pack(fill="x", pady=4)
        bar.add_button("Run Doctor", self.refresh_doctor)
        self.doctor_tree = self._tree(
            self.doctor_tab,
            ("status", "item", "detail"),
            ("Status", "Item", "Detail")
        )

    def action(self, message: str):
        self.status_var.set(message.replace("\n", " | "))
        self.refresh_all()

    def write_hotkey_control(self, app, enabled: bool):
        path = app.write_control(hotkeys_enabled=enabled)
        self.status_var.set(f"Wrote control file: {path}")

    def refresh_all(self):
        self.refresh_boards()
        self.refresh_resources()
        self.refresh_hotkeys()
        self.refresh_doctor()
        if hasattr(self, "profile_combo"):
            self.refresh_profiles()
        if hasattr(self, "startup_enabled_var"):
            self.refresh_startup_controls()
        if hasattr(self, "backup_tree"):
            self.refresh_backup_tools()
        if hasattr(self, "adapter_template_tree"):
            self.refresh_adapter_templates()
        if hasattr(self, "console_tree"):
            self.refresh_console_copies()
        if hasattr(self, "release_tree"):
            self.refresh_release_prep()

    def remember_dashboard_selection(self):
        key = remember_tree_selection(self.resource_tree, 0)
        if key and key != "total":
            self.dashboard_selected_key = key

    def remember_board_selection(self):
        key = remember_tree_selection(self.boards_tree, 0)
        if key:
            self.board_selected_key = key
            self.selected_board_var.set(self.board_label_for_id(key))

    def dashboard_left_click(self, event):
        iid = self.resource_tree.identify_row(event.y)
        if not iid:
            return "break"
        return None

    def board_left_click(self, event):
        iid = self.boards_tree.identify_row(event.y)
        if not iid:
            return "break"
        return None

    def refresh_resources(self):
        selected_key = self.dashboard_selected_key or remember_tree_selection(self.resource_tree, 0)

        for item in self.resource_tree.get_children():
            self.resource_tree.delete(item)

        total_ram = 0.0
        total_cpu = 0.0

        for app_id, app in self.apps.items():
            snap = snapshot_process_tree(app.pid)
            total_ram += snap.rss_mb
            total_cpu += snap.cpu_percent
            state = "Paused/Parked" if app.suspended and snap.running else ("Running" if snap.running else "Closed")
            key = f"app:{app_id}"
            self.resource_tree.insert("", "end", iid=key, values=(
                key,
                "App",
                app.display_name,
                state,
                snap.pid or "",
                f"{snap.rss_mb:.1f}",
                f"{snap.cpu_percent:.1f}",
                snap.children
            ))

        for board in self.board_instances:
            snap = snapshot_process_tree(board.pid)
            total_ram += snap.rss_mb
            total_cpu += snap.cpu_percent
            state = "Running" if board.running else "Stale/Closed"
            key = f"board:{board.instance_id}"
            self.resource_tree.insert("", "end", iid=key, values=(
                key,
                "Pin Board",
                board.display_name,
                state,
                snap.pid or "",
                f"{snap.rss_mb:.1f}",
                f"{snap.cpu_percent:.1f}",
                snap.children
            ))

        self.resource_tree.insert("", "end", iid="total", values=("total", "TOTAL TRACKED", "", "", "", f"{total_ram:.1f}", f"{total_cpu:.1f}", ""))
        restore_tree_selection(self.resource_tree, selected_key, 0)

    def refresh_hotkeys(self):
        selected_key = remember_tree_selection(self.hotkey_tree, 1)
        for item in self.hotkey_tree.get_children():
            self.hotkey_tree.delete(item)

        rows = collect_hotkeys(self.apps)
        conflicts = find_conflicts(rows)
        conflict_keys = set(conflicts.keys())

        for row in rows:
            status = "CONFLICT" if row["key"] in conflict_keys else "OK"
            self.hotkey_tree.insert("", "end", values=(status, row["key"], row["app"], row["action"]))

        restore_tree_selection(self.hotkey_tree, selected_key, 1)

    def refresh_boards(self):
        selected_key = self.board_selected_key or self.selected_board_id()
        self.board_instances = scan_board_instances(include_stale=False)

        values = [self.board_label(b) for b in self.board_instances]
        self.board_combo.configure(values=values)
        if selected_key and any(b.instance_id == selected_key for b in self.board_instances):
            self.selected_board_var.set(self.board_label_for_id(selected_key))
        elif values and self.selected_board_var.get() not in values:
            self.selected_board_var.set(values[0])
            self.board_selected_key = self.selected_board_id()
        elif not values:
            self.selected_board_var.set("")
            self.board_selected_key = ""

        if hasattr(self, "boards_tree"):
            for item in self.boards_tree.get_children():
                self.boards_tree.delete(item)

            for board in self.board_instances:
                status = read_board_status(board.instance_id)
                self.boards_tree.insert("", "end", iid=board.instance_id, values=(
                    board.instance_id,
                    "Running" if board.running else "Stale/Closed",
                    board.pid or "",
                    status.get("pin_count", 0),
                    status.get("resource_mode", ""),
                    status.get("controller_title", board.controller_title),
                    status.get("output_title", board.output_title),
                ))

            restore_tree_selection(self.boards_tree, selected_key, 0)

        self.refresh_open_board_tabs()

    def board_label(self, board):
        return f"{board.display_name} [{board.instance_id}]"

    def board_label_for_id(self, board_id: str) -> str:
        for board in self.board_instances:
            if board.instance_id == board_id:
                return self.board_label(board)
        return self.selected_board_var.get()

    def board_combo_changed(self):
        self.board_selected_key = self.selected_board_id()
        restore_tree_selection(self.boards_tree, self.board_selected_key, 0)

    def selected_board_id(self) -> str:
        value = self.selected_board_var.get()
        if "[" in value and "]" in value:
            return value.rsplit("[", 1)[1].rstrip("]")
        return self.board_selected_key

    def selected_dashboard_key(self) -> str:
        key = remember_tree_selection(self.resource_tree, 0)
        if key and key != "total":
            self.dashboard_selected_key = key
        return self.dashboard_selected_key

    def selected_app_from_dashboard(self):
        key = self.selected_dashboard_key()
        if key.startswith("app:"):
            return self.apps.get(key.split(":", 1)[1])
        return None

    def selected_board_from_dashboard(self) -> str:
        key = self.selected_dashboard_key()
        if key.startswith("board:"):
            return key.split(":", 1)[1]
        return ""

    def dashboard_context_menu(self, event):
        iid = tree_select_under_pointer(self.resource_tree, event)
        if not iid or iid == "total":
            return

        values = self.resource_tree.item(iid, "values")
        key = str(values[0])
        self.dashboard_selected_key = key

        menu = tk.Menu(self.root, tearoff=0)
        if key.startswith("app:"):
            app = self.apps.get(key.split(":", 1)[1])
            if app:
                menu.add_command(label=f"Launch {app.display_name}", command=lambda: self.action(app.launch()))
                menu.add_command(label="Close", command=lambda: self.action(app.close()))
                menu.add_command(label="Restart", command=lambda: self.action(app.restart()))
                menu.add_separator()
                menu.add_command(label="Pause & Park", command=lambda: self.action(app.pause_park()))
                menu.add_command(label="Resume", command=lambda: self.action(app.resume()))
                menu.add_separator()
                menu.add_command(label="Hotkeys OFF", command=lambda: self.write_hotkey_control(app, False))
                menu.add_command(label="Hotkeys ON", command=lambda: self.write_hotkey_control(app, True))
        elif key.startswith("board:"):
            board_id = key.split(":", 1)[1]
            menu.add_command(label="Rise Controller", command=lambda: send_board_command(board_id, "rise_to_top"))
            menu.add_command(label="Rise Pin-Out", command=lambda: send_board_command(board_id, "rise_output"))
            menu.add_command(label="Bring-in as Tab", command=lambda: self.open_board_tab(board_id))
            menu.add_command(label="Controller Always Top", command=lambda: send_board_command(board_id, "set_topmost", {"enabled": True}))
            menu.add_command(label="Controller Normal", command=lambda: send_board_command(board_id, "set_topmost", {"enabled": False}))
            menu.add_separator()
            menu.add_command(label="Emergency Freeze", command=lambda: send_board_command(board_id, "emergency_freeze"))
            menu.add_command(label="Kill w/Mem", command=lambda: self.context_kill_board_with_mem(board_id))
            menu.add_command(label="Close Board", command=lambda: send_board_command(board_id, "close"))
        menu.add_separator()
        menu.add_command(label="Refresh", command=self.refresh_all)
        menu.tk_popup(event.x_root, event.y_root)

    def launch_pin_board(self):
        try:
            instance_id, _proc = launch_board()
            self.status_var.set(f"Launched Pin Board instance: {instance_id}")
            self.root.after(1200, self.refresh_all)
        except Exception as exc:
            messagebox.showerror("Pin Board launch failed", str(exc))

    def board_rise_to_top(self):
        board_id = self.selected_board_id()
        if not board_id:
            self.status_var.set("No Pin Board selected.")
            return
        send_board_command(board_id, "rise_to_top")
        self.status_var.set(f"Rise Controller sent to {board_id}")

    def board_rise_output(self):
        board_id = self.selected_board_id()
        if not board_id:
            self.status_var.set("No Pin Board selected.")
            return
        send_board_command(board_id, "rise_output")
        self.status_var.set(f"Rise Pin-Out sent to {board_id}")

    def board_set_topmost(self, enabled: bool):
        board_id = self.selected_board_id()
        if not board_id:
            self.status_var.set("No Pin Board selected.")
            return
        send_board_command(board_id, "set_topmost", {"enabled": enabled})
        self.status_var.set(f"Controller topmost={enabled} sent to {board_id}")

    def board_freeze(self):
        board_id = self.selected_board_id()
        if not board_id:
            self.status_var.set("No Pin Board selected.")
            return
        send_board_command(board_id, "emergency_freeze")
        self.status_var.set(f"Emergency Freeze sent to {board_id}")

    def board_kill_with_mem(self):
        board_id = self.selected_board_id()
        if not board_id:
            self.status_var.set("No Pin Board selected.")
            return
        self.context_kill_board_with_mem(board_id)

    def board_close(self):
        board_id = self.selected_board_id()
        if not board_id:
            self.status_var.set("No Pin Board selected.")
            return
        send_board_command(board_id, "close")
        self.status_var.set(f"Close sent to {board_id}")
        self.root.after(800, self.refresh_all)

    def board_context_menu(self, event):
        iid = tree_select_under_pointer(self.boards_tree, event)
        if not iid:
            return

        self.board_selected_key = iid
        self.selected_board_var.set(self.board_label_for_id(iid))

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Rise Controller", command=lambda: send_board_command(iid, "rise_to_top"))
        menu.add_command(label="Rise Pin-Out", command=lambda: send_board_command(iid, "rise_output"))
        menu.add_command(label="Bring-in as Tab", command=lambda: self.open_board_tab(iid))
        menu.add_command(label="Controller Always Top", command=lambda: send_board_command(iid, "set_topmost", {"enabled": True}))
        menu.add_command(label="Controller Normal", command=lambda: send_board_command(iid, "set_topmost", {"enabled": False}))
        menu.add_separator()
        menu.add_command(label="Emergency Freeze", command=lambda: send_board_command(iid, "emergency_freeze"))
        menu.add_command(label="Lock Board", command=lambda: send_board_command(iid, "toggle_lock", {"locked": True}))
        menu.add_command(label="Unlock Board", command=lambda: send_board_command(iid, "toggle_lock", {"locked": False}))
        menu.add_separator()
        menu.add_command(label="Static Mode", command=lambda: send_board_command(iid, "set_resource_mode", {"mode": "Static"}))
        menu.add_command(label="Light Mode", command=lambda: send_board_command(iid, "set_resource_mode", {"mode": "Light"}))
        menu.add_command(label="Normal Mode", command=lambda: send_board_command(iid, "set_resource_mode", {"mode": "Normal"}))
        menu.add_command(label="Performance Mode", command=lambda: send_board_command(iid, "set_resource_mode", {"mode": "Performance"}))
        menu.add_separator()
        menu.add_command(label="Kill w/Mem", command=lambda: self.context_kill_board_with_mem(iid))
        menu.add_command(label="Close Board", command=lambda: send_board_command(iid, "close"))
        menu.add_command(label="Refresh", command=self.refresh_all)
        menu.tk_popup(event.x_root, event.y_root)

    def bring_board_as_tab(self):
        board_id = self.selected_board_id()
        if not board_id:
            self.status_var.set("No Pin Board selected.")
            return
        self.open_board_tab(board_id)

    def open_board_tab(self, board_id: str):
        if board_id in self.board_control_tabs:
            self.tabs.select(self.board_control_tabs[board_id])
            self.status_var.set(f"Board tab already open for {board_id}")
            return

        frame = ttk.Frame(self.tabs, padding=8)
        self.board_control_tabs[board_id] = frame
        self.tabs.add(frame, text=f"Board {board_id[:4]}")
        self.build_board_remote_tab(frame, board_id)
        self.tabs.select(frame)
        self.status_var.set(f"Remote board control tab opened for {board_id}")

    def build_board_remote_tab(self, frame: ttk.Frame, board_id: str):
        header_var = tk.StringVar(value=f"Remote controls for Pin Board {board_id}")
        ttk.Label(frame, textvariable=header_var, font=("TkDefaultFont", 13, "bold")).pack(anchor="w")

        info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=info_var, wraplength=1000).pack(anchor="w", pady=4)

        bar = FlowFrame(frame)
        bar.pack(fill="x", pady=6)
        bar.add_button("Rise Controller", lambda: send_board_command(board_id, "rise_to_top"))
        bar.add_button("Rise Pin-Out", lambda: send_board_command(board_id, "rise_output"))
        bar.add_button("Always Top", lambda: send_board_command(board_id, "set_topmost", {"enabled": True}))
        bar.add_button("Normal", lambda: send_board_command(board_id, "set_topmost", {"enabled": False}))
        bar.add_button("Emergency Freeze", lambda: send_board_command(board_id, "emergency_freeze"))
        bar.add_button("Kill w/Mem", lambda: self.context_kill_board_with_mem(board_id))
        bar.add_button("Lock", lambda: send_board_command(board_id, "toggle_lock", {"locked": True}))
        bar.add_button("Unlock", lambda: send_board_command(board_id, "toggle_lock", {"locked": False}))

        mode_group = bar.add_group("Resource Mode:")
        mode_var = tk.StringVar(value="Static")
        mode_combo = ttk.Combobox(mode_group, textvariable=mode_var, values=["Static", "Light", "Normal", "Performance"], width=13, state="readonly")
        mode_combo.pack(side="left")
        mode_combo.bind("<<ComboboxSelected>>", lambda _e: send_board_command(board_id, "set_resource_mode", {"mode": mode_var.get()}))

        pin_group = bar.add_group("Pin:")
        pin_var = tk.StringVar(value="")
        pin_combo = ttk.Combobox(pin_group, textvariable=pin_var, values=[], width=32, state="readonly")
        pin_combo.pack(side="left")

        nudge = ttk.LabelFrame(frame, text="Selected Pin Quick Nudge", padding=8)
        nudge.pack(anchor="w", pady=8)

        def selected_pin_id():
            value = pin_var.get()
            if "[" in value and "]" in value:
                return value.rsplit("[", 1)[1].rstrip("]")
            return ""

        def send_nudge(dx, dy):
            pin_id = selected_pin_id()
            if pin_id:
                send_board_command(board_id, "nudge", {"pin_id": pin_id, "dx": dx, "dy": dy})

        nbar = FlowFrame(nudge)
        nbar.pack(fill="x")
        nbar.add_button("Nudge ↑", lambda: send_nudge(0, -5))
        nbar.add_button("Nudge ↓", lambda: send_nudge(0, 5))
        nbar.add_button("Nudge ←", lambda: send_nudge(-5, 0))
        nbar.add_button("Nudge →", lambda: send_nudge(5, 0))

        pins_tree = self._tree(
            frame,
            ("id", "name", "x", "y", "z"),
            ("Pin ID", "Name", "X", "Y", "Z"),
            height=10,
        )
        pins_tree.bind("<Button-3>", lambda e: self.remote_pin_context_menu(e, pins_tree, board_id, pin_var))
        pins_tree.bind("<Button-1>", lambda e: "break" if not pins_tree.identify_row(e.y) else None)

        def refresh_remote():
            status = read_board_status(board_id)
            pins = status.get("pins", [])
            mode_var.set(status.get("resource_mode", "Static"))
            info_var.set(
                f"PID: {status.get('pid', '')} | Pins: {status.get('pin_count', 0)} | "
                f"Locked: {status.get('locked', False)} | Output topmost: {status.get('output_topmost', False)} | "
                f"Output: {status.get('output_title', '')}"
            )

            old = pin_var.get()
            values = [f"{pin.get('name', '')} [{pin.get('id', '')}]" for pin in pins]
            pin_combo.configure(values=values)
            if values and old not in values:
                pin_var.set(values[0])
            elif not values:
                pin_var.set("")

            selected_pin_key = remember_tree_selection(pins_tree, 0)
            for item in pins_tree.get_children():
                pins_tree.delete(item)
            for pin in pins:
                pin_id = str(pin.get("id", ""))
                pins_tree.insert("", "end", iid=pin_id, values=(
                    pin_id,
                    pin.get("name", ""),
                    f"{float(pin.get('x', 0)):.1f}",
                    f"{float(pin.get('y', 0)):.1f}",
                    pin.get("z", ""),
                ))
            restore_tree_selection(pins_tree, selected_pin_key, 0)

            frame.after(1200, refresh_remote)

        refresh_remote()

    def remote_pin_context_menu(self, event, tree, board_id: str, pin_var):
        iid = tree_select_under_pointer(tree, event)
        if not iid:
            return
        values = tree.item(iid, "values")
        pin_name = values[1] if len(values) > 1 else iid
        pin_var.set(f"{pin_name} [{iid}]")
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Select Pin", command=lambda: send_board_command(board_id, "select_pin", {"pin_id": iid}))
        menu.add_separator()
        menu.add_command(label="Nudge ↑", command=lambda: send_board_command(board_id, "nudge", {"pin_id": iid, "dx": 0, "dy": -5}))
        menu.add_command(label="Nudge ↓", command=lambda: send_board_command(board_id, "nudge", {"pin_id": iid, "dx": 0, "dy": 5}))
        menu.add_command(label="Nudge ←", command=lambda: send_board_command(board_id, "nudge", {"pin_id": iid, "dx": -5, "dy": 0}))
        menu.add_command(label="Nudge →", command=lambda: send_board_command(board_id, "nudge", {"pin_id": iid, "dx": 5, "dy": 0}))
        menu.add_separator()
        menu.add_command(label="Rise Controller", command=lambda: send_board_command(board_id, "rise_to_top"))
        menu.add_command(label="Rise Pin-Out", command=lambda: send_board_command(board_id, "rise_output"))
        menu.tk_popup(event.x_root, event.y_root)

    def context_kill_board_with_mem(self, board_id: str):
        result = kill_board_with_mem(board_id)
        if result.get("passed"):
            self.status_var.set(f"Kill w/Mem: {board_id} -> {result.get('new_instance_id')}")
            self.root.after(1500, self.refresh_all)
        else:
            self.status_var.set(f"Kill w/Mem failed: {result.get('error')}")

    def refresh_open_board_tabs(self):
        pass

    def refresh_doctor(self):
        selected_key = remember_tree_selection(self.doctor_tree, 1)
        for item in self.doctor_tree.get_children():
            self.doctor_tree.delete(item)

        for row in run_doctor(self.apps):
            self.doctor_tree.insert("", "end", values=(row["status"], row["item"], row["detail"]))
        restore_tree_selection(self.doctor_tree, selected_key, 1)

    def emergency_reset(self):
        for app in self.apps.values():
            try:
                app.write_control(hotkeys_enabled=False)
            except Exception:
                pass

        for board in scan_board_instances(include_stale=False):
            try:
                send_board_command(board.instance_id, "emergency_freeze")
                send_board_command(board.instance_id, "set_resource_mode", {"mode": "Static"})
            except Exception:
                pass

        self.status_var.set("Emergency reset: wrote hotkeys OFF controls and froze active Pin Boards.")

    def monitor_tick(self):
        if getattr(self, "_shutdown_requested", False):
            return
        try:
            self.refresh_boards()
            self.refresh_resources()
        except KeyboardInterrupt:
            self.shutdown()
            return
        except Exception as exc:
            try:
                self.status_var.set(f"Monitor warning: {exc}")
            except Exception:
                pass
        if not getattr(self, "_shutdown_requested", False):
            self.root.after(1800, self.monitor_tick)

    def run(self):
        try:
            self.force_window_visible()
            self.root.mainloop()
        except KeyboardInterrupt:
            self.shutdown()

def main():
    app = StreamerBoardConsole()
    try:
        signal.signal(signal.SIGINT, lambda _sig, _frame: app.root.after(0, app.shutdown))
    except Exception:
        pass
    app.run()

if __name__ == "__main__":
    main()
