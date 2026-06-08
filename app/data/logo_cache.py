"""ESPN CDN logo downloader with disk cache.

Team logos: https://a.espncdn.com/i/teamlogos/ncaa/500/{espn_id}.png
Conference logos: https://a.espncdn.com/i/teamlogos/ncaa_conf/500/{conf_id}.png
"""
from __future__ import annotations

import logging
import os
import re
import unicodedata
from typing import Optional

import requests
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ESPN numeric ID map  (team slug → ESPN numeric ID)
# ---------------------------------------------------------------------------
TEAM_ESPN_ID_MAP: dict[str, int] = {
    # SEC
    "alabama":          333,
    "arkansas":         8,
    "auburn":           2,
    "florida":          57,
    "georgia":          61,
    "kentucky":         96,
    "lsu":              99,
    "mississippi_state": 344,
    "missouri":         142,
    "ole_miss":         145,
    "south_carolina":   2579,
    "tennessee":        2633,
    "texas_am":         245,
    "vanderbilt":       238,
    "texas":            251,
    "oklahoma":         201,
    # Big Ten
    "illinois":         356,
    "indiana":          84,
    "iowa":             2294,
    "maryland":         120,
    "michigan":         130,
    "michigan_state":   127,
    "minnesota":        135,
    "nebraska":         158,
    "northwestern":     77,
    "ohio_state":       194,
    "penn_state":       213,
    "purdue":           2755,
    "rutgers":          164,
    "wisconsin":        275,
    "ucla":             26,
    "usc":              30,
    "oregon":           2483,
    "washington":       264,
    # Big 12
    "baylor":           239,
    "byu":              252,
    "cincinnati":       2132,
    "houston":          248,
    "iowa_state":       66,
    "kansas":           2305,
    "kansas_state":     2306,
    "oklahoma_state":   197,
    "tcu":              2628,
    "texas_tech":       2641,
    "ucf":              2116,
    "west_virginia":    277,
    "arizona":          12,
    "arizona_state":    9,
    "colorado":         38,
    "utah":             254,
    # ACC
    "boston_college":   103,
    "clemson":          228,
    "duke":             150,
    "florida_state":    52,
    "georgia_tech":     59,
    "louisville":       97,
    "miami":            2390,
    "nc_state":         152,
    "north_carolina":   153,
    "notre_dame":       87,
    "pittsburgh":       221,
    "stanford":         24,
    "syracuse":         183,
    "virginia":         258,
    "virginia_tech":    259,
    "wake_forest":      154,
    "cal":              25,
    "smu":              2567,
    # Mountain West
    "air_force":        2005,
    "boise_state":      68,
    "colorado_state":   36,
    "fresno_state":     278,
    "hawaii":           62,
    "nevada":           2440,
    "new_mexico":       167,
    "san_diego_state":  21,
    "san_jose_state":   23,
    "unlv":             2439,
    "utah_state":       328,
    "wyoming":          2751,
    # American Athletic
    "east_carolina":    151,
    "memphis":          235,
    "navy":             2426,
    "south_florida":    58,
    "temple":           218,
    "tulane":           2655,
    "tulsa":            202,
    "army":             349,
    "charlotte":        2429,
    "florida_atlantic": 2226,
    "north_texas":      249,
    "rice":             242,
    "utsa":             2573,
    "wku":              98,
    # Sun Belt
    "appalachian_state": 2026,
    "arkansas_state":   2032,
    "coastal_carolina": 324,
    "georgia_southern": 290,
    "georgia_state":    2247,
    "james_madison":    256,
    "la_monroe":        2433,
    "louisiana":        309,
    "marshall":         276,
    "old_dominion":     295,
    "south_alabama":    6,
    "southern_miss":    235,
    "texas_state":      326,
    "troy":             2653,
    # MAC
    "akron":            2006,
    "ball_state":       2050,
    "bowling_green":    189,
    "buffalo":          2084,
    "central_michigan": 2117,
    "eastern_michigan": 2199,
    "kent_state":       2309,
    "miami_oh":         193,
    "northern_illinois": 2459,
    "ohio":             195,
    "toledo":           2649,
    "western_michigan": 2711,
    # Conference USA
    "fiu":              2229,
    "kennesaw_state":   338,
    "liberty":          2335,
    "louisiana_tech":   2348,
    "middle_tennessee": 2393,
    "new_mexico_state": 166,
    "sam_houston":      2534,
    "ut_arlington":     2568,
    "utep":             2638,
    # Independents
    "connecticut":      41,
    "massachusetts":    113,
    "new_mexico_state_ind": 166,
    "sam_houston_ind":  2534,
    # ---------------------------------------------------------------------------
    # Aliases for alternate names returned by the cfbd API
    # ---------------------------------------------------------------------------
    # SEC
    "texas_am":         245,    # existing map key (hand-keyed)
    "texas_andm":       245,    # slugify("Texas A&M") variant
    "texas_aandm":      245,    # slugify("Texas A&M") actual output
    # Big Ten
    "oregon_state":     258,
    "washington_state": 265,
    # ACC
    "california":       25,     # cfbd returns "California" (Cal)
    # Mountain West
    "san_jose_state":   23,     # cfbd returns "San José State"
    "hawaii_w":         62,     # cfbd returns "Hawai'i"
    "hawaii":           62,     # slugify("Hawai'i") = "hawaii"
    # American Athletic
    "uconn":            41,     # cfbd returns "UConn"
    # Sun Belt
    "app_state":        2026,   # cfbd returns "App State" (Appalachian State)
    "ul_monroe":        2433,   # cfbd returns "UL Monroe"
    # MAC
    "western_kentucky": 98,
    # Conference USA
    "florida_international": 2229,  # cfbd returns "Florida International"
    "uab":              5765,
    # FCS schools that occasionally appear
    "north_dakota_state": 2449,
    "delaware":         56,
    "jacksonville_state": 55,
    "sacramento_state": 2377,
    "missouri_state":   2623,
}

_CONF_LOGO_URL: dict[str, str] = {
    "SEC":           "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/8.png",
    "Big Ten":       "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/4.png",
    "Big 12":        "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/12.png",
    "ACC":           "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/1.png",
    "Pac-12":        "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/9.png",
    "American Athletic": "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/151.png",
    "Mountain West": "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/17.png",
    "Sun Belt":      "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/37.png",
    "MAC":           "https://a.espncdn.com/i/teamlogos/ncaa_conf/500/5.png",
    # Conference USA logo is no longer available on ESPN CDN
}

_ESPN_BASE = "https://a.espncdn.com/i/teamlogos/ncaa/500/{espn_id}.png"

# In-memory PIL image cache to avoid re-opening the same file repeatedly
_mem_cache: dict[str, Image.Image] = {}


def slugify(name: str) -> str:
    """Normalise a team name to a lowercase underscore slug for map lookups.

    Handles Unicode accents (é→e), apostrophes, ampersands, and punctuation.
    """
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    s = ascii_str.replace("&", "and").replace("'", "")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _logo_path(abbrev: str, working_dir: str) -> str:
    return os.path.join(working_dir, "logos", f"{abbrev}.png")


def _download(url: str, dest_path: str) -> bool:
    """Download url to dest_path.  Returns True on success."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as fh:
            fh.write(resp.content)
        return True
    except Exception:
        logger.debug("Failed to download logo from %s", url)
        return False


def get_logo(abbrev: str, size_px: int, working_dir: str) -> Optional[Image.Image]:
    """Return a PIL Image of a team logo at size_px × size_px.

    Downloads from ESPN CDN on first use and caches to disk.
    Returns None on any failure.
    """
    # Normalise the abbrev to a consistent slug
    slug = slugify(abbrev)

    cache_key = f"{slug}_{size_px}"
    if cache_key in _mem_cache:
        return _mem_cache[cache_key]

    path = _logo_path(slug, working_dir)

    # Download if not cached on disk
    if not os.path.exists(path):
        espn_id = TEAM_ESPN_ID_MAP.get(slug)
        if espn_id is None:
            logger.debug("No ESPN ID for team slug: %s (from %r)", slug, abbrev)
            return None
        url = _ESPN_BASE.format(espn_id=espn_id)
        if not _download(url, path):
            return None

    # Open from disk
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        logger.warning("Corrupt logo cache for %s — removing", slug)
        try:
            os.remove(path)
        except OSError:
            pass
        return None

    img = img.resize((size_px, size_px), Image.LANCZOS)
    _mem_cache[cache_key] = img
    return img


def get_conference_logo(
    conference: str, size_px: int, working_dir: str
) -> Optional[Image.Image]:
    """Return a PIL Image of a conference logo.  Same cache mechanics as get_logo."""
    safe = conference.lower().replace(" ", "_").replace("-", "_")
    cache_key = f"conf_{safe}_{size_px}"
    if cache_key in _mem_cache:
        return _mem_cache[cache_key]

    path = os.path.join(working_dir, "logos", f"conf_{safe}.png")

    if not os.path.exists(path):
        url = _CONF_LOGO_URL.get(conference)
        if url is None:
            return None
        if not _download(url, path):
            return None

    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        logger.warning("Corrupt conference logo cache for %s — removing", conference)
        try:
            os.remove(path)
        except OSError:
            pass
        return None

    img = img.resize((size_px, size_px), Image.LANCZOS)
    _mem_cache[cache_key] = img
    return img


def clear_logo_memory_cache() -> None:
    _mem_cache.clear()
