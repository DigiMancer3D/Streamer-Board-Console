from __future__ import annotations

import tkinter as tk
from tkinter import ttk

def tree_select_under_pointer(tree: ttk.Treeview, event) -> str:
    iid = tree.identify_row(event.y)
    if iid:
        tree.selection_set(iid)
        tree.focus(iid)
    return iid

def remember_tree_selection(tree: ttk.Treeview, key_column_index: int = 0) -> str:
    sel = tree.selection()
    if not sel:
        return ""
    values = tree.item(sel[0], "values")
    if values and len(values) > key_column_index:
        return str(values[key_column_index])
    return ""

def restore_tree_selection(tree: ttk.Treeview, key_value: str, key_column_index: int = 0) -> None:
    if not key_value:
        return
    for iid in tree.get_children():
        values = tree.item(iid, "values")
        if values and len(values) > key_column_index and str(values[key_column_index]) == str(key_value):
            tree.selection_set(iid)
            tree.focus(iid)
            tree.see(iid)
            return
