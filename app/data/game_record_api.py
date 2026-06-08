"""Game record data fetching — a team's recent game results."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _current_season() -> int:
    """Last completed CFB season (used for game record / last-N mode)."""
    now = datetime.datetime.now()
    return now.year if now.month >= 8 else now.year - 1


def _schedule_season() -> int:
    """The upcoming/current calendar year (used for full-season schedule mode)."""
    return datetime.datetime.now().year


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class GameResult:
    season: int
    week: int
    date: datetime.datetime | None
    opponent: str
    is_home: bool
    is_neutral: bool
    team_score: int | None
    opp_score: int | None
    result: str      # "W", "L", "T", or ""
    notes: str       # bowl game name if applicable
    start_time_utc: datetime.datetime | None = None
    time_tbd: bool = True


@dataclass
class GameRecordBlock:
    team: str
    season: int
    total_wins: int
    total_losses: int
    as_of: datetime.datetime
    games: list[GameResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_game_record(
    team: str,
    season: int,
    api_key: str,
    n: int = 10,
    date_sort: str = "desc",
    mode: str = "last_n",        # "last_n" | "full_season"
    season_type: str = "regular", # "regular" | "postseason" | "both"
) -> GameRecordBlock:
    if not api_key:
        raise ValueError("No CFBD API key configured. Add your key in Settings.")

    try:
        import cfbd
    except ImportError as exc:
        raise ImportError("The 'cfbd' package is not installed.") from exc

    # Season resolution: schedule mode uses the current calendar year;
    # last-N mode uses the last completed season
    if season != 0:
        effective_season = season
    elif mode == "full_season":
        effective_season = _schedule_season()
    else:
        effective_season = _current_season()

    configuration = cfbd.Configuration()
    configuration.access_token = api_key
    api_client = cfbd.ApiClient(configuration)
    games_api = cfbd.GamesApi(api_client)

    # Build season_type argument
    if season_type == "postseason":
        st_arg = cfbd.SeasonType.POSTSEASON
    elif season_type == "both":
        st_arg = cfbd.SeasonType.BOTH
    else:
        st_arg = cfbd.SeasonType.REGULAR

    try:
        games = games_api.get_games(year=effective_season, team=team,
                                     season_type=st_arg)
    except Exception as exc:
        logger.exception("cfbd API error fetching game record")
        raise RuntimeError(f"API error: {exc}") from exc

    if not games:
        raise RuntimeError(f"No game data found for {team} in {effective_season} "
                           f"({season_type}).")

    results: list[GameResult] = []
    wins = losses = 0

    for g in games:
        is_home = g.home_team == team
        opponent = g.away_team if is_home else g.home_team
        team_score = g.home_points if is_home else g.away_points
        opp_score  = g.away_points if is_home else g.home_points

        result = ""
        if team_score is not None and opp_score is not None:
            if team_score > opp_score:
                result = "W"
                wins += 1
            elif team_score < opp_score:
                result = "L"
                losses += 1
            else:
                result = "T"

        # start_date is already a datetime object from cfbd 5.x
        game_date: datetime.datetime | None = None
        start_time_utc: datetime.datetime | None = None
        time_tbd: bool = bool(g.start_time_tbd)

        if g.start_date:
            try:
                if isinstance(g.start_date, datetime.datetime):
                    start_time_utc = g.start_date
                else:
                    start_time_utc = datetime.datetime.fromisoformat(
                        str(g.start_date).replace("Z", "+00:00")
                    )
                # Date (day only) for display — strip time component
                game_date = start_time_utc.replace(
                    hour=0, minute=0, second=0, microsecond=0,
                    tzinfo=None,
                )
            except Exception:
                pass

        results.append(GameResult(
            season=effective_season,
            week=g.week or 0,
            date=game_date,
            opponent=opponent or "",
            is_home=is_home,
            is_neutral=g.neutral_site or False,
            team_score=team_score,
            opp_score=opp_score,
            result=result,
            notes=g.notes or "",
            start_time_utc=start_time_utc,
            time_tbd=time_tbd,
        ))

    # Sort — full season always ascending (chronological); last_n respects user choice
    effective_sort = "asc" if mode == "full_season" else date_sort
    results.sort(
        key=lambda r: (r.week or 99, r.date or datetime.datetime.min),
        reverse=(effective_sort == "desc"),
    )

    # Trim to N only in last_n mode
    if mode == "last_n":
        results = results[:n]

    return GameRecordBlock(
        team=team,
        season=effective_season,
        total_wins=wins,
        total_losses=losses,
        as_of=datetime.datetime.now(),
        games=results,
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_cache: dict[tuple, tuple[datetime.datetime, GameRecordBlock]] = {}


def fetch_game_record_cached(
    team: str,
    season: int,
    api_key: str,
    n: int = 10,
    date_sort: str = "desc",
    mode: str = "last_n",
    season_type: str = "regular",
    ttl_minutes: int = 15,
) -> GameRecordBlock:
    key = (team, season, n, date_sort, mode, season_type)
    if key in _cache:
        ts, block = _cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_game_record(team, season, api_key, n, date_sort, mode, season_type)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_game_record_cache() -> None:
    _cache.clear()
