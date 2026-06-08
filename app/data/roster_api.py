"""Roster data fetching via cfbd."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

POSITION_GROUPS: dict[str, list[str]] = {
    "QB":  ["QB"],
    "RB":  ["RB", "FB"],
    "WR":  ["WR"],
    "TE":  ["TE"],
    "OL":  ["OL", "OT", "OG", "C", "G", "T"],
    "DL":  ["DL", "DE", "DT", "NT"],
    "LB":  ["LB", "ILB", "OLB", "MLB"],
    "DB":  ["DB", "CB", "S", "SS", "FS"],
    "ST":  ["K", "P", "LS", "KR", "PR"],
    "ATH": ["ATH"],
}

GROUP_ORDER = ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "ST", "ATH"]

YEAR_MAP = {1: "Fr", 2: "So", 3: "Jr", 4: "Sr", 5: "Gr"}


def _pos_group(pos: str) -> str:
    pos = (pos or "").upper()
    for group, positions in POSITION_GROUPS.items():
        if pos in positions:
            return group
    return "ATH"


def _fmt_height(inches: int | None) -> str:
    if not inches:
        return ""
    feet, rem = divmod(inches, 12)
    return f"{feet}'{rem}\""


def _current_season() -> int:
    now = datetime.datetime.now()
    return now.year if now.month >= 8 else now.year - 1


@dataclass
class RosterPlayer:
    jersey: str
    first_name: str
    last_name: str
    position: str
    pos_group: str
    year_num: int | None
    year_str: str
    height_str: str
    weight: int | None
    hometown: str


@dataclass
class RosterBlock:
    team: str
    season: int
    as_of: datetime.datetime
    players: list[RosterPlayer] = field(default_factory=list)

    def grouped(self) -> dict[str, list[RosterPlayer]]:
        groups: dict[str, list[RosterPlayer]] = {}
        for p in self.players:
            groups.setdefault(p.pos_group, []).append(p)
        return {g: groups[g] for g in GROUP_ORDER if g in groups}


def fetch_roster(team: str, season: int, api_key: str) -> RosterBlock:
    if not api_key:
        raise ValueError("No CFBD API key configured.")

    try:
        import cfbd
    except ImportError as exc:
        raise ImportError("The 'cfbd' package is not installed.") from exc

    effective_season = season if season != 0 else _current_season()

    configuration = cfbd.Configuration()
    configuration.access_token = api_key
    api_client = cfbd.ApiClient(configuration)
    teams_api = cfbd.TeamsApi(api_client)

    try:
        raw = teams_api.get_roster(team=team, year=effective_season) or []
    except Exception as exc:
        logger.exception("cfbd API error fetching roster")
        raise RuntimeError(f"API error: {exc}") from exc

    if not raw:
        raise RuntimeError(f"No roster data found for {team} in {effective_season}.")

    players = []
    for p in raw:
        hometown_parts = [x for x in [p.home_city, p.home_state] if x]
        hometown = ", ".join(hometown_parts)
        yr = p.year
        players.append(RosterPlayer(
            jersey=str(p.jersey) if p.jersey is not None else "",
            first_name=p.first_name or "",
            last_name=p.last_name or "",
            position=(p.position or "").upper(),
            pos_group=_pos_group(p.position),
            year_num=yr,
            year_str=YEAR_MAP.get(yr, str(yr)) if yr else "",
            height_str=_fmt_height(p.height),
            weight=p.weight,
            hometown=hometown,
        ))

    # Sort within each group by jersey number then last name
    def sort_key(p: RosterPlayer):
        try:
            jn = int(p.jersey)
        except (ValueError, TypeError):
            jn = 999
        return (jn, p.last_name)

    players.sort(key=sort_key)

    return RosterBlock(
        team=team,
        season=effective_season,
        as_of=datetime.datetime.now(),
        players=players,
    )


_cache: dict[tuple, tuple[datetime.datetime, RosterBlock]] = {}


def fetch_roster_cached(
    team: str, season: int, api_key: str, ttl_minutes: int = 15
) -> RosterBlock:
    key = (team, season)
    if key in _cache:
        ts, block = _cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_roster(team, season, api_key)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_roster_cache() -> None:
    _cache.clear()
