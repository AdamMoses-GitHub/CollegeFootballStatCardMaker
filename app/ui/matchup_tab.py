"""Matchup tab."""
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


class MatchupTab(ttk.Frame):
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
        from app.ui import make_scrollable_left_panel
        controls = make_scrollable_left_panel(pw)
        pf = ttk.LabelFrame(pw, text="Preview")
        pw.add(pf, weight=1)
        self._canvas = tk.Canvas(pf, bg="#CCCCCC", width=THUMB_W, height=THUMB_H)
        self._canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._canvas.bind("<Configure>", lambda e: self._update_thumb())
        self._build_controls(controls)

    def _build_controls(self, p):
        self._build_card_size(p)
        self._build_teams(p)
        self._build_options(p)
        self._build_display(p)
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

    def _build_teams(self, p):
        lf = ttk.LabelFrame(p, text="Teams & Season")
        lf.pack(fill="x", padx=8, pady=4)
        for label, attr in [("Team A:", "_ta_var"), ("Team B:", "_tb_var")]:
            r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=2)
            ttk.Label(r, text=label, width=8).pack(side="left")
            var = tk.StringVar(); setattr(self, attr, var)
            cb  = ttk.Combobox(r, textvariable=var, state="readonly", width=20)
            setattr(self, attr.replace("_var", "_cb"), cb)
            cb.pack(side="left", padx=(2,0))
        r2 = ttk.Frame(lf); r2.pack(fill="x", padx=6, pady=(2,6))
        ttk.Label(r2, text="Season:", width=8).pack(side="left")
        self._season_var = tk.StringVar()
        ttk.Spinbox(r2, from_=1970, to=datetime.datetime.now().year,
                    textvariable=self._season_var, width=7).pack(side="left", padx=(2,8))
        ttk.Label(r2, text="(0=current)", foreground="#555555").pack(side="left")

    def _build_options(self, p):
        lf = ttk.LabelFrame(p, text="Stat Set")
        lf.pack(fill="x", padx=8, pady=4)
        self._stat_set_var = tk.StringVar(value="Standard")
        for val in ("Standard", "Advanced"):
            ttk.Radiobutton(lf, text=val, variable=self._stat_set_var,
                            value=val).pack(anchor="w", padx=8, pady=1)

    def _build_display(self, p):
        lf = ttk.LabelFrame(p, text="Display Options")
        lf.pack(fill="x", padx=8, pady=4)
        self._logos_var = tk.BooleanVar(value=True)
        self._ts_var    = tk.BooleanVar(value=False)
        self._use_team_colors_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(lf, text="Show team logos",  variable=self._logos_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Use team colors",  variable=self._use_team_colors_var).pack(anchor="w", padx=8, pady=1)
        ttk.Checkbutton(lf, text="Show timestamp",   variable=self._ts_var).pack(anchor="w", padx=8, pady=(1,4))
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=(0,6))
        ttk.Label(r, text="Win highlight:").pack(side="left")
        self._hl_var = tk.StringVar(value="#D4EDDA")
        self._hl_var.trace_add("write", self._update_hl_swatch)
        ttk.Entry(r, textvariable=self._hl_var, width=9).pack(side="left", padx=(4,4))
        self._hl_swatch = tk.Label(r, width=3, relief="sunken", background="#D4EDDA")
        self._hl_swatch.pack(side="left", padx=(0,4))
        ttk.Button(r, text="Pick…",
                   command=lambda: self._pick("#D4EDDA", self._hl_var)).pack(side="left")

    def _update_hl_swatch(self, *_):
        c = self._hl_var.get()
        if c.startswith("#") and len(c) in (4,7):
            try: self._hl_swatch.config(background=c)
            except tk.TclError: pass

    def _build_bg_color(self, p):
        lf = ttk.LabelFrame(p, text="Background Color")
        lf.pack(fill="x", padx=8, pady=4)
        r = ttk.Frame(lf); r.pack(fill="x", padx=6, pady=6)
        self._bg_var = tk.StringVar(value="#FFFFFF")
        self._bg_var.trace_add("write", self._update_swatch)
        ttk.Entry(r, textvariable=self._bg_var, width=9).pack(side="left", padx=(0,4))
        self._swatch = tk.Label(r, width=3, relief="sunken", background="#FFFFFF")
        self._swatch.pack(side="left", padx=(0,4))
        ttk.Button(r, text="Pick…", command=lambda: self._pick("#FFFFFF", self._bg_var)).pack(side="left")

    def _update_swatch(self, *_):
        c = self._bg_var.get()
        if c.startswith("#") and len(c) in (4,7):
            try: self._swatch.config(background=c)
            except tk.TclError: pass

    def _pick(self, initial, var):
        r = colorchooser.askcolor(color=initial)
        if r and r[1]: var.set(r[1])

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
        self._fname_var = tk.StringVar(value="matchup_card")
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
        self._ta_cb.config(values=names)
        self._tb_cb.config(values=names)
        if self._ta_var.get() not in names and names:
            self._ta_var.set(names[0])
        if self._tb_var.get() not in names and names:
            self._tb_var.set(names[min(1, len(names)-1)])

    def _on_fetch(self): self._start_fetch(False)
    def _on_refresh(self): self._start_fetch(True)

    def _start_fetch(self, bypass):
        if self._fetching: return
        self._fetching = True
        self._fetch_btn.config(state="disabled"); self._refresh_btn.config(state="disabled")
        self._status.config(text="Fetching…", foreground="#555555")
        threading.Thread(target=self._fetch_thread, args=(bypass,), daemon=True).start()

    def _fetch_thread(self, bypass):
        try:
            from app.data.matchup_api import fetch_matchup, fetch_matchup_cached
            from app.cards.matchup_card import MatchupCardConfig, MatchupCardRenderer
            ta  = self._ta_var.get()
            tb  = self._tb_var.get()
            if not ta or not tb: raise ValueError("Please select both teams.")
            if ta == tb: raise ValueError("Teams must be different.")
            season   = self._int(self._season_var, 0)
            stat_set = self._stat_set_var.get()
            key      = self.settings.cfbd_api_key
            ttl      = self.settings.data_cache_ttl_minutes
            block    = fetch_matchup(ta, tb, season, stat_set, key) if bypass \
                       else fetch_matchup_cached(ta, tb, season, stat_set, key, ttl)
            cfg = self._build_config()
            img = MatchupCardRenderer().render(block, cfg, self.settings.working_dir)
            self.after(0, lambda: self._done(img, None))
        except Exception as exc:
            logger.exception("Matchup fetch/render failed")
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
        name = self._fname_var.get().strip() or "matchup_card"
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
        from app.cards.matchup_card import MatchupCardConfig
        ta  = self._ta_var.get()
        tb  = self._tb_var.get()
        use_colors = self._use_team_colors_var.get()
        cfg = MatchupCardConfig(
            width_in=self._float(self._w_var, 6.5),
            height_in=self._float(self._h_var, 5.5),
            dpi=self.settings.dpi,
            bg_color=self._bg_var.get(),
            show_logos=self._logos_var.get(),
            show_timestamp=self._ts_var.get(),
            stat_set=self._stat_set_var.get(),
            win_highlight=self._hl_var.get(),
            use_team_colors=use_colors,
        )
        if use_colors:
            try:
                from app.data.teams_api import get_team_colors, apply_team_colors, _auto_fg
                pa, sa = get_team_colors(ta, self.settings.cfbd_api_key)
                pb, sb = get_team_colors(tb, self.settings.cfbd_api_key)
                cfg.team_a_color = pa
                cfg.team_a_fg    = _auto_fg(pa)
                cfg.team_b_color = pb
                cfg.team_b_fg    = _auto_fg(pb)
                # Title bar blends both colors (use Team A primary)
                pal = apply_team_colors({
                    "title_bg": cfg.title_bg, "title_fg": cfg.title_fg,
                    "row_alt_color": cfg.row_alt_color,
                }, pa, sa)
                cfg.title_bg = pal.get("title_bg", cfg.title_bg)
                cfg.title_fg = pal.get("title_fg", cfg.title_fg)
            except Exception:
                pass
        return cfg

    def _load_from_settings(self):
        s = self.settings
        self._w_var.set(str(s.matchup_width_in))
        self._h_var.set(str(s.matchup_height_in))
        self._global_var.set(s.matchup_use_global_size)
        self._season_var.set(str(s.matchup_season))
        self._ta_var.set(s.matchup_team_a)
        self._tb_var.set(s.matchup_team_b)
        self._stat_set_var.set(s.matchup_stat_set)
        self._logos_var.set(s.matchup_show_logos)
        self._ts_var.set(s.matchup_show_timestamp)
        self._use_team_colors_var.set(s.matchup_use_team_colors)
        self._hl_var.set(s.matchup_win_highlight_color)
        self._bg_var.set(s.matchup_bg_color)
        self._fname_var.set(s.matchup_export_filename)
        self._append_ts_var.set(s.matchup_append_timestamp)
        self._on_global(); self._on_size()

    def apply(self):
        s = self.settings
        s.matchup_width_in  = self._float(self._w_var, 6.5)
        s.matchup_height_in = self._float(self._h_var, 5.5)
        s.matchup_use_global_size     = self._global_var.get()
        s.matchup_season              = self._int(self._season_var, 0)
        s.matchup_team_a              = self._ta_var.get()
        s.matchup_team_b              = self._tb_var.get()
        s.matchup_stat_set            = self._stat_set_var.get()
        s.matchup_show_logos          = self._logos_var.get()
        s.matchup_show_timestamp      = self._ts_var.get()
        s.matchup_use_team_colors     = self._use_team_colors_var.get()
        s.matchup_win_highlight_color = self._hl_var.get()
        s.matchup_bg_color            = self._bg_var.get()
        s.matchup_export_filename     = self._fname_var.get().strip()
        s.matchup_append_timestamp    = self._append_ts_var.get()
