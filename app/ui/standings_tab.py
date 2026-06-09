"""Standings tab for CFB Stat Card Maker."""
from __future__ import annotations

import datetime
import logging
import os
import threading
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk
from typing import Optional

from PIL import Image, ImageTk

from app.settings import Settings

SCOPE_OPTIONS = [
    "SEC",
    "Big Ten",
    "Big 12",
    "ACC",
    "Pac-12",
    "American Athletic",
    "Mountain West",
    "Sun Belt",
    "MAC",
    "Conference USA",
    "Independents",
]

THUMB_W = 480
THUMB_H = 320

logger = logging.getLogger(__name__)


def _full_preview_window(parent: tk.Widget, image: "Image.Image") -> None:
    """Open a scrollable full-resolution preview window."""
    import tkinter as tk
    from tkinter import ttk
    from PIL import ImageTk, Image
    top = tk.Toplevel(parent)
    w, h = image.size
    top.title(f"Full Preview — {w} × {h} px")
    sw = int(parent.winfo_screenwidth() * 0.9)
    sh = int(parent.winfo_screenheight() * 0.9)
    disp = image.copy()
    if disp.width > sw or disp.height > sh:
        disp.thumbnail((sw, sh), Image.LANCZOS)
    photo = ImageTk.PhotoImage(disp)
    frame = ttk.Frame(top)
    frame.pack(fill="both", expand=True)
    hbar = ttk.Scrollbar(frame, orient="horizontal")
    vbar = ttk.Scrollbar(frame, orient="vertical")
    canvas = tk.Canvas(frame, scrollregion=(0, 0, disp.width, disp.height),
                       xscrollcommand=hbar.set, yscrollcommand=vbar.set)
    hbar.config(command=canvas.xview)
    vbar.config(command=canvas.yview)
    hbar.pack(side="bottom", fill="x")
    vbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    canvas.create_image(0, 0, anchor="nw", image=photo)
    canvas._photo = photo  # type: ignore[attr-defined]


class StandingsTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, settings: Settings) -> None:
        super().__init__(parent)
        self.settings = settings

        # Internal state
        self._card_image: Optional[Image.Image] = None
        self._thumb_photo: Optional[ImageTk.PhotoImage] = None
        self._fetching: bool = False

        self._build_ui()
        self._load_from_settings()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=8, pady=8)

        # Left: controls panel
        from app.ui import make_scrollable_left_panel
        controls = make_scrollable_left_panel(pw)

        # Right: preview panel
        preview_frame = ttk.LabelFrame(pw, text="Preview")
        pw.add(preview_frame, weight=1)

        self._preview_canvas = tk.Canvas(
            preview_frame, bg="#CCCCCC", width=THUMB_W, height=THUMB_H
        )
        self._preview_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._preview_canvas.bind("<Configure>", self._on_canvas_resize)

        self._build_controls(controls)

    def _build_controls(self, parent: ttk.Frame) -> None:
        self._build_card_size(parent)
        self._build_season(parent)
        self._build_scope(parent)
        self._build_columns(parent)
        self._build_display_options(parent)
        self._build_bg_color(parent)
        self._build_fetch_bar(parent)
        self._build_export(parent)

    # ---- Card Size ----------------------------------------------------

    def _build_card_size(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Card Size")
        lf.pack(fill="x", padx=8, pady=4)

        row1 = ttk.Frame(lf)
        row1.pack(fill="x", padx=6, pady=(4, 0))

        ttk.Label(row1, text="W (in):").pack(side="left")
        self._width_var = tk.StringVar()
        self._width_spin = ttk.Spinbox(
            row1, from_=2.0, to=24.0, increment=0.5,
            textvariable=self._width_var, width=6,
        )
        self._width_spin.pack(side="left", padx=(2, 8))

        ttk.Label(row1, text="H (in):").pack(side="left")
        self._height_var = tk.StringVar()
        self._height_spin = ttk.Spinbox(
            row1, from_=2.0, to=24.0, increment=0.5,
            textvariable=self._height_var, width=6,
        )
        self._height_spin.pack(side="left", padx=(2, 0))

        row2 = ttk.Frame(lf)
        row2.pack(fill="x", padx=6, pady=2)
        self._use_global_var = tk.BooleanVar()
        ttk.Checkbutton(
            row2, text="Use global card size",
            variable=self._use_global_var,
            command=self._on_use_global_size_changed,
        ).pack(side="left")

        self._orient_label = ttk.Label(lf, text="", foreground="#555555")
        self._orient_label.pack(anchor="w", padx=6, pady=(0, 4))

        for var in (self._width_var, self._height_var):
            var.trace_add("write", self._on_size_changed)

        for event in ("<<Increment>>", "<<Decrement>>", "<FocusOut>"):
            self._width_spin.bind(event, self._on_size_changed)
            self._height_spin.bind(event, self._on_size_changed)

    def _on_size_changed(self, *_) -> None:
        try:
            w = float(self._width_var.get())
            h = float(self._height_var.get())
            self._orient_label.config(
                text="(Landscape)" if w >= h else "(Portrait)"
            )
        except ValueError:
            pass
        self._update_col_suggestion()

    def _on_use_global_size_changed(self) -> None:
        if self._use_global_var.get():
            self._width_var.set(str(self.settings.card_width_in))
            self._height_var.set(str(self.settings.card_height_in))
            self._width_spin.config(state="disabled")
            self._height_spin.config(state="disabled")
        else:
            self._width_spin.config(state="normal")
            self._height_spin.config(state="normal")

    # ---- Season -------------------------------------------------------

    def _build_season(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Season")
        lf.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=6, pady=6)

        current_year = datetime.datetime.now().year
        self._season_var = tk.StringVar()
        ttk.Spinbox(
            row, from_=1970, to=current_year,
            textvariable=self._season_var, width=8,
        ).pack(side="left")
        ttk.Label(row, text="(0 = current season)", foreground="#555555").pack(
            side="left", padx=8
        )

    # ---- Scope --------------------------------------------------------

    def _build_scope(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Scope")
        lf.pack(fill="x", padx=8, pady=4)

        self._scope_var = tk.StringVar()
        ttk.Combobox(
            lf, textvariable=self._scope_var,
            values=SCOPE_OPTIONS, state="readonly", width=22,
        ).pack(padx=6, pady=6, anchor="w")

    # ---- Columns ------------------------------------------------------

    def _build_columns(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Columns")
        lf.pack(fill="x", padx=8, pady=4)

        self._col_mode_var = tk.StringVar(value="auto")
        modes = [
            ("auto",     'Auto (suggested)'),
            ("standard", 'Standard  (W L PCT)'),
            ("extended", 'Extended  (+Conf PF PA)'),
        ]
        for val, label in modes:
            ttk.Radiobutton(
                lf, text=label, variable=self._col_mode_var, value=val,
                command=self._update_col_suggestion,
            ).pack(anchor="w", padx=8, pady=1)

        self._col_suggest_label = ttk.Label(
            lf, text="", foreground="#3355CC"
        )
        self._col_suggest_label.pack(anchor="w", padx=8, pady=(0, 4))

    def _update_col_suggestion(self, *_) -> None:
        if self._col_mode_var.get() != "auto":
            self._col_suggest_label.config(text="")
            return
        try:
            from app.cards.standings_card import suggest_column_mode
            w = float(self._width_var.get())
            mode = suggest_column_mode(w)
            self._col_suggest_label.config(
                text=f"\u2192 {'Extended' if mode == 'extended' else 'Standard'} columns suggested"
            )
        except (ValueError, ImportError):
            self._col_suggest_label.config(text="\u2192 (set width to see suggestion)")

    # ---- Display Options ----------------------------------------------

    def _build_display_options(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Display Options")
        lf.pack(fill="x", padx=8, pady=4)

        self._show_logos_var = tk.BooleanVar()
        self._show_timestamp_var = tk.BooleanVar()
        self._show_col_explainers_var = tk.BooleanVar()

        ttk.Checkbutton(lf, text="Show team logos",
                        variable=self._show_logos_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show 'data as of' timestamp",
                        variable=self._show_timestamp_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show column explainers",
                        variable=self._show_col_explainers_var).pack(
            anchor="w", padx=8, pady=(1, 4)
        )

    # ---- Background Color ---------------------------------------------

    def _build_bg_color(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Background Color")
        lf.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=6, pady=6)

        self._bg_color_var = tk.StringVar(value="#FFFFFF")
        self._bg_color_var.trace_add("write", self._update_bg_swatch)

        ttk.Entry(row, textvariable=self._bg_color_var, width=9).pack(
            side="left", padx=(0, 4)
        )
        self._bg_swatch = tk.Label(row, width=3, relief="sunken", background="#FFFFFF")
        self._bg_swatch.pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Pick…", command=self._pick_bg_color).pack(side="left")

    def _update_bg_swatch(self, *_) -> None:
        color = self._bg_color_var.get()
        if color.startswith("#") and len(color) in (4, 7):
            try:
                self._bg_swatch.config(background=color)
            except tk.TclError:
                pass

    def _pick_bg_color(self) -> None:
        result = colorchooser.askcolor(
            color=self._bg_color_var.get(), title="Choose Background Color"
        )
        if result and result[1]:
            self._bg_color_var.set(result[1])

    # ---- Fetch & Preview ----------------------------------------------

    def _build_fetch_bar(self, parent: ttk.Frame) -> None:
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", padx=8, pady=6)

        row1 = ttk.Frame(parent)
        row1.pack(fill="x", padx=8)

        self._fetch_btn = ttk.Button(
            row1, text="Fetch & Preview", command=self._on_fetch
        )
        self._fetch_btn.pack(side="left", padx=(0, 6))

        self._refresh_btn = ttk.Button(
            row1, text="↺ Refresh", width=9, command=self._on_refresh
        )
        self._refresh_btn.pack(side="left")

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", padx=8, pady=(4, 0))

        self._full_preview_btn = ttk.Button(
            row2, text="Full Preview…", command=self._on_full_preview, state="disabled"
        )
        self._full_preview_btn.pack(side="left")

        self._status_label = ttk.Label(
            parent, text="", foreground="#aa2200",
            wraplength=260, justify="left",
        )
        self._status_label.pack(fill="x", padx=8, pady=4)

    def _on_fetch(self) -> None:
        self._start_fetch(bypass_cache=False)

    def _on_refresh(self) -> None:
        self._start_fetch(bypass_cache=True)

    def _start_fetch(self, bypass_cache: bool) -> None:
        if self._fetching:
            return
        self._fetching = True
        self._fetch_btn.config(state="disabled")
        self._refresh_btn.config(state="disabled")
        self._status_label.config(text="Fetching…", foreground="#555555")

        thread = threading.Thread(
            target=self._fetch_thread,
            args=(bypass_cache,),
            daemon=True,
        )
        thread.start()

    def _fetch_thread(self, bypass_cache: bool) -> None:
        try:
            from app.data.cfb_api import (
                fetch_standings,
                fetch_standings_cached,
                _current_season,
            )
            from app.cards.standings_card import (
                StandingsCardConfig,
                StandingsCardRenderer,
            )

            season = self._get_season()
            scope  = self._scope_var.get()
            key    = self.settings.cfbd_api_key
            ttl    = self.settings.data_cache_ttl_minutes

            if bypass_cache:
                block = fetch_standings(season, scope, key)
            else:
                block = fetch_standings_cached(season, scope, key, ttl)

            config = self._build_card_config()
            renderer = StandingsCardRenderer()
            working_dir = self.settings.working_dir
            image = renderer.render(block, config, working_dir)

            self.after(0, lambda: self._on_fetch_done(image, None))
        except Exception as exc:
            logger.exception("Standings fetch/render failed")
            msg = str(exc)
            self.after(0, lambda m=msg: self._on_fetch_done(None, m))

    def _on_fetch_done(
        self,
        image: Optional[Image.Image],
        error: Optional[str],
    ) -> None:
        self._fetching = False
        self._fetch_btn.config(state="normal")
        self._refresh_btn.config(state="normal")

        if error:
            self._status_label.config(text=error, foreground="#aa2200")
            return

        self._card_image = image
        self._status_label.config(text="", foreground="#aa2200")
        self._full_preview_btn.config(state="normal")
        self._export_png_btn.config(state="normal")
        self._export_jpg_btn.config(state="normal")
        self._update_thumbnail()

    def _on_canvas_resize(self, event: tk.Event) -> None:
        if self._card_image is not None:
            self._update_thumbnail()

    def _update_thumbnail(self) -> None:
        if self._card_image is None:
            return
        canvas_w = self._preview_canvas.winfo_width() or THUMB_W
        canvas_h = self._preview_canvas.winfo_height() or THUMB_H

        thumb = self._card_image.copy()
        thumb.thumbnail((canvas_w, canvas_h), Image.LANCZOS)

        self._thumb_photo = ImageTk.PhotoImage(thumb)
        self._preview_canvas.delete("all")
        self._preview_canvas.create_image(
            canvas_w // 2, canvas_h // 2,
            anchor="center",
            image=self._thumb_photo,
        )

    def _on_full_preview(self) -> None:
        if self._card_image is None:
            return
        top = tk.Toplevel(self)
        w, h = self._card_image.size
        top.title(f"Full Preview — {w} × {h} px")

        # Limit to 90% of screen
        sw = int(self.winfo_screenwidth() * 0.9)
        sh = int(self.winfo_screenheight() * 0.9)
        disp = self._card_image.copy()
        if disp.width > sw or disp.height > sh:
            disp.thumbnail((sw, sh), Image.LANCZOS)

        photo = ImageTk.PhotoImage(disp)

        frame = ttk.Frame(top)
        frame.pack(fill="both", expand=True)

        hbar = ttk.Scrollbar(frame, orient="horizontal")
        vbar = ttk.Scrollbar(frame, orient="vertical")
        canvas = tk.Canvas(
            frame,
            scrollregion=(0, 0, disp.width, disp.height),
            xscrollcommand=hbar.set,
            yscrollcommand=vbar.set,
        )
        hbar.config(command=canvas.xview)
        vbar.config(command=canvas.yview)

        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        canvas.create_image(0, 0, anchor="nw", image=photo)
        # Keep reference
        canvas._photo = photo  # type: ignore[attr-defined]

    # ---- Export -------------------------------------------------------

    def _build_export(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Export")
        lf.pack(fill="x", padx=8, pady=4)

        ttk.Label(lf, text="Filename (no extension):").pack(
            anchor="w", padx=6, pady=(4, 0)
        )
        self._export_name_var = tk.StringVar(value="standings_card")
        ttk.Entry(lf, textvariable=self._export_name_var, width=24).pack(
            anchor="w", padx=6, pady=2
        )

        self._append_ts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            lf, text="Append timestamp to filename",
            variable=self._append_ts_var,
        ).pack(anchor="w", padx=6, pady=2)

        btn_row = ttk.Frame(lf)
        btn_row.pack(fill="x", padx=6, pady=(2, 6))

        self._export_png_btn = ttk.Button(
            btn_row, text="Export PNG",
            command=lambda: self._export("PNG"),
            state="disabled",
        )
        self._export_png_btn.pack(side="left", padx=(0, 6))

        self._export_jpg_btn = ttk.Button(
            btn_row, text="Export JPG",
            command=lambda: self._export("JPEG"),
            state="disabled",
        )
        self._export_jpg_btn.pack(side="left")

    def _export(self, fmt: str) -> None:
        if self._card_image is None:
            return
        from app.utils.image_utils import apply_export_margin

        name = self._export_name_var.get().strip() or "standings_card"
        if self._append_ts_var.get():
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"{name}_{ts}"

        ext = ".jpg" if fmt == "JPEG" else ".png"
        out_dir = os.path.join(self.settings.working_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, name + ext)

        img = apply_export_margin(
            self._card_image,
            self._bg_color_var.get(),
            self.settings.export_canvas_margin_pct,
        )

        config = self._build_card_config()
        final = config.export(img, path, fmt=fmt)
        self._status_label.config(
            text=f"Saved: {os.path.basename(final)}", foreground="#006600"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_season(self) -> int:
        try:
            return int(self._season_var.get())
        except ValueError:
            return 0

    def _build_card_config(self):
        from app.cards.standings_card import StandingsCardConfig
        try:
            w = float(self._width_var.get())
        except ValueError:
            w = 6.0
        try:
            h = float(self._height_var.get())
        except ValueError:
            h = 4.0
        return StandingsCardConfig(
            width_in=w,
            height_in=h,
            dpi=self.settings.dpi,
            bg_color=self._bg_color_var.get(),
            show_logos=self._show_logos_var.get(),
            show_timestamp=self._show_timestamp_var.get(),
            show_col_explainers=self._show_col_explainers_var.get(),
            column_mode=self._col_mode_var.get(),
            season=self._get_season(),
            conference=self._scope_var.get(),
        )

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_from_settings(self) -> None:
        s = self.settings
        self._width_var.set(str(s.standings_width_in))
        self._height_var.set(str(s.standings_height_in))
        self._use_global_var.set(s.standings_use_global_size)
        self._season_var.set(str(s.standings_season))
        self._scope_var.set(s.standings_scope)
        self._col_mode_var.set(s.standings_column_mode)
        self._show_logos_var.set(s.standings_show_logos)
        self._show_timestamp_var.set(s.standings_show_timestamp)
        self._show_col_explainers_var.set(s.standings_show_col_explainers)
        self._bg_color_var.set(s.standings_bg_color)
        self._export_name_var.set(s.standings_export_filename)
        self._append_ts_var.set(s.standings_append_timestamp)
        self._on_use_global_size_changed()
        self._on_size_changed()
        self._update_col_suggestion()

    def apply(self) -> None:
        """Serialize UI state back into settings."""
        s = self.settings
        try:
            s.standings_width_in = float(self._width_var.get())
        except ValueError:
            pass
        try:
            s.standings_height_in = float(self._height_var.get())
        except ValueError:
            pass
        s.standings_use_global_size = self._use_global_var.get()
        try:
            s.standings_season = int(self._season_var.get())
        except ValueError:
            pass
        s.standings_scope = self._scope_var.get()
        s.standings_column_mode = self._col_mode_var.get()
        s.standings_show_logos = self._show_logos_var.get()
        s.standings_show_timestamp = self._show_timestamp_var.get()
        s.standings_show_col_explainers = self._show_col_explainers_var.get()
        s.standings_bg_color = self._bg_color_var.get()
        s.standings_export_filename = self._export_name_var.get().strip()
        s.standings_append_timestamp = self._append_ts_var.get()
