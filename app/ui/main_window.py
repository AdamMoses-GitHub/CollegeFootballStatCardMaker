"""Main application window for CFB Stat Card Maker."""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

from app.settings import Settings


class MainWindow(tk.Tk):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.title("CFB Stat Card Maker")
        self.resizable(True, True)

        # Restore geometry
        if settings.window_geometry:
            try:
                self.geometry(settings.window_geometry)
            except Exception:
                pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._tabs: list = []
        self._add_tabs()

        # Bottom bar
        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x")

        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)

        ttk.Button(bar, text="Open Output Directory",
                   command=self._open_output_dir).pack(side="left")
        ttk.Button(bar, text="Quit",
                   command=self._on_close).pack(side="right")

    def _add_tabs(self) -> None:
        from app.ui.standings_tab import StandingsTab
        from app.ui.rankings_tab import RankingsTab
        from app.ui.playoffs_tab import PlayoffsTab
        from app.ui.game_record_tab import GameRecordTab
        from app.ui.schedule_tab import ScheduleTab
        from app.ui.roster_tab import RosterTab
        from app.ui.matchup_tab import MatchupTab
        from app.ui.career_tab import CareerTab
        from app.ui.settings_tab import SettingsTab

        tabs_cfg = [
            ("  Standings  ",       StandingsTab),
            ("  Rankings  ",        RankingsTab),
            ("  Playoffs  ",        PlayoffsTab),
            ("  Team Record  ",     GameRecordTab),
            ("  Team Schedule  ",   ScheduleTab),
            ("  Team Roster  ",     RosterTab),
            ("  Matchup  ",         MatchupTab),
            ("  Player Career  ",   CareerTab),
            ("  Settings  ",        SettingsTab),
        ]

        for label, TabClass in tabs_cfg:
            tab = TabClass(self.notebook, self.settings)
            self.notebook.add(tab, text=label)
            self._tabs.append(tab)

    # ------------------------------------------------------------------
    # Bottom bar actions
    # ------------------------------------------------------------------

    def _open_output_dir(self) -> None:
        out_dir = os.path.join(self.settings.working_dir, "output")
        os.makedirs(out_dir, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(out_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", out_dir])
            else:
                subprocess.Popen(["xdg-open", out_dir])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        for tab in self._tabs:
            if hasattr(tab, "apply"):
                try:
                    tab.apply()
                except Exception:
                    pass
        self.settings.window_geometry = self.geometry()
        self.settings.save(self.settings.working_dir)
        self.destroy()
