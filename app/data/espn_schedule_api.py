"""ESPN unofficial schedule API — used as a fallback time source.

When cfbd has start_time_tbd=True for upcoming games, this module queries
the public ESPN schedule endpoint to fill in announced kickoff times.

Endpoint:
  https://site.api.espn.com/apis/site/v2/sports/football/college-football/
      teams/{espn_id}/schedule?season={year}&seasontype={type}

The ``timeValid`` field in each competition tells us whether the time is real.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_ESPN_SCHEDULE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/"
    "college-football/teams/{espn_id}/schedule"
    "?season={season}&seasontype={stype}"
)

# In-memory cache: (espn_id, season) -> (fetched_at, {date_key: (utc_dt, time_valid, team_slugs)})
_mem: dict[tuple, tuple[datetime.datetime, dict]] = {}
_TTL_SECONDS = 4 * 3600  # refresh at most once every 4 hours


def _cache_path(espn_id: int, season: int, working_dir: str) -> str:
    return os.path.join(working_dir, "espn_time_cache", f"{espn_id}_{season}.json")


def _load_disk_cache(espn_id: int, season: int, working_dir: str) -> Optional[dict]:
    path = _cache_path(espn_id, season, working_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        # Check TTL
        fetched_at = datetime.datetime.fromisoformat(raw["fetched_at"])
        age = (datetime.datetime.now() - fetched_at).total_seconds()
        if age > _TTL_SECONDS:
            return None
        # Deserialise. Older cache files lack opponent metadata and are unsafe
        # for date-only fallback matching until the cache is refreshed.
        result: dict[str, tuple[Optional[datetime.datetime], bool, set[str]]] = {}
        for date_key, entry in raw["data"].items():
            dt_str, tv, *team_slugs = entry
            dt = datetime.datetime.fromisoformat(dt_str) if dt_str else None
            result[date_key] = (
                dt, bool(tv), set(team_slugs[0]) if team_slugs else {"__legacy_cache__"}
            )
        return result
    except Exception:
        return None


def _save_disk_cache(
    espn_id: int,
    season: int,
    working_dir: str,
    data: dict,
) -> None:
    path = _cache_path(espn_id, season, working_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    serialisable = {
        "fetched_at": datetime.datetime.now().isoformat(),
        "data": {
            k: (v[0].isoformat() if v[0] else None, v[1], sorted(v[2]))
            for k, v in data.items()
        },
    }
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(serialisable, fh, indent=2)
    except Exception:
        logger.debug("Could not write ESPN time cache for %s/%s", espn_id, season)


def _date_key(utc_dt: datetime.datetime) -> str:
    """Return the ESPN event's US Eastern calendar date."""
    from zoneinfo import ZoneInfo
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
    return utc_dt.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")


def _fetch_season_type(espn_id: int, season: int, stype: int) -> list[dict]:
    url = _ESPN_SCHEDULE_URL.format(espn_id=espn_id, season=season, stype=stype)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("events", [])
    except Exception:
        logger.debug("ESPN schedule fetch failed for espn_id=%s season=%s stype=%s",
                     espn_id, season, stype)
        return []


def fetch_espn_schedule(
    espn_id: int,
    season: int,
    working_dir: str,
) -> dict[str, tuple[Optional[datetime.datetime], bool, set[str]]]:
    """Return a dict mapping US-date-key -> (utc_datetime | None, time_valid, team_slugs).

    Fetches both regular season (seasontype=2) and postseason (seasontype=3).
    Results are cached on disk (4 h TTL) and in memory for the process lifetime.
    """
    mem_key = (espn_id, season)
    if mem_key in _mem:
        fetched_at, data = _mem[mem_key]
        age = (datetime.datetime.now() - fetched_at).total_seconds()
        if age < _TTL_SECONDS:
            return data

    # Try disk cache
    data = _load_disk_cache(espn_id, season, working_dir)
    if data is not None:
        _mem[mem_key] = (datetime.datetime.now(), data)
        return data

    # Fetch from ESPN
    data = {}
    from app.data.logo_cache import slugify
    for stype in (2, 3):
        for event in _fetch_season_type(espn_id, season, stype):
            comps = event.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            date_str: str = comp.get("date") or event.get("date", "")
            time_valid: bool = bool(comp.get("timeValid", False))
            if not date_str:
                continue
            try:
                utc_dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if utc_dt.tzinfo is None:
                    utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
                key = _date_key(utc_dt)
                team_slugs = set()
                for competitor in comp.get("competitors", []):
                    team = competitor.get("team", {})
                    for field in ("displayName", "shortDisplayName", "name", "location"):
                        value = team.get(field)
                        if value:
                            team_slugs.add(slugify(value))
                # Prefer time_valid=True entries; don't overwrite a valid entry
                if key not in data or time_valid:
                    data[key] = (utc_dt, time_valid, team_slugs)
            except Exception:
                continue

    if data:
        _save_disk_cache(espn_id, season, working_dir, data)
        _mem[mem_key] = (datetime.datetime.now(), data)
    else:
        logger.debug("No ESPN schedule data for espn_id=%s season=%s", espn_id, season)

    return data
