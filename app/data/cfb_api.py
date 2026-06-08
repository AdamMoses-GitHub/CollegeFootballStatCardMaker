"""CFB standings data fetching via the cfbd Python client.

API reference: https://api.collegefootballdata.com
cfbd PyPI package: https://pypi.org/project/cfbd/
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Current season helper
# ---------------------------------------------------------------------------

def _current_season() -> int:
    """Return the current CFB season year.

    College football seasons start in late August/September.  If we're in
    January–July treat the previous calendar year as the current season.
    """
    now = datetime.datetime.now()
    return now.year if now.month >= 8 else now.year - 1


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class StandingsEntry:
    team_name: str
    team_abbrev: str
    conference: str
    wins: int
    losses: int
    conf_wins: int
    conf_losses: int
    points_for: float
    points_against: float
    streak: str  # e.g. "W3" or "L1"

    @property
    def pct(self) -> float:
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0

    @property
    def pct_str(self) -> str:
        return f"{self.pct:.3f}".lstrip("0") or ".000"


@dataclass
class StandingsBlock:
    season: int
    conference: str
    as_of: datetime.datetime
    entries: list[StandingsEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_standings(
    season: int,
    conference: str,
    api_key: str,
) -> StandingsBlock:
    """Fetch standings from the cfbd API.

    Args:
        season: Season year (0 = current season).
        conference: Conference name from SCOPE_OPTIONS (a specific conference).
        api_key: CFBD Bearer token.

    Returns:
        StandingsBlock with entries sorted by win percentage descending.
    """
    if not api_key:
        raise ValueError("No CFBD API key configured.  Add your key in Settings.")

    try:
        import cfbd
    except ImportError as exc:
        raise ImportError(
            "The 'cfbd' package is not installed.  Run: pip install cfbd"
        ) from exc

    effective_season = season if season != 0 else _current_season()

    configuration = cfbd.Configuration()
    configuration.access_token = api_key
    api_client = cfbd.ApiClient(configuration)
    games_api = cfbd.GamesApi(api_client)

    # Map our friendly conference names to cfbd conference abbreviations
    conf_abbrev = _CONF_NAME_TO_ABBREV.get(conference)

    try:
        records = games_api.get_records(
            year=effective_season,
            conference=conf_abbrev,
        )
    except Exception as exc:
        logger.exception("cfbd API error fetching standings")
        raise RuntimeError(f"API error: {exc}") from exc

    entries: list[StandingsEntry] = []
    for rec in (records or []):
        total = rec.total if rec.total else None
        conf_rec = rec.conference_games if rec.conference_games else None

        wins = getattr(total, "wins", 0) or 0
        losses = getattr(total, "losses", 0) or 0
        conf_wins = getattr(conf_rec, "wins", 0) or 0
        conf_losses = getattr(conf_rec, "losses", 0) or 0

        # Points for/against come from expected_wins field or are unavailable
        # — use 0.0 as placeholder; real values need game data aggregation
        pf = 0.0
        pa = 0.0

        entry = StandingsEntry(
            team_name=rec.team or "",
            team_abbrev=_slugify(rec.team or ""),
            conference=rec.conference or "",
            wins=wins,
            losses=losses,
            conf_wins=conf_wins,
            conf_losses=conf_losses,
            points_for=pf,
            points_against=pa,
            streak="",
        )
        entries.append(entry)

    # Enrich with points for/against via game results
    entries = _enrich_with_scores(entries, effective_season, api_client, conf_abbrev)

    # Sort: win pct descending, then wins descending
    entries.sort(key=lambda e: (e.pct, e.wins), reverse=True)

    return StandingsBlock(
        season=effective_season,
        conference=conference,
        as_of=datetime.datetime.now(),
        entries=entries,
    )


def _enrich_with_scores(
    entries: list[StandingsEntry],
    season: int,
    api_client,
    conf_abbrev: Optional[str],
) -> list[StandingsEntry]:
    """Aggregate points for/against from game results."""
    try:
        import cfbd
        games_api = cfbd.GamesApi(api_client)
        games = games_api.get_games(year=season, season_type=cfbd.SeasonType.REGULAR)
    except Exception:
        logger.warning("Could not fetch game scores for PF/PA enrichment")
        return entries

    pf_map: dict[str, float] = {}
    pa_map: dict[str, float] = {}
    streak_map: dict[str, str] = {}
    last_game_map: dict[str, tuple[int, str]] = {}  # team → (game_id, result)

    for game in (games or []):
        if game.home_points is None or game.away_points is None:
            continue
        ht = game.home_team
        at = game.away_team
        hp = game.home_points
        ap = game.away_points

        pf_map[ht] = pf_map.get(ht, 0.0) + hp
        pa_map[ht] = pa_map.get(ht, 0.0) + ap
        pf_map[at] = pf_map.get(at, 0.0) + ap
        pa_map[at] = pa_map.get(at, 0.0) + hp

        gid = game.id or 0
        for team, scored, allowed in [(ht, hp, ap), (at, ap, hp)]:
            result = "W" if scored > allowed else "L"
            prev = last_game_map.get(team)
            if prev is None or gid > prev[0]:
                last_game_map[team] = (gid, result)

    # Build streak strings (simplified: just last result)
    for team, (_, result) in last_game_map.items():
        streak_map[team] = result

    for entry in entries:
        entry.points_for = pf_map.get(entry.team_name, 0.0)
        entry.points_against = pa_map.get(entry.team_name, 0.0)
        entry.streak = streak_map.get(entry.team_name, "")

    return entries


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------

_cache: dict[tuple, tuple[datetime.datetime, StandingsBlock]] = {}


def fetch_standings_cached(
    season: int,
    conference: str,
    api_key: str,
    ttl_minutes: int = 15,
) -> StandingsBlock:
    key = (season, conference)
    if key in _cache:
        ts, block = _cache[key]
        age = (datetime.datetime.now() - ts).total_seconds()
        if age < ttl_minutes * 60:
            return block
    block = fetch_standings(season, conference, api_key)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_standings_cache() -> None:
    _cache.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_").replace(".", "")


_CONF_NAME_TO_ABBREV: dict[str, Optional[str]] = {
    "SEC":               "SEC",
    "Big Ten":           "Big Ten",
    "Big 12":            "Big 12",
    "ACC":               "ACC",
    "Pac-12":            "Pac-12",
    "American Athletic": "AAC",
    "Mountain West":     "MWC",
    "Sun Belt":          "Sun Belt",
    "MAC":               "MAC",
    "Conference USA":    "CUSA",
    "Independents":      "Ind",
}
