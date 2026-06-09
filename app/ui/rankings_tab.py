"""Rankings tab for CFB Stat Card Maker."""
from __future__ import annotations

import datetime
import logging
import os
import threading
import tkinter as tk
from tkinter import colorchooser, ttk
from typing import Optional

from PIL import Image, ImageTk

from app.settings import Settings
from app.data.rankings_api import POLL_OPTIONS

THUMB_W = 480
THUMB_H = 320

logger = logging.getLogger(__name__)


class RankingsTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, settings: Settings) -> None:
        super().__init__(parent)
        self.settings = settings
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

        from app.ui import make_scrollable_left_panel
        controls = make_scrollable_left_panel(pw)

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
        self._build_poll_options(parent)
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
        for ev in ("<<Increment>>", "<<Decrement>>", "<FocusOut>"):
            self._width_spin.bind(ev, self._on_size_changed)
            self._height_spin.bind(ev, self._on_size_changed)

    def _on_size_changed(self, *_) -> None:
        try:
            w = float(self._width_var.get())
            h = float(self._height_var.get())
            self._orient_label.config(
                text="(Landscape)" if w >= h else "(Portrait)"
            )
        except ValueError:
            pass

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
        lf = ttk.LabelFrame(parent, text="Season & Week")
        lf.pack(fill="x", padx=8, pady=4)

        row1 = ttk.Frame(lf)
        row1.pack(fill="x", padx=6, pady=(6, 2))
        ttk.Label(row1, text="Season:").pack(side="left")
        self._season_var = tk.StringVar()
        ttk.Spinbox(
            row1, from_=1970, to=datetime.datetime.now().year,
            textvariable=self._season_var, width=7,
        ).pack(side="left", padx=(4, 12))
        ttk.Label(row1, text="(0=current)", foreground="#555555").pack(side="left")

        row2 = ttk.Frame(lf)
        row2.pack(fill="x", padx=6, pady=(2, 6))
        ttk.Label(row2, text="Week:").pack(side="left")
        self._week_var = tk.StringVar()
        ttk.Spinbox(
            row2, from_=0, to=20,
            textvariable=self._week_var, width=5,
        ).pack(side="left", padx=(4, 8))
        ttk.Label(row2, text="(0=latest)", foreground="#555555").pack(side="left")

    # ---- Poll & Season Type ------------------------------------------

    def _build_poll_options(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Poll")
        lf.pack(fill="x", padx=8, pady=4)

        self._poll_var = tk.StringVar()
        ttk.Combobox(
            lf, textvariable=self._poll_var,
            values=POLL_OPTIONS, state="readonly", width=22,
        ).pack(padx=6, pady=(6, 2), anchor="w")

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=6, pady=(2, 6))
        ttk.Label(row, text="Season type:").pack(side="left")
        self._season_type_var = tk.StringVar(value="regular")
        ttk.Radiobutton(row, text="Regular", variable=self._season_type_var,
                        value="regular").pack(side="left", padx=(6, 0))
        ttk.Radiobutton(row, text="Postseason", variable=self._season_type_var,
                        value="postseason").pack(side="left", padx=(6, 0))

    # ---- Display Options ----------------------------------------------

    def _build_display_options(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Display Options")
        lf.pack(fill="x", padx=8, pady=4)

        self._show_logos_var       = tk.BooleanVar()
        self._show_rank_badges_var = tk.BooleanVar()
        self._show_timestamp_var   = tk.BooleanVar()
        self._show_explainers_var  = tk.BooleanVar()

        ttk.Checkbutton(lf, text="Show team logos",
                        variable=self._show_logos_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show rank badges (gold/silver/bronze)",
                        variable=self._show_rank_badges_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show 'data as of' timestamp",
                        variable=self._show_timestamp_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show column explainers",
                        variable=self._show_explainers_var).pack(anchor="w", padx=8, pady=(1, 4))

    # ---- Background Color ---------------------------------------------

    def _build_bg_color(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Background Color")
        lf.pack(fill="x", padx=8, pady=4)
        row = ttk.Frame(lf)
        row.pack(fill="x", padx=6, pady=6)
        self._bg_color_var = tk.StringVar(value="#FFFFFF")
        self._bg_color_var.trace_add("write", self._update_bg_swatch)
        ttk.Entry(row, textvariable=self._bg_color_var, width=9).pack(side="left", padx=(0, 4))
        self._bg_swatch = tk.Label(row, width=3, relief="sunken", background="#FFFFFF")
        self._bg_swatch.pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Pick…", command=self._pick_bg_color).pack(side="left")

    def _update_bg_swatch(self, *_) -> None:
        c = self._bg_color_var.get()
        if c.startswith("#") and len(c) in (4, 7):
            try:
                self._bg_swatch.config(background=c)
            except tk.TclError:
                pass

    def _pick_bg_color(self) -> None:
        result = colorchooser.askcolor(color=self._bg_color_var.get(),
                                       title="Choose Background Color")
        if result and result[1]:
            self._bg_color_var.set(result[1])

    # ---- Fetch & Preview ----------------------------------------------

    def _build_fetch_bar(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=8, pady=6)

        row1 = ttk.Frame(parent)
        row1.pack(fill="x", padx=8)
        self._fetch_btn = ttk.Button(row1, text="Fetch & Preview",
                                     command=self._on_fetch)
        self._fetch_btn.pack(side="left", padx=(0, 6))
        self._refresh_btn = ttk.Button(row1, text="↺ Refresh", width=9,
                                       command=self._on_refresh)
        self._refresh_btn.pack(side="left")

        row2 = ttk.Frame(parent)
        row2.pack(fill="x", padx=8, pady=(4, 0))
        self._full_preview_btn = ttk.Button(row2, text="Full Preview…",
                                            command=self._on_full_preview,
                                            state="disabled")
        self._full_preview_btn.pack(side="left")

        self._status_label = ttk.Label(parent, text="", foreground="#aa2200",
                                       wraplength=260, justify="left")
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
        threading.Thread(target=self._fetch_thread, args=(bypass_cache,),
                         daemon=True).start()

    def _fetch_thread(self, bypass_cache: bool) -> None:
        try:
            from app.data.rankings_api import fetch_rankings, fetch_rankings_cached
            from app.cards.rankings_card import RankingsCardConfig, RankingsCardRenderer

            season      = self._get_int(self._season_var, 0)
            week        = self._get_int(self._week_var, 0)
            poll        = self._poll_var.get()
            season_type = self._season_type_var.get()
            key         = self.settings.cfbd_api_key
            ttl         = self.settings.data_cache_ttl_minutes

            if bypass_cache:
                block = fetch_rankings(season, week, poll, season_type, key)
            else:
                block = fetch_rankings_cached(season, week, poll, season_type, key, ttl)

            config   = self._build_card_config()
            renderer = RankingsCardRenderer()
            image    = renderer.render(block, config, self.settings.working_dir)
            self.after(0, lambda: self._on_fetch_done(image, None))
        except Exception as exc:
            logger.exception("Rankings fetch/render failed")
            msg = str(exc)
            self.after(0, lambda m=msg: self._on_fetch_done(None, m))

    def _on_fetch_done(self, image: Optional[Image.Image], error: Optional[str]) -> None:
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
        cw = self._preview_canvas.winfo_width()  or THUMB_W
        ch = self._preview_canvas.winfo_height() or THUMB_H
        thumb = self._card_image.copy()
        thumb.thumbnail((cw, ch), Image.LANCZOS)
        self._thumb_photo = ImageTk.PhotoImage(thumb)
        self._preview_canvas.delete("all")
        self._preview_canvas.create_image(cw // 2, ch // 2, anchor="center",
                                          image=self._thumb_photo)

    def _on_full_preview(self) -> None:
        if self._card_image is None:
            return
        top = tk.Toplevel(self)
        w, h = self._card_image.size
        top.title(f"Full Preview — {w} × {h} px")
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
        canvas = tk.Canvas(frame, scrollregion=(0, 0, disp.width, disp.height),
                           xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.config(command=canvas.xview)
        vbar.config(command=canvas.yview)
        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas._photo = photo  # type: ignore[attr-defined]

    # ---- Export -------------------------------------------------------

    def _build_export(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Export")
        lf.pack(fill="x", padx=8, pady=4)
        ttk.Label(lf, text="Filename (no extension):").pack(anchor="w", padx=6, pady=(4, 0))
        self._export_name_var = tk.StringVar(value="rankings_card")
        ttk.Entry(lf, textvariable=self._export_name_var, width=24).pack(anchor="w", padx=6, pady=2)
        self._append_ts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(lf, text="Append timestamp to filename",
                        variable=self._append_ts_var).pack(anchor="w", padx=6, pady=2)
        row = ttk.Frame(lf)
        row.pack(fill="x", padx=6, pady=(2, 6))
        self._export_png_btn = ttk.Button(row, text="Export PNG",
                                          command=lambda: self._export("PNG"),
                                          state="disabled")
        self._export_png_btn.pack(side="left", padx=(0, 6))
        self._export_jpg_btn = ttk.Button(row, text="Export JPG",
                                          command=lambda: self._export("JPEG"),
                                          state="disabled")
        self._export_jpg_btn.pack(side="left")

    def _export(self, fmt: str) -> None:
        if self._card_image is None:
            return
        from app.utils.image_utils import apply_export_margin
        name = self._export_name_var.get().strip() or "rankings_card"
        if self._append_ts_var.get():
            name = f"{name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ext = ".jpg" if fmt == "JPEG" else ".png"
        out_dir = os.path.join(self.settings.working_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        img = apply_export_margin(self._card_image, self._bg_color_var.get(),
                                  self.settings.export_canvas_margin_pct)
        config = self._build_card_config()
        final = config.export(img, os.path.join(out_dir, name + ext), fmt=fmt)
        self._status_label.config(text=f"Saved: {os.path.basename(final)}",
                                  foreground="#006600")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_int(self, var: tk.StringVar, default: int) -> int:
        try:
            return int(var.get())
        except ValueError:
            return default

    def _build_card_config(self):
        from app.cards.rankings_card import RankingsCardConfig
        try:
            w = float(self._width_var.get())
        except ValueError:
            w = 6.0
        try:
            h = float(self._height_var.get())
        except ValueError:
            h = 7.0
        return RankingsCardConfig(
            width_in=w, height_in=h,
            dpi=self.settings.dpi,
            bg_color=self._bg_color_var.get(),
            show_logos=self._show_logos_var.get(),
            show_rank_badges=self._show_rank_badges_var.get(),
            show_timestamp=self._show_timestamp_var.get(),
            show_col_explainers=self._show_explainers_var.get(),
            season=self._get_int(self._season_var, 0),
            week=self._get_int(self._week_var, 0),
            poll=self._poll_var.get(),
            season_type=self._season_type_var.get(),
        )

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_from_settings(self) -> None:
        s = self.settings
        self._width_var.set(str(s.rankings_width_in))
        self._height_var.set(str(s.rankings_height_in))
        self._use_global_var.set(s.rankings_use_global_size)
        self._season_var.set(str(s.rankings_season))
        self._week_var.set(str(s.rankings_week))
        self._poll_var.set(s.rankings_poll)
        self._season_type_var.set(s.rankings_season_type)
        self._show_logos_var.set(s.rankings_show_logos)
        self._show_rank_badges_var.set(s.rankings_show_rank_badges)
        self._show_timestamp_var.set(s.rankings_show_timestamp)
        self._show_explainers_var.set(s.rankings_show_col_explainers)
        self._bg_color_var.set(s.rankings_bg_color)
        self._export_name_var.set(s.rankings_export_filename)
        self._append_ts_var.set(s.rankings_append_timestamp)
        self._on_use_global_size_changed()
        self._on_size_changed()

    def apply(self) -> None:
        s = self.settings
        try:
            s.rankings_width_in = float(self._width_var.get())
        except ValueError:
            pass
        try:
            s.rankings_height_in = float(self._height_var.get())
        except ValueError:
            pass
        s.rankings_use_global_size   = self._use_global_var.get()
        s.rankings_season            = self._get_int(self._season_var, 0)
        s.rankings_week              = self._get_int(self._week_var, 0)
        s.rankings_poll              = self._poll_var.get()
        s.rankings_season_type       = self._season_type_var.get()
        s.rankings_show_logos        = self._show_logos_var.get()
        s.rankings_show_rank_badges  = self._show_rank_badges_var.get()
        s.rankings_show_timestamp    = self._show_timestamp_var.get()
        s.rankings_show_col_explainers = self._show_explainers_var.get()
        s.rankings_bg_color          = self._bg_color_var.get()
        s.rankings_export_filename   = self._export_name_var.get().strip()
        s.rankings_append_timestamp  = self._append_ts_var.get()
