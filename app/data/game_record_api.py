"""Game record data fetching — a team's recent game results."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _current_season() -> int:
    """Most recently completed CFB season for Team Record data."""
    return datetime.datetime.now().year - 1


def _schedule_season() -> int:
    """The upcoming/current calendar year (used for full-season schedule mode)."""
    return datetime.datetime.now().year


def _source_date(start_time_utc: datetime.datetime) -> datetime.datetime:
    """Preserve the calendar date supplied with a game timestamp."""
    return start_time_utc.replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None
    )


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
    is_bye: bool = False


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
    mode: str = "last_n",        # "last_n" | "season" | "full_season"
    season_type: str = "regular", # "regular" | "postseason" | "both"
    working_dir: str | None = None,
) -> GameRecordBlock:
    if not api_key:
        raise ValueError("No CFBD API key configured. Add your key in Settings.")

    latest_completed = _current_season()
    if mode == "season" and season > latest_completed:
        raise ValueError(
            f"Team Record only supports completed seasons through {latest_completed}."
        )

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

        if mode == "season" and (team_score is None or opp_score is None):
            continue

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
                game_date = _source_date(start_time_utc)
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

    if mode == "full_season" and working_dir:
        _enrich_schedule_times(results, team, effective_season, working_dir)

    if mode == "season" and not results:
        raise RuntimeError(f"No completed game data found for {team} in {effective_season}.")

    # Sort — full season always ascending (chronological); last_n respects user choice
    effective_sort = "asc" if mode == "full_season" else date_sort
    results.sort(
        key=lambda r: (r.week or 99, r.date or datetime.datetime.min),
        reverse=(effective_sort == "desc"),
    )

    # Trim to N only in last_n mode
    if mode == "last_n":
        results = results[:n]

    # In full_season mode insert synthetic bye-week rows for week gaps
    if mode == "full_season":
        results = _insert_bye_weeks(results, effective_season)

    return GameRecordBlock(
        team=team,
        season=effective_season,
        total_wins=wins,
        total_losses=losses,
        as_of=datetime.datetime.now(),
        games=results,
    )


def _enrich_schedule_times(
    results: list[GameResult], team: str, season: int, working_dir: str
) -> None:
    """Fill missing upcoming CFBD kickoff times from ESPN when available."""
    try:
        from app.data.espn_schedule_api import fetch_espn_schedule
        from app.data.logo_cache import get_espn_id, slugify

        espn_id = get_espn_id(team, working_dir)
        if espn_id is None:
            return
        times = fetch_espn_schedule(espn_id, season, working_dir)
        for game in results:
            if game.is_bye or game.team_score is not None:
                continue
            if (
                game.start_time_utc is not None
                and not game.time_tbd
            ):
                continue
            date_key = (
                game.date.strftime("%Y-%m-%d")
                if game.start_time_utc is not None
                else game.date.strftime("%Y-%m-%d") if game.date else None
            )
            if date_key is None:
                continue
            espn_time, time_valid, team_slugs = times.get(date_key, (None, False, set()))
            opponent_slug = slugify(game.opponent)
            if not team_slugs or "__legacy_cache__" in team_slugs:
                continue
            if opponent_slug not in team_slugs:
                continue
            if time_valid and espn_time:
                game.start_time_utc = espn_time
                game.date = _source_date(espn_time)
                game.time_tbd = False
    except Exception:
        logger.debug("Could not enrich %s %s schedule times from ESPN", season, team)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _insert_bye_weeks(results: list[GameResult], season: int) -> list[GameResult]:
    """Insert synthetic bye-week entries for any missing regular-season weeks.

    Only considers weeks 1–15 (regular season). Postseason games (bowl, playoff)
    have week numbers in the 20s and are left untouched.
    """
    if not results:
        return results

    regular = [g for g in results if 1 <= g.week <= 15]
    other   = [g for g in results if g.week < 1 or g.week > 15]

    if len(regular) < 2:
        return results

    first_week = regular[0].week
    last_week  = regular[-1].week
    weeks_seen = {g.week for g in regular}

    byes: list[GameResult] = []
    for wk in range(first_week, last_week + 1):
        if wk not in weeks_seen:
            byes.append(GameResult(
                season=season,
                week=wk,
                date=None,
                opponent="BYE",
                is_home=False,
                is_neutral=False,
                team_score=None,
                opp_score=None,
                result="",
                notes="",
                time_tbd=False,
                is_bye=True,
            ))

    combined = regular + byes + other
    combined.sort(key=lambda r: (r.week or 99, r.date or datetime.datetime.min))
    return combined

_cache: dict[tuple, tuple[datetime.datetime, GameRecordBlock]] = {}


def fetch_last_n_across_seasons(
    team: str,
    api_key: str,
    n: int = 10,
    date_sort: str = "desc",
    season_type: str = "both",
    max_seasons_back: int = 6,
) -> GameRecordBlock:
    """Fetch the last N *completed* games for a team, crossing season boundaries.

    Starts from the current season and works backward until N completed games
    have been accumulated or max_seasons_back seasons have been searched.
    Future (unplayed) games are excluded.
    """
    if not api_key:
        raise ValueError("No CFBD API key configured. Add your key in Settings.")

    try:
        import cfbd
    except ImportError as exc:
        raise ImportError("The 'cfbd' package is not installed.") from exc

    if season_type == "postseason":
        st_arg = cfbd.SeasonType.POSTSEASON
    elif season_type == "both":
        st_arg = cfbd.SeasonType.BOTH
    else:
        st_arg = cfbd.SeasonType.REGULAR

    configuration = cfbd.Configuration()
    configuration.access_token = api_key
    api_client = cfbd.ApiClient(configuration)
    games_api = cfbd.GamesApi(api_client)

    all_results: list[GameResult] = []
    total_wins = total_losses = 0
    start_season = _schedule_season()

    for season_offset in range(max_seasons_back):
        check_season = start_season - season_offset
        try:
            raw = games_api.get_games(year=check_season, team=team, season_type=st_arg) or []
        except Exception as exc:
            logger.warning("API error fetching season %d for %s: %s", check_season, team, exc)
            break

        season_results: list[GameResult] = []
        for g in raw:
            is_home = g.home_team == team
            team_score = g.home_points if is_home else g.away_points
            opp_score  = g.away_points if is_home else g.home_points

            # Only include completed games
            if team_score is None or opp_score is None:
                continue

            opponent = g.away_team if is_home else g.home_team
            result = ""
            if team_score > opp_score:
                result = "W"
            elif team_score < opp_score:
                result = "L"
            else:
                result = "T"

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
                    game_date = _source_date(start_time_utc)
                except Exception:
                    pass

            season_results.append(GameResult(
                season=check_season,
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

        # Sort this season descending so the most-recent games come first,
        # then extend the accumulator (most recent season is always at the front)
        season_results.sort(
            key=lambda r: (r.week or 99, r.date or datetime.datetime.min),
            reverse=True,
        )
        all_results.extend(season_results)

        if len(all_results) >= n:
            break

    if not all_results:
        raise RuntimeError(f"No completed game data found for {team}.")

    # all_results is newest-season-first, newest-game-within-season-first.
    # Trim to the N most recent games.
    trimmed = all_results[:n]

    # Tally wins/losses from the trimmed set
    for g in trimmed:
        if g.result == "W":
            total_wins += 1
        elif g.result == "L":
            total_losses += 1

    # Apply user-requested sort order
    trimmed.sort(
        key=lambda r: (r.season, r.week or 99, r.date or datetime.datetime.min),
        reverse=(date_sort == "desc"),
    )

    return GameRecordBlock(
        team=team,
        season=trimmed[0].season if trimmed else start_season,
        total_wins=total_wins,
        total_losses=total_losses,
        as_of=datetime.datetime.now(),
        games=trimmed,
    )


_last_n_cache: dict[tuple, tuple[datetime.datetime, GameRecordBlock]] = {}


def fetch_last_n_across_seasons_cached(
    team: str,
    api_key: str,
    n: int = 10,
    date_sort: str = "desc",
    season_type: str = "both",
    ttl_minutes: int = 15,
    max_seasons_back: int = 6,
) -> GameRecordBlock:
    key = (team, n, date_sort, season_type, max_seasons_back)
    if key in _last_n_cache:
        ts, block = _last_n_cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_last_n_across_seasons(team, api_key, n, date_sort, season_type,
                                        max_seasons_back)
    _last_n_cache[key] = (datetime.datetime.now(), block)
    return block


def clear_game_record_last_n_cache() -> None:
    _last_n_cache.clear()


def fetch_game_record_cached(
    team: str,
    season: int,
    api_key: str,
    n: int = 10,
    date_sort: str = "desc",
    mode: str = "last_n",
    season_type: str = "regular",
    ttl_minutes: int = 15,
    working_dir: str | None = None,
) -> GameRecordBlock:
    key = (team, season, n, date_sort, mode, season_type, working_dir)
    if key in _cache:
        ts, block = _cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_game_record(team, season, api_key, n, date_sort, mode, season_type, working_dir)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_game_record_cache() -> None:
    _cache.clear()
    _last_n_cache.clear()
