"""Player career stats data fetching via cfbd."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _current_season() -> int:
    now = datetime.datetime.now()
    return now.year if now.month >= 8 else now.year - 1


@dataclass
class PlayerSearchResult:
    player_id: int
    name: str
    team: str
    position: str
    jersey: str


@dataclass
class CareerSeasonRow:
    season: int
    team: str
    games: int
    stats: dict[str, str]   # column_key -> formatted value


@dataclass
class CareerBlock:
    player_id: int
    player_name: str
    position: str
    stat_type: str
    as_of: datetime.datetime
    rows: list[CareerSeasonRow] = field(default_factory=list)


# Column sets per stat type
CAREER_COLS: dict[str, list[str]] = {
    "Passing":   ["YEAR", "TEAM", "G", "CMP", "ATT", "YDS", "TD", "INT", "RATING"],
    "Rushing":   ["YEAR", "TEAM", "G", "CAR", "YDS", "AVG", "TD"],
    "Receiving": ["YEAR", "TEAM", "G", "REC", "YDS", "AVG", "TD"],
    "Defense":   ["YEAR", "TEAM", "G", "TKL", "SACKS", "INT", "PD", "FF"],
}

CAREER_COL_EXPLAINERS: dict[str, str] = {
    "YEAR":   "Season",
    "TEAM":   "Team",
    "G":      "Games",
    "CMP":    "Completions",
    "ATT":    "Attempts",
    "YDS":    "Yards",
    "TD":     "Touchdowns",
    "INT":    "Interceptions",
    "RATING": "Passer Rating",
    "CAR":    "Carries",
    "AVG":    "Avg Yards",
    "REC":    "Receptions",
    "TKL":    "Tackles",
    "SACKS":  "Sacks",
    "PD":     "Pass Deflections",
    "FF":     "Forced Fumbles",
}

# cfbd stat category and stat_type names per career stat type
_CATEGORY_MAP: dict[str, str] = {
    "Passing":   "passing",
    "Rushing":   "rushing",
    "Receiving": "receiving",
    "Defense":   "defensive",
}
_STAT_KEYS: dict[str, dict[str, str]] = {
    "Passing": {
        "completions": "CMP",
        "attempts":    "ATT",
        "yards":       "YDS",
        "touchdowns":  "TD",
        "interceptions": "INT",
        "passer_rating": "RATING",
    },
    "Rushing": {
        "car": "CAR",
        "yds": "YDS",
        "avg": "AVG",
        "td":  "TD",
    },
    "Receiving": {
        "rec": "REC",
        "yds": "YDS",
        "avg": "AVG",
        "td":  "TD",
    },
    "Defense": {
        "tot": "TKL",
        "sacks": "SACKS",
        "int": "INT",
        "pd":  "PD",
        "ff":  "FF",
    },
}


def search_players(query: str, api_key: str) -> list[PlayerSearchResult]:
    if not api_key:
        raise ValueError("No CFBD API key configured.")
    try:
        import cfbd
    except ImportError as exc:
        raise ImportError("cfbd not installed") from exc

    cfg = cfbd.Configuration()
    cfg.access_token = api_key
    client = cfbd.ApiClient(cfg)
    players_api = cfbd.PlayersApi(client)

    try:
        results = players_api.search_players(search_term=query) or []
    except Exception as exc:
        raise RuntimeError(f"API error: {exc}") from exc

    return [
        PlayerSearchResult(
            player_id=r.id or 0,
            name=r.name or f"{r.first_name} {r.last_name}",
            team=r.team or "",
            position=r.position or "",
            jersey=str(r.jersey) if r.jersey else "",
        )
        for r in results[:20]
    ]


def fetch_career(
    player_name: str,
    stat_type: str,
    api_key: str,
    year_start: int = 0,
    year_end: int = 0,
    year_sort: str = "Ascending",
) -> CareerBlock:
    if not api_key:
        raise ValueError("No CFBD API key configured.")
    try:
        import cfbd
    except ImportError as exc:
        raise ImportError("cfbd not installed") from exc

    cfg = cfbd.Configuration()
    cfg.access_token = api_key
    client = cfbd.ApiClient(cfg)
    stats_api = cfbd.StatsApi(client)

    category = _CATEGORY_MAP.get(stat_type, "passing")

    # Fetch a range of seasons — cfbd requires year per call
    current = _current_season()
    start   = year_start if year_start > 0 else max(2000, current - 15)
    end     = year_end   if year_end   > 0 else current

    rows: list[CareerSeasonRow] = []
    seen_years: set[int] = set()

    for yr in range(start, end + 1):
        try:
            raw = stats_api.get_player_season_stats(
                year=yr, category=category
            ) or []
        except Exception:
            continue

        # Filter to this player (by name match)
        name_lower = player_name.lower()
        for s in raw:
            if (s.player or "").lower() != name_lower:
                continue
            if yr in seen_years:
                continue
            seen_years.add(yr)

            stat_vals = _parse_stats(raw, s.player, yr, stat_type)
            rows.append(CareerSeasonRow(
                season=yr,
                team=s.team or "",
                games=0,
                stats=stat_vals,
            ))

    if not rows:
        raise RuntimeError(
            f"No {stat_type} stats found for '{player_name}' "
            f"({start}–{end})."
        )

    rows.sort(
        key=lambda r: r.season,
        reverse=(year_sort == "Descending"),
    )

    return CareerBlock(
        player_id=0,
        player_name=player_name,
        position="",
        stat_type=stat_type,
        as_of=datetime.datetime.now(),
        rows=rows,
    )


def _parse_stats(
    raw_stats, player_name: str, year: int, stat_type: str
) -> dict[str, str]:
    """Collect all stat entries for this player/year into a column dict."""
    name_lower = player_name.lower()
    values: dict[str, float] = {}

    # cfbd returns one row per stat_type, so iterate all and collect
    for s in raw_stats:
        if (s.player or "").lower() != name_lower:
            continue
        stat_name = (s.stat_type or "").lower()
        try:
            val = float(s.stat or 0)
        except (TypeError, ValueError):
            val = 0.0
        values[stat_name] = val

    mapping = _STAT_KEYS.get(stat_type, {})
    result: dict[str, str] = {}
    for raw_key, col_key in mapping.items():
        v = values.get(raw_key)
        if v is None:
            result[col_key] = "—"
        elif col_key in ("AVG", "RATING"):
            result[col_key] = f"{v:.1f}"
        else:
            result[col_key] = str(int(v))

    return result


_cache: dict[tuple, tuple[datetime.datetime, CareerBlock]] = {}


def fetch_career_cached(
    player_name, stat_type, api_key,
    year_start=0, year_end=0, year_sort="Ascending",
    ttl_minutes=15,
) -> CareerBlock:
    key = (player_name, stat_type, year_start, year_end, year_sort)
    if key in _cache:
        ts, block = _cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_career(player_name, stat_type, api_key,
                         year_start, year_end, year_sort)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_career_cache() -> None:
    _cache.clear()
