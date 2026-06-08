"""Matchup data — head-to-head team comparison."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def _current_season() -> int:
    now = datetime.datetime.now()
    return now.year if now.month >= 8 else now.year - 1


@dataclass
class TeamSeasonStats:
    team: str
    games: int
    wins: int
    losses: int
    ppg: float
    opp_ppg: float
    total_yards_pg: float
    opp_yards_pg: float
    turnovers: int
    # Advanced
    epa_per_play: float | None
    success_rate: float | None
    explosiveness: float | None


@dataclass
class MatchupBlock:
    team_a: str
    team_b: str
    season: int
    stat_set: str
    all_time_wins_a: int
    all_time_wins_b: int
    all_time_ties: int
    stats_a: TeamSeasonStats
    stats_b: TeamSeasonStats
    as_of: datetime.datetime


def fetch_matchup(
    team_a: str,
    team_b: str,
    season: int,
    stat_set: str,
    api_key: str,
) -> MatchupBlock:
    if not api_key:
        raise ValueError("No CFBD API key configured.")

    try:
        import cfbd
    except ImportError as exc:
        raise ImportError("The 'cfbd' package is not installed.") from exc

    effective_season = season if season != 0 else _current_season()

    cfg = cfbd.Configuration()
    cfg.access_token = api_key
    client = cfbd.ApiClient(cfg)

    teams_api  = cfbd.TeamsApi(client)
    games_api  = cfbd.GamesApi(client)
    stats_api  = cfbd.StatsApi(client)

    # All-time head-to-head record
    try:
        matchup = teams_api.get_matchup(team1=team_a, team2=team_b)
        atw_a = matchup.team1_wins or 0
        atw_b = matchup.team2_wins or 0
        att   = matchup.ties or 0
    except Exception:
        atw_a = atw_b = att = 0

    # Season stats for each team
    stats_a = _fetch_team_stats(team_a, effective_season, stat_set, games_api, stats_api)
    stats_b = _fetch_team_stats(team_b, effective_season, stat_set, games_api, stats_api)

    return MatchupBlock(
        team_a=team_a,
        team_b=team_b,
        season=effective_season,
        stat_set=stat_set,
        all_time_wins_a=atw_a,
        all_time_wins_b=atw_b,
        all_time_ties=att,
        stats_a=stats_a,
        stats_b=stats_b,
        as_of=datetime.datetime.now(),
    )


def _stat_float(val) -> float:
    """Extract a numeric value from cfbd's TeamStatStatValue (or a plain float/int/str)."""
    if val is None:
        return 0.0
    # cfbd 5.x wraps stat values in TeamStatStatValue with .actual_instance
    actual = getattr(val, "actual_instance", val)
    try:
        return float(actual)
    except (TypeError, ValueError):
        return 0.0


def _fetch_team_stats(
    team: str, season: int, stat_set: str, games_api, stats_api
) -> TeamSeasonStats:
    # Season record from games
    wins = losses = 0
    total_pts = opp_pts = total_yds = opp_yds = turnovers = 0
    games_played = 0
    try:
        import cfbd
        games = games_api.get_games(year=season, team=team,
                                     season_type=cfbd.SeasonType.REGULAR) or []
        for g in games:
            if g.home_points is None or g.away_points is None:
                continue
            is_home = g.home_team == team
            pts     = g.home_points if is_home else g.away_points
            opp     = g.away_points if is_home else g.home_points
            if pts > opp:   wins += 1
            elif pts < opp: losses += 1
            total_pts += pts
            opp_pts   += opp
            games_played += 1
    except Exception:
        pass

    # Team stats (total yards)
    try:
        raw_stats = stats_api.get_team_stats(year=season, team=team) or []
        stat_map: dict[str, float] = {
            s.stat_name: _stat_float(s.stat_value) for s in raw_stats
        }
        total_yds = stat_map.get("totalYards", 0.0)
        opp_yds   = stat_map.get("totalYardsOpponent", 0.0)
        turnovers = int(stat_map.get("turnovers", 0))
        # Normalise to per-game
        g = games_played or 1
        total_yds = total_yds / g
        opp_yds   = opp_yds   / g
    except Exception:
        pass

    ppg     = total_pts / max(games_played, 1)
    opp_ppg = opp_pts   / max(games_played, 1)

    # Advanced stats
    epa = success = expl = None
    if stat_set == "Advanced":
        try:
            adv_list = stats_api.get_advanced_season_stats(year=season, team=team) or []
            if adv_list:
                adv = adv_list[0]
                if adv.offense:
                    epa     = adv.offense.ppa
                    success = adv.offense.success_rate
                    expl    = adv.offense.explosiveness
        except Exception:
            pass

    return TeamSeasonStats(
        team=team,
        games=games_played,
        wins=wins,
        losses=losses,
        ppg=round(ppg, 1),
        opp_ppg=round(opp_ppg, 1),
        total_yards_pg=round(total_yds, 1),
        opp_yards_pg=round(opp_yds, 1),
        turnovers=turnovers,
        epa_per_play=round(epa, 3) if epa is not None else None,
        success_rate=round(success * 100, 1) if success is not None else None,
        explosiveness=round(expl, 3) if expl is not None else None,
    )


_cache: dict[tuple, tuple[datetime.datetime, MatchupBlock]] = {}


def fetch_matchup_cached(
    team_a, team_b, season, stat_set, api_key, ttl_minutes=15
) -> MatchupBlock:
    key = (team_a, team_b, season, stat_set)
    if key in _cache:
        ts, block = _cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_matchup(team_a, team_b, season, stat_set, api_key)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_matchup_cache() -> None:
    _cache.clear()
