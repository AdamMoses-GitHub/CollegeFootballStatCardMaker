# CFB Stat Card Maker

*Because screenshotting a browser tab and cropping it in Paint is not a workflow.*

![Version](https://img.shields.io/badge/version-1.0.0-blue) ![Python](https://img.shields.io/badge/python-3.10%2B-yellow) ![License](https://img.shields.io/badge/license-MIT-green)

![App Screenshot](INSERT_IMAGE_URL_HERE)

---

## About

Manually assembling college football stat graphics means bouncing between ESPN, Sports Reference, and whatever poll site still loads — then either hand-typing numbers into a template or screenshotting a blurry table. It's tedious, inconsistent, and looks like it.

**CFB Stat Card Maker** pulls live data directly from the [College Football Data API](https://collegefootballdata.com) and renders clean, exportable stat cards as print-quality PNG or JPEG images — all from a desktop GUI, no design skills required.

**GitHub:** [https://github.com/AdamMoses-GitHub/CollegeFootballStatCardMaker](https://github.com/AdamMoses-GitHub/CollegeFootballStatCardMaker)

---

## What It Does

### The Main Features

- **Conference Standings** — standings table for any FBS conference with W/L, PCT, conference record, and current streak
- **AP / Coaches / CFP Rankings** — poll rankings card for any week with rank badges and first-place vote counts
- **CFP Playoff Bracket** — full bracket card with seeds, scores, and winner highlighting; supports both 12-team and legacy formats
- **Team Season Record** — game-by-game results card for any team/season with W/L color coding and kickoff times
- **Team Schedule** — upcoming full-season schedule with dates, opponents, home/away, and kickoff times
- **Team Roster** — full roster grouped by position with jersey, class year, and hometown columns
- **Head-to-Head Matchup** — side-by-side team stat comparison (standard or advanced EPA metrics)
- **Player Career Stats** — season-by-season career table for passing, rushing, receiving, or defense

### The Nerdy Stuff

- Renders cards with **Pillow** at configurable DPI (default 300) — vector-sharp at any print size
- **ESPN CDN logo cache** — team and conference logos fetched once and stored on disk to avoid redundant requests
- **In-memory data cache** with configurable TTL (default 15 min) — rapid re-renders without hammering the API
- **Rotating log files** (5 × 1 MB) written to the working directory for easy debugging
- All card dimensions specified in **inches × DPI**, so "6×4 at 300 DPI" means exactly 1800×1200 px

---

## Quick Start (TL;DR)

See [INSTALL_AND_USAGE.md](INSTALL_AND_USAGE.md) for the full guide.

```bash
git clone https://github.com/AdamMoses-GitHub/CollegeFootballStatCardMaker.git
cd CollegeFootballStatCardMaker
pip install -r requirements.txt
python run.py
```

A free API key from [collegefootballdata.com](https://collegefootballdata.com) is required. Enter it in the **Settings** tab on first launch.

---

## Tech Stack

| Component | Purpose | Why This One |
|---|---|---|
| [cfbd](https://pypi.org/project/cfbd/) | College football data (standings, rankings, rosters, stats) | Official Python client for the CFBD REST API |
| [Pillow](https://python-pillow.org/) | Image generation and export | De-facto standard for Python image manipulation; handles fonts, drawing, and JPEG/PNG natively |
| [requests](https://requests.readthedocs.io/) | ESPN CDN logo downloads | Simple, battle-tested HTTP client |
| [tkinter](https://docs.python.org/3/library/tkinter.html) | Desktop GUI | Ships with Python — zero extra install for the UI layer |
| Roboto (bundled) | Card typography | Clean, legible at small sizes; bundled so cards look the same on every machine |

---

## License

MIT — see [LICENSE](LICENSE).

## Contributing

PRs welcome. Open an issue first for anything larger than a bug fix.

---

<sub>college football stats, CFB stat cards, college football data, standings card generator, AP poll rankings card, CFP bracket card, team roster card, player career stats, football stat graphics, CFBD API, Pillow image generation, Python desktop app, tkinter GUI, college football schedule, team record card, matchup comparison, stat card maker, football card generator, college football visualizations, NCAA football stats</sub>
