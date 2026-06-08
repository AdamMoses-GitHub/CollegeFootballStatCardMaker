"""Player Career tab."""
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

THUMB_W, THUMB_H = 480, 320

logger = logging.getLogger(__name__)


class CareerTab(ttk.Frame):
    def __init__(self, parent, settings: Settings) -> None:
        super().__init__(parent)
        self.settings = settings
        self._card_image: Optional[Image.Image] = None
        self._thumb_photo = None
        self._fetching = False
        self._search_results: list = []
        self._selected_player: str = ""
        self._build_ui()
        self._load_from_settings()

    def _build_ui(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True, padx=8, pady=8)
        controls = ttk.Frame(pw, width=290)
        controls.pack_propagate(False)
        pw.add(controls, weight=0)
        pf = ttk.LabelFrame(pw, text="Preview")
        pw.add(pf, weight=1)
        self._canvas = tk.Canvas(pf, bg="#CCCCCC", width=THUMB_W, height=THUMB_H)
        self._canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._canvas.bind("<Configure>", lambda e: self._update_thumb())
        self._build_controls(controls)

    def _build_controls(self, p):
        self._build_card_size(p)
        self._build_player_search(p)
        self._build_stat_type(p)
        self._build_year_range(p)
        self._build_display_opts(p)
        self._build_bg_color(p)
        self._build_fetch_bar(p)
        self._build_export(p)

    def _build_card_size(self, p):
        lf = ttk.LabelFrame(p, text="Card Size")
        lf.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=(4,0))
        ttk.Label(r, text="W (in):").pack(side="left")
        self._w_var = tk.StringVar()
        self._w_spin = ttk.Spinbox(r, from_=2, to=24, increment=0.5, textvariable=self._w_var, width=6)
        self._w_spin.pack(side="left", padx=(2,8))
        ttk.Label(r, text="H (in):").pack(side="left")
        self._h_var = tk.StringVar()
        self._h_spin = ttk.Spinbox(r, from_=2, to=24, increment=0.5, textvariable=self._h_var, width=6)
        self._h_spin.pack(side="left", padx=(2,0))
        r2 = ttk.Frame(lf); r2.pack(fill="x", padx=6, pady=2)
        self._global_var = tk.BooleanVar()
        ttk.Checkbutton(r2, text="Use global card size", variable=self._global_var,
                        command=self._on_global).pack(side="left")
        self._orient_lbl = ttk.Label(lf, text="", foreground="#555555")
        self._orient_lbl.pack(anchor="w", padx=6, pady=(0,4))
        for v in (self._w_var, self._h_var):
            v.trace_add("write", self._on_size)

    def _on_size(self, *_):
        try:
            w, h = float(self._w_var.get()), float(self._h_var.get())
            self._orient_lbl.config(text="(Landscape)" if w >= h else "(Portrait)")
        except ValueError:
            pass

    def _on_global(self):
        if self._global_var.get():
            self._w_var.set(str(self.settings.card_width_in))
            self._h_var.set(str(self.settings.card_height_in))
            self._w_spin.config(state="disabled"); self._h_spin.config(state="disabled")
        else:
            self._w_spin.config(state="normal"); self._h_spin.config(state="normal")

    def _build_player_search(self, p):
        lf = ttk.LabelFrame(p, text="Player")
        lf.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=(6,2))
        self._search_var = tk.StringVar()
        ttk.Entry(r, textvariable=self._search_var, width=20).pack(side="left", padx=(0,4))
        ttk.Button(r, text="Search", command=self._on_search).pack(side="left")

        self._results_var = tk.StringVar()
        self._results_lb = tk.Listbox(lf, height=4, listvariable=self._results_var,
                                      selectmode="single", activestyle="none")
        self._results_lb.pack(fill="x", padx=6, pady=(2,2))
        self._results_lb.bind("<<ListboxSelect>>", self._on_select)

        self._selected_lbl = ttk.Label(lf, text="No player selected",
                                       foreground="#555555", wraplength=240)
        self._selected_lbl.pack(anchor="w", padx=6, pady=(0,6))

    def _on_search(self):
        query = self._search_var.get().strip()
        if not query: return
        def _bg():
            try:
                from app.data.career_api import search_players
                results = search_players(query, self.settings.cfbd_api_key)
                self.after(0, lambda r=results: self._show_results(r))
            except Exception as exc:
                logger.exception("Player search failed")
                msg = str(exc)
                self.after(0, lambda m=msg: self._show_search_error(m))
        threading.Thread(target=_bg, daemon=True).start()

    def _show_results(self, results):
        self._search_results = results
        labels = [f"{r.name} ({r.team}, {r.position})" for r in results]
        self._results_lb.delete(0, "end")
        for lbl in labels:
            self._results_lb.insert("end", lbl)
        if not results:
            self._selected_lbl.config(text="No results found.")

    def _show_search_error(self, msg):
        self._selected_lbl.config(text=f"Search error: {msg}", foreground="#aa2200")

    def _on_select(self, event=None):
        sel = self._results_lb.curselection()
        if not sel: return
        idx = sel[0]
        if idx < len(self._search_results):
            r = self._search_results[idx]
            self._selected_player = r.name
            self._selected_lbl.config(
                text=f"Selected: {r.name} | {r.team} | {r.position}",
                foreground="#006600",
            )

    def _build_stat_type(self, p):
        lf = ttk.LabelFrame(p, text="Stat Type")
        lf.pack(fill="x", padx=8, pady=4)
        self._stat_type_var = tk.StringVar(value="Passing")
        for val in ("Passing", "Rushing", "Receiving", "Defense"):
            ttk.Radiobutton(lf, text=val, variable=self._stat_type_var,
                            value=val).pack(anchor="w", padx=8, pady=1)

    def _build_year_range(self, p):
        lf = ttk.LabelFrame(p, text="Season Range")
        lf.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=(6,2))
        ttk.Label(r, text="From:").pack(side="left")
        self._yr_start_var = tk.StringVar(value="0")
        ttk.Spinbox(r, from_=0, to=datetime.datetime.now().year,
                    textvariable=self._yr_start_var, width=6).pack(side="left", padx=(4,8))
        ttk.Label(r, text="To:").pack(side="left")
        self._yr_end_var = tk.StringVar(value="0")
        ttk.Spinbox(r, from_=0, to=datetime.datetime.now().year,
                    textvariable=self._yr_end_var, width=6).pack(side="left", padx=(4,0))
        ttk.Label(lf, text="(0 = career start/end)", foreground="#555555").pack(anchor="w", padx=6, pady=(0,2))
        r2 = ttk.Frame(lf); r2.pack(fill="x", padx=6, pady=(0,6))
        ttk.Label(r2, text="Sort:").pack(side="left")
        self._sort_var = tk.StringVar(value="Ascending")
        ttk.Radiobutton(r2, text="Asc", variable=self._sort_var, value="Ascending").pack(side="left", padx=(4,0))
        ttk.Radiobutton(r2, text="Desc", variable=self._sort_var, value="Descending").pack(side="left", padx=(4,0))

    def _build_display_opts(self, p):
        lf = ttk.LabelFrame(p, text="Display Options")
        lf.pack(fill="x", padx=8, pady=4)
        self._hl_recent_var = tk.BooleanVar(value=True)
        self._show_ts_var   = tk.BooleanVar(value=False)
        self._show_expl_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(lf, text="Highlight most recent season",
                        variable=self._hl_recent_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show timestamp",
                        variable=self._show_ts_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show column explainers",
                        variable=self._show_expl_var).pack(anchor="w", padx=8, pady=(1,4))

    def _build_bg_color(self, p):
        lf = ttk.LabelFrame(p, text="Background Color")
        lf.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=6)
        self._bg_var = tk.StringVar(value="#FFFFFF")
        self._bg_var.trace_add("write", self._update_swatch)
        ttk.Entry(r, textvariable=self._bg_var, width=9).pack(side="left", padx=(0,4))
        self._swatch = tk.Label(r, width=3, relief="sunken", background="#FFFFFF")
        self._swatch.pack(side="left", padx=(0,4))
        ttk.Button(r, text="Pick…", command=self._pick_color).pack(side="left")

    def _update_swatch(self, *_):
        c = self._bg_var.get()
        if c.startswith("#") and len(c) in (4,7):
            try: self._swatch.config(background=c)
            except tk.TclError: pass

    def _pick_color(self):
        r = colorchooser.askcolor(color=self._bg_var.get())
        if r and r[1]: self._bg_var.set(r[1])

    def _build_fetch_bar(self, p):
        ttk.Separator(p, orient="horizontal").pack(fill="x", padx=8, pady=6)
        r = ttk.Frame(p); r.pack(fill="x", padx=8)
        self._fetch_btn = ttk.Button(r, text="Fetch & Preview", command=self._on_fetch)
        self._fetch_btn.pack(side="left", padx=(0,6))
        self._refresh_btn = ttk.Button(r, text="↺ Refresh", width=9, command=self._on_refresh)
        self._refresh_btn.pack(side="left")
        r2 = ttk.Frame(p); r2.pack(fill="x", padx=8, pady=(4,0))
        self._full_btn = ttk.Button(r2, text="Full Preview…", command=self._on_full, state="disabled")
        self._full_btn.pack(side="left")
        self._status = ttk.Label(p, text="", foreground="#aa2200", wraplength=260, justify="left")
        self._status.pack(fill="x", padx=8, pady=4)

    def _build_export(self, p):
        lf = ttk.LabelFrame(p, text="Export")
        lf.pack(fill="x", padx=8, pady=4)
        ttk.Label(lf, text="Filename (no extension):").pack(anchor="w", padx=6, pady=(4,0))
        self._fname_var = tk.StringVar(value="career_card")
        ttk.Entry(lf, textvariable=self._fname_var, width=24).pack(anchor="w", padx=6, pady=2)
        self._append_ts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(lf, text="Append timestamp", variable=self._append_ts_var).pack(anchor="w", padx=6)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=(2,6))
        self._png_btn = ttk.Button(r, text="Export PNG", command=lambda: self._export("PNG"), state="disabled")
        self._png_btn.pack(side="left", padx=(0,6))
        self._jpg_btn = ttk.Button(r, text="Export JPG", command=lambda: self._export("JPEG"), state="disabled")
        self._jpg_btn.pack(side="left")

    # ------------------------------------------------------------------

    def _on_fetch(self): self._start_fetch(False)
    def _on_refresh(self): self._start_fetch(True)

    def _start_fetch(self, bypass):
        if self._fetching: return
        player = self._selected_player or self._search_var.get().strip()
        if not player:
            self._status.config(text="Search for and select a player first.", foreground="#aa2200")
            return
        self._fetching = True
        self._fetch_btn.config(state="disabled"); self._refresh_btn.config(state="disabled")
        self._status.config(text="Fetching…", foreground="#555555")
        threading.Thread(target=self._fetch_thread, args=(bypass, player), daemon=True).start()

    def _fetch_thread(self, bypass, player):
        try:
            from app.data.career_api import fetch_career, fetch_career_cached
            from app.cards.career_card import CareerCardConfig, CareerCardRenderer
            stat_type  = self._stat_type_var.get()
            yr_start   = self._int(self._yr_start_var, 0)
            yr_end     = self._int(self._yr_end_var, 0)
            sort       = self._sort_var.get()
            key        = self.settings.cfbd_api_key
            ttl        = self.settings.data_cache_ttl_minutes
            block = fetch_career(player, stat_type, key, yr_start, yr_end, sort) if bypass \
                    else fetch_career_cached(player, stat_type, key, yr_start, yr_end, sort, ttl)
            cfg = self._build_config()
            img = CareerCardRenderer().render(block, cfg, self.settings.working_dir)
            self.after(0, lambda: self._done(img, None))
        except Exception as exc:
            logger.exception("Career fetch/render failed")
            msg = str(exc)
            self.after(0, lambda m=msg: self._done(None, m))

    def _done(self, img, err):
        self._fetching = False
        self._fetch_btn.config(state="normal"); self._refresh_btn.config(state="normal")
        if err:
            self._status.config(text=err, foreground="#aa2200"); return
        self._card_image = img
        self._status.config(text="", foreground="#aa2200")
        self._full_btn.config(state="normal")
        self._png_btn.config(state="normal"); self._jpg_btn.config(state="normal")
        self._update_thumb()

    def _update_thumb(self):
        if not self._card_image: return
        cw = self._canvas.winfo_width()  or THUMB_W
        ch = self._canvas.winfo_height() or THUMB_H
        t = self._card_image.copy(); t.thumbnail((cw, ch), Image.LANCZOS)
        self._thumb_photo = ImageTk.PhotoImage(t)
        self._canvas.delete("all")
        self._canvas.create_image(cw//2, ch//2, anchor="center", image=self._thumb_photo)

    def _on_full(self):
        if not self._card_image: return
        from app.ui.standings_tab import _full_preview_window
        _full_preview_window(self, self._card_image)

    def _export(self, fmt):
        if not self._card_image: return
        from app.utils.image_utils import apply_export_margin
        name = self._fname_var.get().strip() or "career_card"
        if self._append_ts_var.get():
            name = f"{name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        ext = ".jpg" if fmt == "JPEG" else ".png"
        out = os.path.join(self.settings.working_dir, "output")
        os.makedirs(out, exist_ok=True)
        img = apply_export_margin(self._card_image, self._bg_var.get(),
                                  self.settings.export_canvas_margin_pct)
        final = self._build_config().export(img, os.path.join(out, name + ext), fmt=fmt)
        self._status.config(text=f"Saved: {os.path.basename(final)}", foreground="#006600")

    def _int(self, var, default):
        try: return int(var.get())
        except ValueError: return default

    def _float(self, var, default):
        try: return float(var.get())
        except ValueError: return default

    def _build_config(self):
        from app.cards.career_card import CareerCardConfig
        return CareerCardConfig(
            width_in=self._float(self._w_var, 7.0),
            height_in=self._float(self._h_var, 6.0),
            dpi=self.settings.dpi,
            bg_color=self._bg_var.get(),
            show_timestamp=self._show_ts_var.get(),
            show_col_explainers=self._show_expl_var.get(),
            highlight_recent=self._hl_recent_var.get(),
            stat_type=self._stat_type_var.get(),
        )

    def _load_from_settings(self):
        s = self.settings
        self._w_var.set(str(s.career_width_in))
        self._h_var.set(str(s.career_height_in))
        self._global_var.set(s.career_use_global_size)
        self._stat_type_var.set(s.career_stat_type)
        self._yr_start_var.set(str(s.career_year_start))
        self._yr_end_var.set(str(s.career_year_end))
        self._sort_var.set(s.career_year_sort)
        if s.career_player_name:
            self._selected_player = s.career_player_name
            self._selected_lbl.config(text=f"Selected: {s.career_player_name}", foreground="#555555")
        self._hl_recent_var.set(s.career_highlight_current)
        self._show_ts_var.set(s.career_show_timestamp)
        self._show_expl_var.set(s.career_show_col_explainers)
        self._bg_var.set(s.career_bg_color)
        self._fname_var.set(s.career_export_filename)
        self._append_ts_var.set(s.career_append_timestamp)
        self._on_global(); self._on_size()

    def apply(self):
        s = self.settings
        s.career_width_in  = self._float(self._w_var, 7.0)
        s.career_height_in = self._float(self._h_var, 6.0)
        s.career_use_global_size    = self._global_var.get()
        s.career_stat_type          = self._stat_type_var.get()
        s.career_player_name        = self._selected_player
        s.career_year_start         = self._int(self._yr_start_var, 0)
        s.career_year_end           = self._int(self._yr_end_var, 0)
        s.career_year_sort          = self._sort_var.get()
        s.career_highlight_current  = self._hl_recent_var.get()
        s.career_show_timestamp     = self._show_ts_var.get()
        s.career_show_col_explainers= self._show_expl_var.get()
        s.career_bg_color           = self._bg_var.get()
        s.career_export_filename    = self._fname_var.get().strip()
        s.career_append_timestamp   = self._append_ts_var.get()
