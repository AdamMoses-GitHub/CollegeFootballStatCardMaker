"""FBS team list fetching and caching."""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TeamInfo:
    name: str           # e.g. "Alabama"
    abbreviation: str   # e.g. "ALA"
    conference: str
    color: str          # primary hex color, e.g. "#9E1B32"
    alt_color: str      # secondary hex color, e.g. "#FFFFFF"


_cache: list[TeamInfo] = []
_cache_ts: datetime.datetime | None = None
_CACHE_TTL_HOURS = 24


def fetch_fbs_teams(api_key: str) -> list[TeamInfo]:
    """Return FBS team list, cached for 24 hours."""
    global _cache, _cache_ts
    now = datetime.datetime.now()
    if _cache and _cache_ts and (now - _cache_ts).total_seconds() < _CACHE_TTL_HOURS * 3600:
        return _cache

    if not api_key:
        return _fallback_teams()

    try:
        import cfbd
    except ImportError:
        return _fallback_teams()

    try:
        configuration = cfbd.Configuration()
        configuration.access_token = api_key
        client = cfbd.ApiClient(configuration)
        teams_api = cfbd.TeamsApi(client)
        raw = teams_api.get_fbs_teams() or []
    except Exception:
        logger.warning("Could not fetch FBS team list; using fallback")
        return _fallback_teams()

    teams = []
    for t in raw:
        teams.append(TeamInfo(
            name=t.school or "",
            abbreviation=t.abbreviation or "",
            conference=t.conference or "",
            color=t.color or "#1a3a5c",
            alt_color=t.alternate_color or "#2c5f8a",
        ))
    return teams


def team_names(api_key: str) -> list[str]:
    """Return sorted list of FBS team names for populating Comboboxes."""
    return [t.name for t in fetch_fbs_teams(api_key)]


def get_team_colors(team_name: str, api_key: str) -> tuple[str, str]:
    """Return (primary_hex, secondary_hex) for a team.

    Falls back to the default navy palette if the team is not found.
    """
    for t in fetch_fbs_teams(api_key):
        if t.name.lower() == team_name.lower():
            primary   = _normalise_color(t.color)     or "#1a3a5c"
            secondary = _normalise_color(t.alt_color)  or _tint(primary, 0.65)
            return primary, secondary
    return "#1a3a5c", "#2c5f8a"


def apply_team_colors(palette: dict, primary: str, secondary: str) -> dict:
    """Return an updated palette dict with team colors applied.

    Args:
        palette: dict of color field name → current hex value.
        primary: team's primary hex color.
        secondary: team's secondary hex color (used for sub-headers/accents).

    Returns a new dict with title/header/accent fields replaced.
    """
    fg = _auto_fg(primary)
    sec_fg = _auto_fg(secondary)
    alt_tint = _tint(primary, 0.08)   # very faint row tint

    updates = {
        "title_bg":      primary,
        "title_fg":      fg,
        "header_bg":     primary,
        "header_fg":     fg,
        "div_header_bg": secondary,
        "div_header_fg": sec_fg,
        "game_box_border": primary,
        "round_label_fg":  primary,
        "row_alt_color": alt_tint,
    }
    result = dict(palette)
    for k, v in updates.items():
        if k in result:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def _normalise_color(color: str | None) -> str:
    """Ensure color is a valid #RRGGBB string, or return empty string."""
    if not color:
        return ""
    c = color.strip()
    if not c.startswith("#"):
        c = "#" + c
    if len(c) == 4:   # #RGB → #RRGGBB
        c = "#" + c[1]*2 + c[2]*2 + c[3]*2
    if len(c) == 7:
        return c.upper()
    return ""


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance (0=black, 1=white)."""
    r, g, b = _hex_to_rgb(hex_color)
    def chan(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _auto_fg(bg_hex: str) -> str:
    """Return '#FFFFFF' or '#111111' depending on background luminance."""
    try:
        lum = _relative_luminance(bg_hex)
        return "#FFFFFF" if lum < 0.35 else "#111111"
    except Exception:
        return "#FFFFFF"


def _tint(hex_color: str, alpha: float) -> str:
    """Blend hex_color onto white at the given alpha (0=white, 1=full color)."""
    try:
        r, g, b = _hex_to_rgb(hex_color)
        tr = round(r * alpha + 255 * (1 - alpha))
        tg = round(g * alpha + 255 * (1 - alpha))
        tb = round(b * alpha + 255 * (1 - alpha))
        return f"#{tr:02X}{tg:02X}{tb:02X}"
    except Exception:
        return "#F0F0F0"


def clear_teams_cache() -> None:
    global _cache, _cache_ts
    _cache = []
    _cache_ts = None


def _fallback_teams() -> list[TeamInfo]:
    """Minimal hardcoded fallback so the UI isn't empty without an API call."""
    names = [
        "Air Force", "Akron", "Alabama", "Appalachian State", "Arizona",
        "Arizona State", "Arkansas", "Arkansas State", "Army", "Auburn",
        "Ball State", "Baylor", "Boise State", "Boston College", "Bowling Green",
        "BYU", "Buffalo", "California", "Central Michigan", "Charlotte",
        "Cincinnati", "Clemson", "Coastal Carolina", "Colorado", "Colorado State",
        "Connecticut", "Duke", "East Carolina", "Eastern Michigan", "FIU",
        "Florida", "Florida Atlantic", "Florida State", "Fresno State",
        "Georgia", "Georgia Southern", "Georgia State", "Georgia Tech",
        "Hawaii", "Houston", "Illinois", "Indiana", "Iowa", "Iowa State",
        "James Madison", "Kansas", "Kansas State", "Kent State", "Kentucky",
        "Liberty", "Louisiana", "Louisiana Tech", "Louisiana-Monroe", "Louisville",
        "LSU", "Marshall", "Maryland", "Memphis", "Miami", "Miami (OH)",
        "Michigan", "Michigan State", "Middle Tennessee", "Minnesota",
        "Mississippi State", "Missouri", "Montana State", "Navy", "Nebraska",
        "Nevada", "New Mexico", "New Mexico State", "North Carolina",
        "North Carolina State", "North Texas", "Northern Illinois", "Northwestern",
        "Notre Dame", "Ohio", "Ohio State", "Oklahoma", "Oklahoma State",
        "Ole Miss", "Oregon", "Penn State", "Pittsburgh", "Purdue",
        "Rice", "Rutgers", "Sam Houston", "San Diego State", "San Jose State",
        "SMU", "South Alabama", "South Carolina", "South Florida", "Southern Miss",
        "Stanford", "Syracuse", "TCU", "Temple", "Tennessee", "Texas",
        "Texas A&M", "Texas State", "Texas Tech", "Toledo", "Troy", "Tulane",
        "Tulsa", "UCF", "UCLA", "UNLV", "USC", "Utah", "Utah State",
        "UTSA", "Vanderbilt", "Virginia", "Virginia Tech", "Wake Forest",
        "Washington", "Washington State", "West Virginia", "Western Kentucky",
        "Western Michigan", "Wisconsin", "Wyoming",
    ]
    return [TeamInfo(n, "", "", "#1a3a5c", "#2c5f8a") for n in sorted(names)]
