# ui package
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def make_scrollable_left_panel(pw: ttk.PanedWindow, width: int = 290) -> ttk.Frame:
    """Create a scrollable controls panel and add it as the left pane of *pw*.

    Returns the inner ttk.Frame where controls should be packed.
    The panel is exactly *width* pixels wide and gains a vertical scrollbar
    when its content is taller than the visible area.
    """
    outer = ttk.Frame(pw, width=width)
    outer.pack_propagate(False)
    pw.add(outer, weight=0)

    canvas = tk.Canvas(outer, highlightthickness=0)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = ttk.Frame(canvas)
    win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _update_scroll_region(event: tk.Event | None = None) -> None:
        bounds = canvas.bbox("all")
        if bounds is None:
            return
        canvas.configure(scrollregion=bounds)
        needs_scrollbar = bounds[3] - bounds[1] > canvas.winfo_height()
        if needs_scrollbar and not scrollbar.winfo_manager():
            scrollbar.pack(side="right", fill="y")
        elif not needs_scrollbar and scrollbar.winfo_manager():
            scrollbar.pack_forget()
            canvas.yview_moveto(0)

    inner.bind("<Configure>", _update_scroll_region)

    def _on_canvas_configure(event: tk.Event) -> None:
        canvas.itemconfig(win_id, width=event.width)
        _update_scroll_region()

    canvas.bind("<Configure>", _on_canvas_configure)

    def _on_mousewheel(event: tk.Event) -> None:
        first, last = canvas.yview()
        if first > 0 or last < 1:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    inner.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
    inner.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    return inner
