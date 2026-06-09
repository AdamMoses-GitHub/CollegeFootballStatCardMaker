"""Settings tab for CFB Stat Card Maker."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tkinter as tk
from tkinter import colorchooser, filedialog, ttk

from app.settings import Settings

logger = logging.getLogger(__name__)


class SettingsTab(ttk.Frame):
    def __init__(self, parent: ttk.Notebook, settings: Settings) -> None:
        super().__init__(parent)
        self.settings = settings
        self._build_ui()
        self._load_from_settings()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # Scrollable canvas so the tab doesn't overflow on small screens
        canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = ttk.Frame(canvas)
        self._window_id = canvas.create_window((0, 0), window=self._inner, anchor="nw")

        self._inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._window_id, width=e.width),
        )

        self._canvas = canvas
        self._build_sections(self._inner)

    def _build_sections(self, parent: ttk.Frame) -> None:
        self._build_working_dir(parent)
        self._build_default_card_size(parent)
        self._build_export_dpi(parent)
        self._build_default_bg_color(parent)
        self._build_data_cache(parent)
        self._build_col_explainer_sep(parent)
        self._build_export_margin(parent)
        self._build_timezone(parent)
        self._build_api_key(parent)
        self._build_log_section(parent)

        ttk.Button(
            parent, text="Save Settings", command=self.apply
        ).pack(anchor="e", padx=12, pady=10)

    # ---- 8.1 Working Directory ----------------------------------------

    def _build_working_dir(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Working Directory")
        lf.pack(fill="x", padx=8, pady=4)

        ttk.Label(
            lf, text="Output folder for cards, logos, and settings:"
        ).pack(anchor="w", padx=8, pady=(4, 0))

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=4)

        self._working_dir_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._working_dir_var, width=52).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(row, text="Browse…", command=self._browse_working_dir).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(row, text="Open…", command=self._open_working_dir).pack(
            side="left"
        )

    def _browse_working_dir(self) -> None:
        d = filedialog.askdirectory(
            initialdir=self._working_dir_var.get() or os.path.expanduser("~")
        )
        if d:
            self._working_dir_var.set(d)

    def _open_working_dir(self) -> None:
        d = self._working_dir_var.get()
        if not d:
            return
        os.makedirs(d, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(d)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", d])
            else:
                subprocess.Popen(["xdg-open", d])
        except Exception:
            pass

    # ---- 8.2 Default Card Size ----------------------------------------

    def _build_default_card_size(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Default Card Size")
        lf.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=6)

        ttk.Label(row, text="Width (in):").pack(side="left")
        self._card_w_var = tk.StringVar()
        ttk.Spinbox(
            row, from_=1.0, to=24.0, increment=0.5,
            textvariable=self._card_w_var, width=6,
        ).pack(side="left", padx=(2, 12))

        ttk.Label(row, text="Height (in):").pack(side="left")
        self._card_h_var = tk.StringVar()
        ttk.Spinbox(
            row, from_=1.0, to=24.0, increment=0.5,
            textvariable=self._card_h_var, width=6,
        ).pack(side="left", padx=(2, 12))

        self._size_orient_label = ttk.Label(row, text="", foreground="#555555")
        self._size_orient_label.pack(side="left")

        for var in (self._card_w_var, self._card_h_var):
            var.trace_add("write", self._update_size_orient)

    def _update_size_orient(self, *_) -> None:
        try:
            w = float(self._card_w_var.get())
            h = float(self._card_h_var.get())
            self._size_orient_label.config(
                text="(Landscape)" if w >= h else "(Portrait)"
            )
        except ValueError:
            pass

    # ---- 8.3 Export DPI -----------------------------------------------

    def _build_export_dpi(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Export DPI")
        lf.pack(fill="x", padx=8, pady=4)

        self._dpi_var = tk.IntVar()
        row1 = ttk.Frame(lf)
        row1.pack(fill="x", padx=8, pady=(6, 2))
        for dpi_val in (72, 150, 300, 600):
            ttk.Radiobutton(
                row1, text=str(dpi_val), variable=self._dpi_var, value=dpi_val
            ).pack(side="left", padx=4)
        row2 = ttk.Frame(lf)
        row2.pack(fill="x", padx=8, pady=(0, 6))
        for dpi_val in (900, 1200, 1500, 1800):
            ttk.Radiobutton(
                row2, text=str(dpi_val), variable=self._dpi_var, value=dpi_val
            ).pack(side="left", padx=4)
        ttk.Label(row2, text="  Custom:").pack(side="left")
        self._dpi_custom_var = tk.StringVar()
        ttk.Spinbox(
            row2, from_=72, to=1800, increment=50,
            textvariable=self._dpi_custom_var, width=6,
            command=self._on_dpi_custom,
        ).pack(side="left", padx=(2, 0))

    def _on_dpi_custom(self) -> None:
        try:
            self._dpi_var.set(int(self._dpi_custom_var.get()))
        except ValueError:
            pass

    # ---- 8.4 Default Background Color ---------------------------------

    def _build_default_bg_color(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Default Background Color")
        lf.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=6)

        self._bg_color_var = tk.StringVar(value="#FFFFFF")
        self._bg_color_var.trace_add("write", self._update_bg_swatch)

        ttk.Entry(row, textvariable=self._bg_color_var, width=10).pack(
            side="left", padx=(0, 4)
        )
        self._bg_swatch = tk.Label(
            row, width=3, relief="sunken", background="#FFFFFF"
        )
        self._bg_swatch.pack(side="left", padx=(0, 4))
        ttk.Button(row, text="Pick Color…", command=self._pick_bg_color).pack(
            side="left"
        )

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

    # ---- 8.5 Data Cache -----------------------------------------------

    def _build_data_cache(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Data Cache")
        lf.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=(6, 0))

        ttk.Label(row, text="API cache TTL:").pack(side="left")
        self._cache_ttl_var = tk.StringVar()
        ttk.Spinbox(
            row, from_=1, to=1440, increment=5,
            textvariable=self._cache_ttl_var, width=6,
        ).pack(side="left", padx=(2, 4))
        ttk.Label(row, text="minutes").pack(side="left")

        ttk.Label(
            lf,
            text=(
                "Fetched data is cached in memory for this many minutes.\n"
                "Use ↺ Refresh on any tab to bypass the cache."
            ),
            foreground="#555555",
            wraplength=420,
        ).pack(anchor="w", padx=8, pady=(2, 4))

        ttk.Button(
            lf, text="Clear Memory Cache", command=self._clear_cache
        ).pack(anchor="w", padx=8, pady=(0, 6))

    def _clear_cache(self) -> None:
        for module, fn in [
            ("app.data.cfb_api",          "clear_standings_cache"),
            ("app.data.logo_cache",        "clear_logo_memory_cache"),
            ("app.data.game_record_api",   "clear_game_record_cache"),
            ("app.data.game_record_api",   "clear_game_record_last_n_cache"),
            ("app.data.matchup_api",       "clear_matchup_cache"),
            ("app.data.roster_api",        "clear_roster_cache"),
            ("app.data.career_api",        "clear_career_cache"),
            ("app.data.rankings_api",      "clear_rankings_cache"),
            ("app.data.playoffs_api",      "clear_playoffs_cache"),
            ("app.data.teams_api",         "clear_teams_cache"),
        ]:
            try:
                import importlib
                mod = importlib.import_module(module)
                getattr(mod, fn)()
            except Exception:
                pass

    # ---- 8.6 Column Explainer Separator --------------------------------

    def _build_col_explainer_sep(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Column Explainer Separator")
        lf.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=6)

        self._col_sep_var = tk.StringVar(value="=")
        seps = [
            ("=", '=  · e.g. OPS=OBP+SLG'),
            (":", ':  · e.g. OPS: OBP+SLG'),
            ("–", '–  · e.g. OPS–OBP+SLG'),
        ]
        for val, label in seps:
            ttk.Radiobutton(
                row, text=label, variable=self._col_sep_var, value=val
            ).pack(side="left", padx=8)

    # ---- 8.7 Export Canvas Margin -------------------------------------

    def _build_export_margin(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Export Canvas Margin")
        lf.pack(fill="x", padx=8, pady=4)

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=6)

        self._margin_var = tk.StringVar()
        ttk.Spinbox(
            row, from_=0.0, to=20.0, increment=0.5,
            textvariable=self._margin_var, width=6,
        ).pack(side="left")
        ttk.Label(row, text="%").pack(side="left", padx=(2, 12))
        ttk.Label(
            row,
            text="Adds a border of this size around the card on export (PNG/JPG only).",
            foreground="#555555",
        ).pack(side="left")

    # ---- API Key section (CFB-specific) --------------------------------

    def _build_timezone(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Display Timezone")
        lf.pack(fill="x", padx=8, pady=4)
        self._tz_var = tk.StringVar(value="ET")
        row1 = ttk.Frame(lf)
        row1.pack(fill="x", padx=8, pady=(6, 2))
        for tz in ("ET", "CT", "MT", "PT"):
            ttk.Radiobutton(row1, text=tz, variable=self._tz_var, value=tz).pack(side="left", padx=4)
        row2 = ttk.Frame(lf)
        row2.pack(fill="x", padx=8, pady=(0, 2))
        for tz in ("AKT", "HT", "UTC"):
            ttk.Radiobutton(row2, text=tz, variable=self._tz_var, value=tz).pack(side="left", padx=4)
        ttk.Label(
            lf,
            text="Used for kickoff times on schedule and game record cards.",
            foreground="#555555",
        ).pack(anchor="w", padx=8, pady=(0, 6))

    # ---- API Key section (CFB-specific) --------------------------------

    def _build_api_key(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(
            parent, text="College Football Data API Key"
        )
        lf.pack(fill="x", padx=8, pady=4)

        ttk.Label(
            lf,
            text=(
                "Required for all data fetches.  "
                "Get a free key at https://collegefootballdata.com"
            ),
            foreground="#555555",
            wraplength=480,
        ).pack(anchor="w", padx=8, pady=(4, 2))

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=4)

        self._api_key_var = tk.StringVar()
        self._api_key_entry = ttk.Entry(
            row, textvariable=self._api_key_var
        )
        self._api_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        ttk.Button(
            row, text="Show/Hide", command=self._toggle_api_key_vis
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            row, text="Test Key", command=self._test_api_key
        ).pack(side="left")

        self._api_key_status_label = ttk.Label(lf, text="", foreground="#555555")
        self._api_key_status_label.pack(anchor="w", padx=8, pady=(0, 6))

    def _toggle_api_key_vis(self) -> None:
        current = self._api_key_entry.cget("show")
        self._api_key_entry.config(show="" if current == "*" else "*")

    def _test_api_key(self) -> None:
        import threading
        key = self._api_key_var.get().strip()
        if not key:
            self._api_key_status_label.config(
                text="✗ No key entered.", foreground="#aa2200"
            )
            return
        self._api_key_status_label.config(
            text="Testing…", foreground="#555555"
        )

        def _do_test() -> None:
            try:
                import cfbd
                config = cfbd.Configuration()
                config.access_token = key
                client = cfbd.ApiClient(config)
                games_api = cfbd.GamesApi(client)
                # A lightweight call — just fetch 1 game
                games_api.get_records(year=2023, team="Alabama")
                self.after(0, lambda: self._api_key_status_label.config(
                    text="✓ Key valid", foreground="#006600"
                ))
            except Exception as exc:
                logger.exception("API key test failed")
                msg = f"✗ Key invalid: {exc}"
                self.after(0, lambda: self._api_key_status_label.config(
                    text=msg[:80], foreground="#aa2200"
                ))

        threading.Thread(target=_do_test, daemon=True).start()

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    # ---- Log file section --------------------------------------------

    def _build_log_section(self, parent: ttk.Frame) -> None:
        lf = ttk.LabelFrame(parent, text="Application Log")
        lf.pack(fill="x", padx=8, pady=4)

        ttk.Label(
            lf,
            text="Log file location:  {working_dir}/logs/cfb_stat_card_maker.log",
            foreground="#555555",
        ).pack(anchor="w", padx=8, pady=(4, 2))

        row = ttk.Frame(lf)
        row.pack(fill="x", padx=8, pady=(2, 6))
        ttk.Button(row, text="Open Log File…", command=self._open_log).pack(side="left", padx=(0, 6))
        ttk.Button(row, text="Open Log Folder…", command=self._open_log_dir).pack(side="left")

    def _open_log(self) -> None:
        import subprocess
        log_path = os.path.join(
            self._working_dir_var.get().strip(), "logs", "cfb_stat_card_maker.log"
        )
        if not os.path.exists(log_path):
            return
        try:
            if sys.platform == "win32":
                os.startfile(log_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", log_path])
            else:
                subprocess.Popen(["xdg-open", log_path])
        except Exception:
            pass

    def _open_log_dir(self) -> None:
        log_dir = os.path.join(self._working_dir_var.get().strip(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(log_dir)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", log_dir])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", log_dir])
        except Exception:
            pass

    # ------------------------------------------------------------------

    def _load_from_settings(self) -> None:
        s = self.settings
        self._working_dir_var.set(s.working_dir)
        self._card_w_var.set(str(s.card_width_in))
        self._card_h_var.set(str(s.card_height_in))
        self._dpi_var.set(s.dpi)
        self._dpi_custom_var.set(str(s.dpi))
        self._bg_color_var.set(s.bg_color)
        self._cache_ttl_var.set(str(s.data_cache_ttl_minutes))
        self._col_sep_var.set(s.col_explainer_sep)
        self._margin_var.set(str(s.export_canvas_margin_pct))
        self._tz_var.set(getattr(s, "display_timezone", "ET"))
        self._api_key_var.set(s.cfbd_api_key)
        self._update_size_orient()
        self._update_bg_swatch()

    def apply(self) -> None:
        """Serialize UI state back into settings."""
        s = self.settings
        s.working_dir = self._working_dir_var.get().strip()
        try:
            s.card_width_in = float(self._card_w_var.get())
        except ValueError:
            pass
        try:
            s.card_height_in = float(self._card_h_var.get())
        except ValueError:
            pass
        try:
            s.dpi = int(self._dpi_var.get())
        except (ValueError, tk.TclError):
            pass
        s.bg_color = self._bg_color_var.get().strip()
        try:
            s.data_cache_ttl_minutes = int(self._cache_ttl_var.get())
        except ValueError:
            pass
        s.col_explainer_sep = self._col_sep_var.get()
        try:
            s.export_canvas_margin_pct = float(self._margin_var.get())
        except ValueError:
            pass
        s.display_timezone = self._tz_var.get()
        s.cfbd_api_key = self._api_key_var.get().strip()
        from app.data import logo_cache
        logo_cache.set_api_key(s.cfbd_api_key)
        s.save(s.working_dir)
