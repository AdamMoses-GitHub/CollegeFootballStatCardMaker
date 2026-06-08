"""Team Schedule tab — full-season schedule for an upcoming or ongoing season."""
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


class ScheduleTab(ttk.Frame):
    def __init__(self, parent, settings: Settings) -> None:
        super().__init__(parent)
        self.settings = settings
        self._card_image: Optional[Image.Image] = None
        self._thumb_photo = None
        self._fetching = False
        self._build_ui()
        self._load_from_settings()
        self.after(100, self._load_teams)

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
        self._build_team_season(p)
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

    def _build_team_season(self, p):
        lf = ttk.LabelFrame(p, text="Team & Season")
        lf.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=(6,2))
        ttk.Label(r, text="Team:").pack(side="left")
        self._team_var = tk.StringVar()
        self._team_cb = ttk.Combobox(r, textvariable=self._team_var, state="readonly", width=22)
        self._team_cb.pack(side="left", padx=(4,0))
        r2 = ttk.Frame(lf); r2.pack(fill="x", padx=6, pady=(2,6))
        ttk.Label(r2, text="Season:").pack(side="left")
        self._season_var = tk.StringVar()
        cur_year = datetime.datetime.now().year
        ttk.Spinbox(r2, from_=1970, to=cur_year + 2,
                    textvariable=self._season_var, width=7).pack(side="left", padx=(4,8))
        ttk.Label(r2, text=f"(0 = {cur_year})", foreground="#555555").pack(side="left")

    def _build_display_opts(self, p):
        lf = ttk.LabelFrame(p, text="Display Options")
        lf.pack(fill="x", padx=8, pady=4)
        self._show_logo_var       = tk.BooleanVar(value=True)
        self._show_scores_var     = tk.BooleanVar(value=True)
        self._show_summary_var    = tk.BooleanVar(value=True)
        self._use_team_colors_var = tk.BooleanVar(value=False)
        self._show_ts_var         = tk.BooleanVar(value=False)
        ttk.Checkbutton(lf, text="Show team logo",
                        variable=self._show_logo_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show scores (uncheck for spoiler-free)",
                        variable=self._show_scores_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show W-L summary",
                        variable=self._show_summary_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Use team colors",
                        variable=self._use_team_colors_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show timestamp",
                        variable=self._show_ts_var).pack(anchor="w", padx=8, pady=(1,4))

    def _build_bg_color(self, p):
        lf = ttk.LabelFrame(p, text="Background Color")
        lf.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=6)
        self._bg_var = tk.StringVar(value="#FFFFFF")
        self._bg_var.trace_add("write", self._update_swatch)
        ttk.Entry(r, textvariable=self._bg_var, width=9).pack(side="left", padx=(0,4))
        self._swatch = tk.Label(r, width=3, relief="sunken", background="#FFFFFF")
        self._swatch.pack(side="left", padx=(0,4))
        ttk.Button(r, text="Pick...", command=self._pick_color).pack(side="left")

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
        self._refresh_btn = ttk.Button(r, text="Refresh", width=9, command=self._on_refresh)
        self._refresh_btn.pack(side="left")
        r2 = ttk.Frame(p); r2.pack(fill="x", padx=8, pady=(4,0))
        self._full_btn = ttk.Button(r2, text="Full Preview...", command=self._on_full, state="disabled")
        self._full_btn.pack(side="left")
        self._status = ttk.Label(p, text="", foreground="#aa2200", wraplength=260, justify="left")
        self._status.pack(fill="x", padx=8, pady=4)

    def _build_export(self, p):
        lf = ttk.LabelFrame(p, text="Export")
        lf.pack(fill="x", padx=8, pady=4)
        ttk.Label(lf, text="Filename (no extension):").pack(anchor="w", padx=6, pady=(4,0))
        self._fname_var = tk.StringVar(value="schedule_card")
        ttk.Entry(lf, textvariable=self._fname_var, width=24).pack(anchor="w", padx=6, pady=2)
        self._append_ts_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(lf, text="Append timestamp", variable=self._append_ts_var).pack(anchor="w", padx=6)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=(2,6))
        self._png_btn = ttk.Button(r, text="Export PNG", command=lambda: self._export("PNG"), state="disabled")
        self._png_btn.pack(side="left", padx=(0,6))
        self._jpg_btn = ttk.Button(r, text="Export JPG", command=lambda: self._export("JPEG"), state="disabled")
        self._jpg_btn.pack(side="left")

    # ------------------------------------------------------------------

    def _load_teams(self):
        def _bg():
            try:
                from app.data.teams_api import team_names
                names = team_names(self.settings.cfbd_api_key)
                self.after(0, lambda n=names: self._set_teams(n))
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

    def _set_teams(self, names):
        self._team_cb.config(values=names)
        cur = self._team_var.get()
        if cur not in names and names:
            self._team_var.set(names[0])

    def _on_fetch(self): self._start_fetch(False)
    def _on_refresh(self): self._start_fetch(True)

    def _start_fetch(self, bypass):
        if self._fetching: return
        self._fetching = True
        self._fetch_btn.config(state="disabled"); self._refresh_btn.config(state="disabled")
        self._status.config(text="Fetching...", foreground="#555555")
        threading.Thread(target=self._fetch_thread, args=(bypass,), daemon=True).start()

    def _fetch_thread(self, bypass):
        try:
            from app.data.game_record_api import fetch_game_record, fetch_game_record_cached
            from app.cards.game_record_card import GameRecordCardRenderer
            team   = self._team_var.get()
            if not team: raise ValueError("Please select a team.")
            season = self._int(self._season_var, 0)
            key    = self.settings.cfbd_api_key
            ttl    = self.settings.data_cache_ttl_minutes
            # Schedule: full_season mode, regular season, ascending sort, no N limit
            block = fetch_game_record(team, season, key, 99, "asc", "full_season", "regular") if bypass \
                    else fetch_game_record_cached(team, season, key, 99, "asc", "full_season", "regular", ttl)
            cfg   = self._build_config()
            img   = GameRecordCardRenderer().render(block, cfg, self.settings.working_dir)
            self.after(0, lambda: self._done(img, None))
        except Exception as exc:
            logger.exception("Schedule fetch/render failed")
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
        name = self._fname_var.get().strip() or "schedule_card"
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
        from app.cards.game_record_card import GameRecordCardConfig
        team = self._team_var.get()
        cfg = GameRecordCardConfig(
            width_in=self._float(self._w_var, 6.0),
            height_in=self._float(self._h_var, 9.0),
            dpi=self.settings.dpi,
            bg_color=self._bg_var.get(),
            show_logo=self._show_logo_var.get(),
            show_summary=self._show_summary_var.get(),
            show_timestamp=self._show_ts_var.get(),
            use_team_colors=self._use_team_colors_var.get(),
            show_week=True,
            show_scores=self._show_scores_var.get(),
            team=team,
        )
        if cfg.use_team_colors and team:
            try:
                from app.data.teams_api import get_team_colors, apply_team_colors
                p, s = get_team_colors(team, self.settings.cfbd_api_key)
                pal = apply_team_colors({
                    "title_bg": cfg.title_bg, "title_fg": cfg.title_fg,
                    "header_bg": cfg.header_bg, "header_fg": cfg.header_fg,
                    "row_alt_color": cfg.row_alt_color,
                }, p, s)
                for k, v in pal.items():
                    if hasattr(cfg, k): setattr(cfg, k, v)
            except Exception:
                pass
        return cfg

    def _load_from_settings(self):
        s = self.settings
        self._w_var.set(str(s.schedule_width_in))
        self._h_var.set(str(s.schedule_height_in))
        self._global_var.set(s.schedule_use_global_size)
        self._season_var.set(str(s.schedule_season))
        self._team_var.set(s.schedule_team)
        self._show_logo_var.set(s.schedule_show_logos)
        self._show_scores_var.set(s.schedule_show_scores)
        self._show_summary_var.set(s.schedule_show_summary)
        self._show_ts_var.set(s.schedule_show_timestamp)
        self._use_team_colors_var.set(s.schedule_use_team_colors)
        self._bg_var.set(s.schedule_bg_color)
        self._fname_var.set(s.schedule_export_filename)
        self._append_ts_var.set(s.schedule_append_timestamp)
        self._on_global(); self._on_size()

    def apply(self):
        s = self.settings
        s.schedule_width_in         = self._float(self._w_var, 6.0)
        s.schedule_height_in        = self._float(self._h_var, 9.0)
        s.schedule_use_global_size  = self._global_var.get()
        s.schedule_season           = self._int(self._season_var, 0)
        s.schedule_team             = self._team_var.get()
        s.schedule_show_logos       = self._show_logo_var.get()
        s.schedule_show_scores      = self._show_scores_var.get()
        s.schedule_show_summary     = self._show_summary_var.get()
        s.schedule_show_timestamp   = self._show_ts_var.get()
        s.schedule_use_team_colors  = self._use_team_colors_var.get()
        s.schedule_bg_color         = self._bg_var.get()
        s.schedule_export_filename  = self._fname_var.get().strip()
        s.schedule_append_timestamp = self._append_ts_var.get()
