"""CFP Playoff bracket data fetching via the cfbd API.

Handles both:
  - Classic 4-team CFP (2014-2023)
  - 12-team CFP (2024+)

Strategy: fetch postseason games, match them to known bowl/CFP game names,
then arrange into bracket slots by round.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


def _current_season() -> int:
    now = datetime.datetime.now()
    return now.year if now.month >= 8 else now.year - 1


def is_12_team_format(season: int) -> bool:
    """The 12-team CFP began with the 2024 season."""
    return season >= 2024


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PlayoffGame:
    game_id: int
    round_name: str       # e.g. "First Round", "Quarterfinal", "Semifinal", "Championship"
    round_num: int        # 1=first round, 2=QF, 3=SF, 4=championship
    slot: int             # position within the round (1-based)
    home_team: str
    away_team: str
    home_seed: Optional[int]
    away_seed: Optional[int]
    home_score: Optional[int]
    away_score: Optional[int]
    venue: str
    neutral_site: bool
    completed: bool
    game_date: Optional[datetime.datetime]
    notes: str            # bowl game name / game label


@dataclass
class PlayoffBracket:
    season: int
    format: str           # "4-team" or "12-team"
    champion: Optional[str]
    as_of: datetime.datetime
    games: list[PlayoffGame] = field(default_factory=list)

    def rounds(self) -> dict[int, list[PlayoffGame]]:
        """Return games grouped by round_num, sorted by slot."""
        result: dict[int, list[PlayoffGame]] = {}
        for g in self.games:
            result.setdefault(g.round_num, []).append(g)
        for rnd in result:
            result[rnd].sort(key=lambda g: g.slot)
        return result


def _classify_round(notes: str, season: int) -> tuple[int, str]:
    """Return (round_num, round_name) based on the actual API notes string."""
    n = (notes or "").lower()
    # These match the exact prefixes returned by the cfbd API
    if "national championship" in n:
        return 4, "Championship"
    if "semifinal" in n:
        return 3, "Semifinal"
    if "quarterfinal" in n:
        return 2, "Quarterfinal"
    if "first round" in n:
        return 1, "First Round"
    # Shouldn't reach here after _filter_cfp_games, but default to semifinal
    return 3, "Semifinal"


# ---------------------------------------------------------------------------
# CFP seed lookup from final regular-season CFP rankings
# ---------------------------------------------------------------------------

def _fetch_cfp_seeds(season: int, api_client) -> dict[str, int]:
    """Return {team_name: seed} from final regular-season CFP rankings."""
    try:
        import cfbd
        rankings_api = cfbd.RankingsApi(api_client)
        weeks = rankings_api.get_rankings(
            year=season,
            season_type=cfbd.SeasonType.REGULAR,
        )
    except Exception:
        logger.warning("Could not fetch CFP seeds for %d", season)
        return {}

    if not weeks:
        return {}

    # Get the last regular-season week
    weeks_sorted = sorted(weeks, key=lambda w: w.week or 0, reverse=True)
    last_week = weeks_sorted[0]

    seeds: dict[str, int] = {}
    for poll in (last_week.polls or []):
        if "playoff" in (poll.poll or "").lower() or "cfp" in (poll.poll or "").lower():
            for rank in (poll.ranks or []):
                if rank.school and rank.rank:
                    seeds[rank.school] = rank.rank
            break

    return seeds


# ---------------------------------------------------------------------------
# Main fetch
# ---------------------------------------------------------------------------

def fetch_playoffs(season: int, api_key: str) -> PlayoffBracket:
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
    games_api = cfbd.GamesApi(api_client)

    try:
        games = games_api.get_games(
            year=effective_season,
            season_type=cfbd.SeasonType.POSTSEASON,
        )
    except Exception as exc:
        logger.exception("cfbd API error fetching postseason games")
        raise RuntimeError(f"API error: {exc}") from exc

    if not games:
        raise RuntimeError(
            f"No postseason game data found for {effective_season}."
        )

    # Fetch seeds
    seeds = _fetch_cfp_seeds(effective_season, api_client)
    fmt = "12-team" if is_12_team_format(effective_season) else "4-team"

    # Filter to CFP games only (exclude non-CFP bowls)
    cfp_games = _filter_cfp_games(games, effective_season)

    if not cfp_games:
        raise RuntimeError(
            f"Could not identify CFP playoff games for {effective_season}. "
            f"Found {len(games)} total postseason games."
        )

    # Build PlayoffGame objects
    playoff_games: list[PlayoffGame] = []
    round_counters: dict[int, int] = {}

    for g in cfp_games:
        notes = g.notes or ""
        round_num, round_name = _classify_round(notes, effective_season)
        round_counters[round_num] = round_counters.get(round_num, 0) + 1
        slot = round_counters[round_num]

        home = g.home_team or ""
        away = g.away_team or ""

        game_date = None
        if g.start_date:
            try:
                game_date = datetime.datetime.fromisoformat(
                    str(g.start_date).replace("Z", "+00:00")
                )
            except Exception:
                pass

        playoff_games.append(PlayoffGame(
            game_id=g.id or 0,
            round_name=round_name,
            round_num=round_num,
            slot=slot,
            home_team=home,
            away_team=away,
            home_seed=seeds.get(home),
            away_seed=seeds.get(away),
            home_score=g.home_points,
            away_score=g.away_points,
            venue=g.venue or "",
            neutral_site=g.neutral_site or False,
            completed=g.completed or False,
            game_date=game_date,
            notes=_short_note(notes, round_name),
        ))

    # Determine champion (winner of championship game)
    champion: Optional[str] = None
    for g in playoff_games:
        if g.round_num == 4 and g.completed:
            if g.home_score is not None and g.away_score is not None:
                champion = g.home_team if g.home_score > g.away_score else g.away_team

    return PlayoffBracket(
        season=effective_season,
        format=fmt,
        champion=champion,
        as_of=datetime.datetime.now(),
        games=sorted(playoff_games, key=lambda g: (g.round_num, g.slot)),
    )


def _short_note(notes: str, round_name: str) -> str:
    """Strip the verbose CFP prefix to leave just the bowl name or game label.

    'College Football Playoff Quarterfinal at the Vrbo Fiesta Bowl' -> 'Vrbo Fiesta Bowl'
    'College Football Playoff First Round Game Presented by Allstate' -> 'First Round'
    'College Football Playoff National Championship Presented by AT&T' -> 'CFP Championship'
    """
    n = notes.strip()
    # National Championship
    if "national championship" in n.lower():
        return "CFP Championship"
    # Semifinal / Quarterfinal / First Round with a named bowl
    for marker in ("at the ", "at ", "- "):
        idx = n.lower().find(marker)
        if idx != -1:
            remainder = n[idx + len(marker):].strip()
            # Strip trailing sponsor tags like "Presented by ..."
            for cut in (" presented by", " rescheduled", " - rescheduled"):
                ci = remainder.lower().find(cut)
                if ci != -1:
                    remainder = remainder[:ci].strip()
            if remainder:
                return remainder.rstrip(" -")
    # Fallback: just return the round name
    return round_name


def _filter_cfp_games(games, season: int):
    """Keep only games that are part of the CFP bracket."""
    cfp = [g for g in games
           if "college football playoff" in (g.notes or "").lower()]

    if not cfp:
        raise RuntimeError(
            f"No College Football Playoff games found in {season} postseason data. "
            f"({len(games)} total postseason games returned.)"
        )

    return cfp


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_cache: dict[tuple, tuple[datetime.datetime, PlayoffBracket]] = {}


def fetch_playoffs_cached(
    season: int,
    api_key: str,
    ttl_minutes: int = 15,
) -> PlayoffBracket:
    key = (season,)
    if key in _cache:
        ts, block = _cache[key]
        if (datetime.datetime.now() - ts).total_seconds() < ttl_minutes * 60:
            return block
    block = fetch_playoffs(season, api_key)
    _cache[key] = (datetime.datetime.now(), block)
    return block


def clear_playoffs_cache() -> None:
    _cache.clear()
