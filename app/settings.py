from __future__ import annotations

import json
import logging
import os
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WORKING_DIR = str(Path.home() / "CFBStatCards")


@dataclass
class Settings:
    working_dir: str = DEFAULT_WORKING_DIR

    # Global card defaults
    card_width_in: float = 6.0
    card_height_in: float = 4.0
    dpi: int = 300
    bg_color: str = "#FFFFFF"

    # Global column explainer separator
    col_explainer_sep: str = "="

    # Export canvas margin
    export_canvas_margin_pct: float = 0.0

    # Display timezone for kickoff times (ET / CT / MT / PT / AKT / HT / UTC)
    display_timezone: str = "ET"

    # Data cache TTL
    data_cache_ttl_minutes: int = 15

    # UI state
    window_geometry: str = ""

    # CFBD API key
    cfbd_api_key: str = ""

    # ---- Standings ----
    standings_scope: str = "SEC"
    standings_season: int = 0
    standings_column_mode: str = "auto"
    standings_show_logos: bool = True
    standings_show_timestamp: bool = False
    standings_show_col_explainers: bool = False
    standings_width_in: float = 6.0
    standings_height_in: float = 4.0
    standings_use_global_size: bool = False
    standings_bg_color: str = "#FFFFFF"
    standings_export_filename: str = "standings_card"
    standings_append_timestamp: bool = True

    # ---- Offense ----
    offense_scope: str = "All FBS"
    offense_season: int = 0
    offense_stat_type: str = "Scoring"
    offense_top_n: int = 10
    offense_min_plays: int = 200
    offense_column_mode: str = "auto"
    offense_show_logos: bool = True
    offense_show_rank_badges: bool = True
    offense_show_timestamp: bool = False
    offense_show_col_explainers: bool = False
    offense_width_in: float = 7.0
    offense_height_in: float = 5.0
    offense_use_global_size: bool = False
    offense_bg_color: str = "#FFFFFF"
    offense_export_filename: str = "offense_card"
    offense_append_timestamp: bool = True

    # ---- Defense ----
    defense_scope: str = "All FBS"
    defense_season: int = 0
    defense_stat_type: str = "Scoring Defense"
    defense_top_n: int = 10
    defense_column_mode: str = "auto"
    defense_show_logos: bool = True
    defense_show_rank_badges: bool = True
    defense_show_timestamp: bool = False
    defense_show_col_explainers: bool = False
    defense_width_in: float = 7.0
    defense_height_in: float = 5.0
    defense_use_global_size: bool = False
    defense_bg_color: str = "#FFFFFF"
    defense_export_filename: str = "defense_card"
    defense_append_timestamp: bool = True

    # ---- Passing ----
    passing_scope: str = "All FBS"
    passing_season: int = 0
    passing_sort_stat: str = "YDS"
    passing_top_n: int = 10
    passing_min_att: int = 100
    passing_column_mode: str = "auto"
    passing_show_logos: bool = True
    passing_show_rank_badges: bool = True
    passing_show_jersey_number: bool = False
    passing_show_timestamp: bool = False
    passing_show_col_explainers: bool = False
    passing_width_in: float = 7.0
    passing_height_in: float = 5.0
    passing_use_global_size: bool = False
    passing_bg_color: str = "#FFFFFF"
    passing_export_filename: str = "passing_card"
    passing_append_timestamp: bool = True

    # ---- Rushing ----
    rushing_scope: str = "All FBS"
    rushing_season: int = 0
    rushing_sort_stat: str = "YDS"
    rushing_top_n: int = 10
    rushing_min_carries: int = 50
    rushing_column_mode: str = "auto"
    rushing_show_logos: bool = True
    rushing_show_rank_badges: bool = True
    rushing_show_jersey_number: bool = False
    rushing_show_timestamp: bool = False
    rushing_show_col_explainers: bool = False
    rushing_width_in: float = 7.0
    rushing_height_in: float = 5.0
    rushing_use_global_size: bool = False
    rushing_bg_color: str = "#FFFFFF"
    rushing_export_filename: str = "rushing_card"
    rushing_append_timestamp: bool = True

    # ---- Receiving ----
    receiving_scope: str = "All FBS"
    receiving_season: int = 0
    receiving_sort_stat: str = "YDS"
    receiving_top_n: int = 10
    receiving_min_rec: int = 20
    receiving_column_mode: str = "auto"
    receiving_show_logos: bool = True
    receiving_show_rank_badges: bool = True
    receiving_show_jersey_number: bool = False
    receiving_show_timestamp: bool = False
    receiving_show_col_explainers: bool = False
    receiving_width_in: float = 7.0
    receiving_height_in: float = 5.0
    receiving_use_global_size: bool = False
    receiving_bg_color: str = "#FFFFFF"
    receiving_export_filename: str = "receiving_card"
    receiving_append_timestamp: bool = True

    # ---- Roster ----
    roster_team: str = "Alabama"
    roster_season: int = 0
    roster_group_by_position: bool = True
    roster_show_jersey_number: bool = True
    roster_show_hometown: bool = True
    roster_show_year: bool = True
    roster_show_height_weight: bool = False
    roster_show_logos: bool = True
    roster_show_timestamp: bool = False
    roster_show_col_explainers: bool = False
    roster_use_team_colors: bool = False
    roster_hide_ol: bool = False
    roster_hide_st: bool = False
    roster_columns: int = 1
    roster_group_filter: list = field(default_factory=list)
    roster_width_in: float = 5.0
    roster_height_in: float = 7.0
    roster_use_global_size: bool = False
    roster_bg_color: str = "#FFFFFF"
    roster_export_filename: str = "roster_card"
    roster_append_timestamp: bool = True

    # ---- Matchup ----
    matchup_team_a: str = "Alabama"
    matchup_team_b: str = "Georgia"
    matchup_season: int = 0
    matchup_stat_set: str = "Standard"
    matchup_win_highlight_color: str = "#D4EDDA"
    matchup_show_logos: bool = True
    matchup_show_timestamp: bool = False
    matchup_show_col_explainers: bool = False
    matchup_use_team_colors: bool = False
    matchup_width_in: float = 6.5
    matchup_height_in: float = 5.5
    matchup_use_global_size: bool = False
    matchup_bg_color: str = "#FFFFFF"
    matchup_export_filename: str = "matchup_card"
    matchup_append_timestamp: bool = True

    # ---- Career ----
    career_stat_type: str = "Passing"
    career_player_id: int = 0
    career_player_name: str = ""
    career_current_team_abbrev: str = ""
    career_year_start: int = 0
    career_year_end: int = 0
    career_year_sort: str = "Ascending"
    career_recent_players: list = field(default_factory=list)
    career_show_logos: bool = True
    career_highlight_current: bool = True
    career_show_timestamp: bool = False
    career_show_col_explainers: bool = False
    career_width_in: float = 7.0
    career_height_in: float = 6.0
    career_use_global_size: bool = False
    career_bg_color: str = "#FFFFFF"
    career_export_filename: str = "career_card"
    career_append_timestamp: bool = True

    # ---- Game Record ----
    game_record_team: str = "Alabama"
    game_record_season: int = 0
    game_record_n: int = 10
    game_record_date_sort: str = "desc"
    game_record_season_type: str = "both"     # "regular" | "postseason" | "both"
    game_record_mode: str = "season"          # "season" | "last_n"
    game_record_lastn_season_type: str = "both"
    game_record_max_seasons_back: int = 6
    game_record_show_year_in_date: bool = False
    game_record_show_season_breaks: bool = True
    game_record_show_results: bool = True
    game_record_result_placement: str = "column"
    game_record_time_placement: str = "column"
    game_record_column_order: str = "date"
    game_record_show_day_of_week: bool = False

    # ---- Schedule ----
    schedule_team: str = "Alabama"
    schedule_season: int = 0
    schedule_show_logos: bool = True
    schedule_show_opp_logos: bool = False
    schedule_show_scores: bool = True
    schedule_show_results: bool = True
    schedule_result_placement: str = "column"
    schedule_time_placement: str = "column"
    schedule_column_order: str = "schedule"
    schedule_show_ha_col: bool = False
    schedule_show_time: bool = True
    schedule_show_day_of_week: bool = False
    schedule_show_byes: bool = False
    schedule_show_summary: bool = True
    schedule_show_timestamp: bool = False
    schedule_use_team_colors: bool = False
    schedule_width_in: float = 6.0
    schedule_height_in: float = 9.0
    schedule_use_global_size: bool = False
    schedule_bg_color: str = "#FFFFFF"
    schedule_export_filename: str = "schedule_card"
    schedule_append_timestamp: bool = True
    game_record_series_detail: str = "result_only"
    game_record_show_logos: bool = True
    game_record_show_opp_logos: bool = False
    game_record_show_scores: bool = True
    game_record_show_ha_col: bool = True
    game_record_show_time: bool = True
    game_record_show_summary: bool = True
    game_record_show_timestamp: bool = False
    game_record_show_col_explainers: bool = False
    game_record_use_team_colors: bool = False
    game_record_date_sort: str = "desc"
    game_record_width_in: float = 6.0
    game_record_height_in: float = 8.0
    game_record_use_global_size: bool = False
    game_record_bg_color: str = "#FFFFFF"
    game_record_export_filename: str = "game_record_card"
    game_record_append_timestamp: bool = True

    # ---- Rankings ----
    rankings_season: int = 0
    rankings_week: int = 0          # 0 = latest available
    rankings_poll: str = "AP Top 25"
    rankings_season_type: str = "regular"
    rankings_show_logos: bool = True
    rankings_show_rank_badges: bool = True
    rankings_show_timestamp: bool = False
    rankings_show_col_explainers: bool = False
    rankings_width_in: float = 6.0
    rankings_height_in: float = 7.0
    rankings_use_global_size: bool = False
    rankings_bg_color: str = "#FFFFFF"
    rankings_export_filename: str = "rankings_card"
    rankings_append_timestamp: bool = True

    # ---- Playoffs ----
    playoffs_season: int = 0
    playoffs_show_logos: bool = True
    playoffs_show_scores: bool = True
    playoffs_show_seeds: bool = True
    playoffs_show_timestamp: bool = False
    playoffs_width_in: float = 10.0
    playoffs_height_in: float = 7.0
    playoffs_use_global_size: bool = False
    playoffs_bg_color: str = "#FFFFFF"
    playoffs_export_filename: str = "playoffs_card"
    playoffs_append_timestamp: bool = True

    _path: str = field(default="", repr=False, compare=False)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, working_dir: str) -> "Settings":
        settings_dir = os.path.join(working_dir, "settings")
        path = os.path.join(settings_dir, "settings.json")

        # One-time migration: root-level settings.json → settings/settings.json
        old_path = os.path.join(working_dir, "settings.json")
        if os.path.exists(old_path) and not os.path.exists(path):
            os.makedirs(settings_dir, exist_ok=True)
            shutil.move(old_path, path)
            logger.info("Migrated settings.json to %s", path)

        if not os.path.exists(path):
            obj = cls(working_dir=working_dir)
            obj._path = path
            return obj

        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except Exception:
            logger.exception("Failed to read settings from %s", path)
            obj = cls(working_dir=working_dir)
            obj._path = path
            return obj

        # Strip unknown keys so forward-compat is maintained
        known = {f.name for f in cls.__dataclass_fields__.values()
                 if f.name != "_path"}
        filtered = {k: v for k, v in raw.items() if k in known}

        obj = cls(**filtered)
        obj._path = path
        return obj

    def save(self, working_dir: str) -> None:
        settings_dir = os.path.join(working_dir, "settings")
        os.makedirs(settings_dir, exist_ok=True)
        path = os.path.join(settings_dir, "settings.json")

        data = {k: v for k, v in asdict(self).items() if k != "_path"}
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            self._path = path
        except Exception:
            logger.exception("Failed to save settings to %s", path)


def init_working_dir(working_dir: str) -> None:
    """Create the standard subdirectory layout inside working_dir."""
    for sub in ("output", "logos", "settings", "logs"):
        os.makedirs(os.path.join(working_dir, sub), exist_ok=True)

    readme = os.path.join(working_dir, "README.txt")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as fh:
            fh.write(
                "CFB Stat Card Maker — Working Directory\n"
                "========================================\n\n"
                "output/    Exported PNG and JPG stat cards\n"
                "logos/     Cached team logo images\n"
                "settings/  Application settings (settings.json)\n"
            )
