# CFB Stat Card Maker — Install & Usage Guide

## Feature Recap

- Generate print-quality (300 DPI) college football stat cards as PNG or JPEG
- Pull live data from the College Football Data API (standings, rankings, rosters, schedules, stats)
- Browse 8 card types via a tabbed desktop GUI: Standings, Rankings, Playoffs Bracket, Team Record, Team Schedule, Team Roster, Matchup, and Player Career
- Customize card dimensions (inches × DPI), background color, and per-card display options
- Team and conference logos auto-fetched from ESPN CDN and cached on disk
- All exports saved to a configurable working directory (default: `~/CFBStatCards/`)

---

## Prerequisites

- Python 3.10 or higher
- A free API key from [collegefootballdata.com](https://collegefootballdata.com) — register, log in, and copy the key from your profile page

---

## Installation

### Method A — Conda (Recommended)

Creates an isolated environment with a locked Python version, avoiding dependency conflicts with other projects.

```bash
git clone https://github.com/AdamMoses-GitHub/CollegeFootballStatCardMaker.git
cd CollegeFootballStatCardMaker

conda create -p .conda python=3.11 -y
conda activate ./.conda

pip install -r requirements.txt
```

### Method B — pip + venv (Quick)

```bash
git clone https://github.com/AdamMoses-GitHub/CollegeFootballStatCardMaker.git
cd CollegeFootballStatCardMaker

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Running the App

```bash
python run.py
```

The GUI opens. On first launch, go to the **Settings** tab and paste your CFBD API key. Settings are saved automatically on exit to `~/CFBStatCards/settings.json`.

---

## Usage Workflows

### 1. Standings Card

**Scenario:** You want a clean SEC standings card to post after Week 10.

1. Click the **Standings** tab.
2. Select the **Conference** (e.g., `SEC`) and **Season** year.
3. Toggle **Show Logos** and choose **Column Mode** (`standard` or `extended` — extended adds conference record, PF, PA, and streak).
4. Adjust card width/height in inches if needed (extended columns display better at 7.5"+ wide).
5. Click **Generate** — a preview appears on the right.
6. Click **Export** to save the image to your output directory.

**Example:** Set conference to `Big Ten`, season to `2024`, column mode to `extended` at 8×5 inches → one card with every team's full record and current win/loss streak.

---

### 2. Rankings Card

**Scenario:** The CFP rankings dropped on Tuesday night and you want a shareable graphic immediately.

1. Click the **Rankings** tab.
2. Choose **Poll** (`AP Top 25`, `Coaches Poll`, `CFP Rankings`, or `AFCA Coaches`).
3. Select the **Season** and **Week**.
4. Enable **Show Rank Badges** — gold/silver/bronze badges appear on the top 3 teams.
5. Click **Generate**, then **Export**.

**Example:** Set poll to `CFP Rankings`, week to `12`, enable rank badges → a 25-row card with seed badges and first-place vote counts for every ranked team.

---

### 3. Matchup Card

**Scenario:** Two teams are playing Saturday and you want a head-to-head stat breakdown.

1. Click the **Matchup** tab.
2. Select **Team A** and **Team B** from the dropdowns (or type to search).
3. Choose **Season** and **Stat Set** (`Standard` for PPG/yards/turnovers, `Advanced` for EPA/play, success rate, explosiveness).
4. Optionally enable **Use Team Colors** — column headers adopt each school's primary color.
5. Click **Generate** → the card shows both teams side-by-side with better values highlighted in green.
6. **Export**.

**Example:** Alabama vs. Georgia, 2024, Advanced stats → EPA/play and success rate comparison with team-colored headers, winner column highlighted.

---

### 4. Player Career Card

**Scenario:** A receiver just broke the school's career receiving yards record and you need a career stats table.

1. Click the **Player Career** tab.
2. Type the player's name in the search box and click **Search**.
3. Select the correct player from the results list (name, team, position shown).
4. Choose **Stat Type** (`Passing`, `Rushing`, `Receiving`, or `Defense`).
5. Toggle **Highlight Most Recent Season** — the current/last season row is highlighted in yellow.
6. Click **Generate**, then **Export**.

**Example:** Search `Tetairoa McMillan`, select Receiving → a season-by-season table with REC, YDS, AVG, and TD, most recent season highlighted.

---

### 5. Playoff Bracket Card

**Scenario:** You want a CFP bracket card once the first-round results are in.

1. Click the **Playoffs** tab.
2. Select the **Season**.
3. Toggle **Show Seeds**, **Show Scores**, and **Show Logos** as desired.
4. Click **Generate** — the bracket renders with winners highlighted in green and eliminated teams grayed out.
5. **Export**.

**Example:** Season `2024` → 12-team bracket with all first-round games filled in, seeds, and ESPN logos.

---

## Project Structure

```
CollegeFootballStatCardMaker/
├── run.py                     # Entry point — launches the GUI
├── requirements.txt           # Python dependencies
│
├── app/
│   ├── main.py                # App init: settings load, logging, window launch
│   ├── settings.py            # Settings dataclass + JSON persistence
│   │
│   ├── cards/                 # Image renderers — one file per card type
│   │   ├── base_card.py       # CardConfig base (dimensions, DPI, canvas)
│   │   ├── standings_card.py
│   │   ├── rankings_card.py
│   │   ├── playoffs_card.py
│   │   ├── game_record_card.py
│   │   ├── matchup_card.py
│   │   ├── roster_card.py
│   │   └── career_card.py
│   │
│   ├── data/                  # API fetch + data models — one file per card type
│   │   ├── cfb_api.py         # Standings data (cfbd client)
│   │   ├── rankings_api.py
│   │   ├── playoffs_api.py
│   │   ├── game_record_api.py
│   │   ├── espn_schedule_api.py
│   │   ├── roster_api.py
│   │   ├── matchup_api.py
│   │   ├── career_api.py
│   │   ├── teams_api.py       # Team list / conference lookup
│   │   └── logo_cache.py      # ESPN CDN logo downloader + disk cache
│   │
│   ├── ui/                    # tkinter tabs — one file per card type
│   │   ├── main_window.py     # Root window + tab container
│   │   ├── standings_tab.py
│   │   ├── rankings_tab.py
│   │   ├── playoffs_tab.py
│   │   ├── game_record_tab.py
│   │   ├── schedule_tab.py
│   │   ├── roster_tab.py
│   │   ├── matchup_tab.py
│   │   ├── career_tab.py
│   │   └── settings_tab.py
│   │
│   └── utils/
│       ├── font_manager.py    # Roboto font loader with LRU cache
│       └── image_utils.py     # Shared image helpers
│
└── assets/
    └── fonts/
        └── Roboto/            # Bundled Roboto & Roboto Condensed TTF files
```

### Key Directories

| Directory | What's in it |
|---|---|
| `app/cards/` | Pure rendering logic. Each renderer takes a data block + config and returns a `PIL.Image`. No UI or API calls here. |
| `app/data/` | API fetch functions and data model dataclasses. Each file pairs with the matching card renderer. |
| `app/ui/` | tkinter `Frame` subclasses — one per tab. Owns controls, preview thumbnail, and export wiring. |
| `app/utils/` | Shared utilities: font loading (LRU-cached) and image helpers used across renderers. |
| `assets/fonts/Roboto/` | Bundled font files so card typography is consistent across all machines. |

---

## Settings Reference

All settings are accessible from the **Settings** tab and persisted to `~/CFBStatCards/settings.json`.

| Setting | Default | Description |
|---|---|---|
| CFBD API Key | *(empty)* | Required. Get yours at [collegefootballdata.com](https://collegefootballdata.com) |
| Working Directory | `~/CFBStatCards` | Where exports and logs are saved |
| Card Width / Height | 6.0 × 4.0 in | Global default card size |
| DPI | 300 | Output resolution |
| Background Color | `#FFFFFF` | Default card background |
| Display Timezone | `ET` | Kickoff time display (ET / CT / MT / PT / AKT / HT / UTC) |
| Data Cache TTL | 15 min | How long fetched API data is reused before re-fetching |

---

## Requirements

| Package | Version | Purpose |
|---|---|---|
| `cfbd` | ≥ 4.0 | College Football Data API Python client |
| `Pillow` | ≥ 10.0 | Image generation, font rendering, PNG/JPEG export |
| `requests` | ≥ 2.31 | ESPN CDN logo downloads |
| Python | ≥ 3.10 | f-string match-case and `__future__` annotations used throughout |
