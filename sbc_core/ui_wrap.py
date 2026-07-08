from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

class FlowFrame(ttk.Frame):
    """A simple wrapping frame for control groups.

    Each group is a child frame. Groups wrap as whole objects, so labels and
    their related controls move together instead of being split across rows.
    """

    def __init__(self, master, pad_x: int = 4, pad_y: int = 4, min_item_width: int = 1, **kwargs):
        super().__init__(master, **kwargs)
        self.pad_x = pad_x
        self.pad_y = pad_y
        self.min_item_width = min_item_width
        self._items: list[ttk.Frame] = []
        self.bind("<Configure>", lambda _e: self.reflow_later())

    def add_group(self, label: str | None = None) -> ttk.Frame:
        group = ttk.Frame(self)
        if label:
            ttk.Label(group, text=label).pack(side="left", padx=(0, 3))
        self._items.append(group)
        group.bind("<Configure>", lambda _e: self.reflow_later())
        self.reflow_later()
        return group

    def add_button(self, text: str, command: Callable) -> ttk.Button:
        group = self.add_group()
        btn = ttk.Button(group, text=text, command=command)
        btn.pack(side="left")
        return btn

    def reflow_later(self) -> None:
        self.after_idle(self.reflow)

    def reflow(self) -> None:
        width = max(1, self.winfo_width())
        x = self.pad_x
        y = self.pad_y
        row_h = 0

        for group in self._items:
            group.update_idletasks()
            gw = max(self.min_item_width, group.winfo_reqwidth())
            gh = max(1, group.winfo_reqheight())

            if x > self.pad_x and x + gw + self.pad_x > width:
                x = self.pad_x
                y += row_h + self.pad_y
                row_h = 0

            group.place(x=x, y=y, width=gw, height=gh)
            x += gw + self.pad_x
            row_h = max(row_h, gh)

        total_h = y + row_h + self.pad_y
        self.configure(height=total_h)
