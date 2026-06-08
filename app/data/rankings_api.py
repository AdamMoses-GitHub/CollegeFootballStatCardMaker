"""Rankings data fetching via the cfbd API."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

POLL_OPTIONS = [
    "AP Top 25",
    "Coaches Poll",
    "CFP Rankings",
    "AFCA Coaches",
]

# Map friendly names → cfbd poll name strings (partial match)
_POLL_NAME_MAP: dict[str, str] = {
    "AP Top 25":     "AP Top 25",
    "Coaches Poll":  "Coaches Poll",
    "CFP Rankings":  "College Football Playoff",
    "AFCA Coaches":  "AFCA Coaches",
}


def _current_season() -> int:
    now = datetime.datetime.now()
    return now.year if now.month >= 8 else now.year - 1


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RankingEntry:
    rank: int
    team_name: str
    team_abbrev: str
    conference: str
    first_place_votes: int
    points: int


@dataclass
class RankingsBlock:
    season: int
    week: int
    season_type: str
    poll: str
    as_of: datetime.datetime
    entries: list[RankingEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_rankings(
    season: int,
    week: int,
    poll: str,
    season_type: str,
    api_key: str,
) -> RankingsBlock:
    if not api_key:
        raise ValueError("No CFBD API key configured. Add your key in Settings.")

    try:
        import cfbd
    except ImportError as exc:
        raise ImportError("The 'cfbd' package is not installed.") from exc

    effective_season = season if season != 0 else _current_season()

    configuration = cfbd.Configuration()
    configuration.access_token = api_key
    api_client = cfbd.ApiClient(configuration)
    rankings_api = cfbd.RankingsApi(api_client)

    st = cfbd.SeasonType.REGULAR if season_type == "regular" else cfbd.SeasonType.POSTSEASON
    week_arg = week if week != 0 else None

    try:
        results = rankings_api.get_rankings(
            year=effective_season,
            season_type=st,
            week=week_arg,
        )
    except Exception as exc:
        logger.exception("cfbd API error fetching rankings")
        raise RuntimeError(f"API error: {exc}") from exc

    if not results:
        raise RuntimeError(f"No rankings data returned for {effective_season}.")

    # Find the most recent week if week=0
    results_sorted = sorted(results, key=lambda w: w.week or 0, reverse=True)
    target_week_data = results_sorted[0]
    actual_week = target_week_data.week or 0

    # Find the requested poll
    poll_target = _POLL_NAME_MAP.get(poll, poll)
    matched_poll = None
    for p in (target_week_data.polls or []):
        if poll_target.lower() in (p.poll or "").lower():
            matched_poll = p
            break

    if matched_poll is None:
        available = [p.poll for p in (target_week_data.polls or [])]
        raise RuntimeError(
            f"Poll '{poll}' not found for week {actual_week}. "
            f"Available: {available}"
        )

    entries: list[RankingEntry] = []
    for rank in (matched_poll.ranks or []):
        entries.append(RankingEntry(
            rank=rank.rank or 0,
            team_name=rank.school or "",
            team_abbrev=_slugify(rank.school or ""),
            conference=rank.conference or "",
            first_place_votes=rank.first_place_votes or 0,
            points=rank.points or 0,
        ))

    entries.sort(key=lambda e: e.rank)

    return RankingsBlock(
        season=effective_season,
        week=actual_week,
        season_type=season_type,
        poll=matched_poll.poll or poll,
        as_of=datetime.datetime.now(),
        entries=entries,
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_cache: dict[tuple, tuple[datetime.datetime, RankingsBlock]] = {}


def fetch_rankings_cached(
    season: int,
    week: int,
    poll: str,
    season_type: str,
    api_key: str,
    ttl_minutes: int = 15,
) -> RankingsBlock:
    key = (season, week, poll, season_type)
    if key in _cache:
        ts, block = _cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_rankings(season, week, poll, season_type, api_key)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_rankings_cache() -> None:
    _cache.clear()


def _slugify(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "").replace("&", "and")
