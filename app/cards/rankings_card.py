"""Rankings card renderer for CFB Stat Card Maker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from app.cards.base_card import CardConfig
from app.data.rankings_api import RankingsBlock, RankingEntry
from app.utils.font_manager import get_font

# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

STANDARD_COLS  = ["RANK", "TEAM", "CONF", "RECORD", "POINTS"]
EXTENDED_COLS  = ["RANK", "TEAM", "CONF", "RECORD", "POINTS", "1ST"]

COL_EXPLAINERS: dict[str, str] = {
    "RANK":   "Poll Ranking",
    "CONF":   "Conference",
    "RECORD": "W-L Record",
    "POINTS": "Poll Points",
    "1ST":    "First-Place Votes",
}

_COL_FRACS_STANDARD: dict[str, float] = {
    "RANK":   0.09,
    "CONF":   0.18,
    "RECORD": 0.13,
    "POINTS": 0.13,
}
_COL_FRACS_EXTENDED: dict[str, float] = {
    "RANK":   0.08,
    "CONF":   0.16,
    "RECORD": 0.12,
    "POINTS": 0.12,
    "1ST":    0.09,
}

_EXTENDED_THRESHOLD = 7.5
_MIN_ROW_H = 18
_MAX_ROWS   = 25

# Rank badge colors: gold / silver / bronze
_BADGE_COLORS = {1: "#D4AF37", 2: "#C0C0C0", 3: "#B87333"}
_BADGE_OUTLINE = {1: "#9A7B1A", 2: "#808080", 3: "#7A4A20"}


def suggest_column_mode(width_in: float) -> str:
    return "extended" if width_in >= _EXTENDED_THRESHOLD else "standard"


# ---------------------------------------------------------------------------
# Card config
# ---------------------------------------------------------------------------

@dataclass
class RankingsCardConfig(CardConfig):
    show_logos: bool         = True
    show_timestamp: bool     = False
    show_col_explainers: bool= False
    show_rank_badges: bool   = True
    column_mode: str         = "auto"
    season: int              = 0
    week: int                = 0
    poll: str                = "AP Top 25"
    season_type: str         = "regular"
    max_rows: int            = 0

    header_bg: str     = "#1a3a5c"
    header_fg: str     = "#FFFFFF"
    title_bg: str      = "#1a3a5c"
    title_fg: str      = "#FFFFFF"
    row_alt_color: str = "#EEF2F7"
    row_color: str     = "#FFFFFF"
    divider_color: str = "#CCCCCC"
    text_color: str    = "#111111"
    footer_color: str  = "#888888"


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class RankingsCardRenderer:

    TITLE_H_PCT  = 0.10
    HEADER_H_PCT = 0.065
    FOOTER_H_PCT = 0.08
    CELL_PAD_X   = 8

    def render(
        self,
        block: RankingsBlock,
        config: RankingsCardConfig,
        working_dir: str,
    ) -> Image.Image:
        cols    = self._resolve_cols(config)
        entries = self._cap_entries(block.entries, config)

        W = config.width_px
        H = config.height_px

        title_h    = round(H * self.TITLE_H_PCT)
        header_h   = round(H * self.HEADER_H_PCT)
        has_footer = config.show_timestamp or config.show_col_explainers
        footer_h   = round(H * self.FOOTER_H_PCT) if has_footer else 0
        data_area  = H - title_h - header_h - footer_h

        n_rows = max(len(entries), 1)
        row_h  = data_area // n_rows
        if row_h < _MIN_ROW_H:
            n_rows  = max(1, data_area // _MIN_ROW_H)
            entries = entries[:n_rows]
            row_h   = data_area // n_rows

        col_widths = self._calc_col_widths(cols, W)

        img  = config.new_canvas()
        draw = ImageDraw.Draw(img)

        self._draw_title(draw, img, block, config, W, title_h, working_dir)
        y = title_h

        self._draw_col_header(draw, cols, col_widths, config, y, header_h, W)
        y += header_h

        for i, entry in enumerate(entries):
            row_bg = config.row_color if i % 2 == 0 else config.row_alt_color
            draw.rectangle([0, y, W - 1, y + row_h - 1], fill=row_bg)
            self._draw_row(draw, img, entry, cols, col_widths, config, y, row_h, working_dir)
            y += row_h

        if has_footer:
            fy = H - footer_h
            draw.line([(0, fy), (W - 1, fy)], fill=config.divider_color, width=1)
            self._draw_footer(draw, block, config, fy, footer_h, W, cols)

        return img

    # ------------------------------------------------------------------

    def _resolve_cols(self, config: RankingsCardConfig) -> list[str]:
        mode = config.column_mode
        if mode == "auto":
            mode = suggest_column_mode(config.width_in)
        return EXTENDED_COLS if mode == "extended" else STANDARD_COLS

    def _cap_entries(self, entries: list[RankingEntry], config: RankingsCardConfig) -> list[RankingEntry]:
        cap = config.max_rows if config.max_rows > 0 else _MAX_ROWS
        return entries[:cap]

    def _calc_col_widths(self, cols: list[str], total_w: int) -> list[int]:
        fracs = _COL_FRACS_EXTENDED if len(cols) > 5 else _COL_FRACS_STANDARD
        non_team: dict[str, int] = {}
        used = 0
        for col in cols:
            if col == "TEAM":
                continue
            w = round(total_w * fracs.get(col, 0.10))
            non_team[col] = w
            used += w
        team_w = total_w - used
        widths = [team_w if col == "TEAM" else non_team[col] for col in cols]
        widths[-1] += total_w - sum(widths)
        return widths

    def _col_xs(self, col_widths: list[int]) -> list[int]:
        xs, x = [], 0
        for w in col_widths:
            xs.append(x)
            x += w
        return xs

    # ------------------------------------------------------------------

    def _draw_title(self, draw, img, block, config, W, title_h, working_dir):
        draw.rectangle([0, 0, W - 1, title_h - 1], fill=config.title_bg)

        pad = round(title_h * 0.14)
        title_text = f"{block.season} {block.poll}"
        sub_text   = (
            f"Week {block.week}" if block.week else "Final Rankings"
        ) + (f"  ·  {block.season_type.title()}" if block.season_type != "regular" else "")

        title_font = get_font(max(12, round(title_h * 0.40)), bold=True)
        sub_font   = get_font(max(9,  round(title_h * 0.24)), italic=True)

        tb  = draw.textbbox((0, 0), title_text, font=title_font)
        sb  = draw.textbbox((0, 0), sub_text,   font=sub_font)
        gap = round(title_h * 0.06)
        total_h = (tb[3] - tb[1]) + gap + (sb[3] - sb[1])
        ty = (title_h - total_h) // 2

        draw.text(((W - (tb[2]-tb[0])) // 2, ty),
                  title_text, font=title_font, fill=config.title_fg)
        draw.text(((W - (sb[2]-sb[0])) // 2, ty + (tb[3] - tb[1]) + gap),
                  sub_text, font=sub_font, fill=config.title_fg)

    # ------------------------------------------------------------------

    def _draw_col_header(self, draw, cols, col_widths, config, y, header_h, W):
        draw.rectangle([0, y, W - 1, y + header_h - 1], fill=config.header_bg)
        font = get_font(max(8, round(header_h * 0.48)), bold=True, condensed=True)
        xs   = self._col_xs(col_widths)

        for i, col in enumerate(cols):
            col_x = xs[i]
            col_w = col_widths[i]
            label = col.replace("_", " ")
            bbox  = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            ty = y + (header_h - th) // 2

            if col in ("RANK", "TEAM"):
                draw.text((col_x + self.CELL_PAD_X, ty), label,
                          font=font, fill=config.header_fg)
            else:
                draw.text((col_x + col_w - tw - self.CELL_PAD_X, ty), label,
                          font=font, fill=config.header_fg)

            if i > 0:
                draw.line([(col_x, y), (col_x, y + header_h - 1)],
                          fill="#3d6a96", width=1)

    # ------------------------------------------------------------------

    def _draw_row(self, draw, img, entry, cols, col_widths, config, y, row_h, working_dir):
        font_sz   = max(8, round(row_h * 0.48))
        font      = get_font(font_sz)
        font_bold = get_font(font_sz, bold=True)
        xs        = self._col_xs(col_widths)

        for i, col in enumerate(cols):
            col_x = xs[i]
            col_w = col_widths[i]

            if col == "RANK":
                self._draw_rank_cell(draw, entry.rank, config,
                                     col_x, col_w, y, row_h, font_sz)
            elif col == "TEAM":
                logo_offset = 0
                if config.show_logos:
                    logo_sz = max(12, row_h - 6)
                    from app.data.logo_cache import get_logo
                    logo = get_logo(entry.team_abbrev, logo_sz, working_dir)
                    if logo:
                        ly = y + (row_h - logo_sz) // 2
                        img.paste(logo, (col_x + self.CELL_PAD_X, ly), logo)
                        logo_offset = logo_sz + self.CELL_PAD_X
                bbox = draw.textbbox((0, 0), entry.team_name, font=font_bold)
                ty = y + (row_h - (bbox[3] - bbox[1])) // 2
                draw.text((col_x + self.CELL_PAD_X + logo_offset, ty),
                          entry.team_name, font=font_bold, fill=config.text_color)
            else:
                val = self._get_value(entry, col)
                bbox = draw.textbbox((0, 0), val, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                tx = col_x + col_w - tw - self.CELL_PAD_X
                ty = y + (row_h - th) // 2
                draw.text((tx, ty), val, font=font, fill=config.text_color)
                draw.line([(col_x, y), (col_x, y + row_h - 1)],
                          fill=config.divider_color, width=1)

        draw.line([(0, y + row_h - 1), (config.width_px - 1, y + row_h - 1)],
                  fill=config.divider_color, width=1)

    def _draw_rank_cell(self, draw, rank, config, col_x, col_w, y, row_h, font_sz):
        badge_sz = round(row_h * 0.62)
        cx = col_x + self.CELL_PAD_X + badge_sz // 2
        cy = y + row_h // 2
        if rank in _BADGE_COLORS:
            r = badge_sz // 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         fill=_BADGE_COLORS[rank], outline=_BADGE_OUTLINE[rank])
            font = get_font(max(7, round(badge_sz * 0.50)), bold=True)
            text = str(rank)
            tb = draw.textbbox((0, 0), text, font=font)
            draw.text((cx - (tb[2] - tb[0]) // 2, cy - (tb[3] - tb[1]) // 2),
                      text, font=font, fill="#FFFFFF")
        else:
            font = get_font(font_sz, bold=True)
            text = str(rank)
            tb = draw.textbbox((0, 0), text, font=font)
            tx = col_x + self.CELL_PAD_X
            ty = y + (row_h - (tb[3] - tb[1])) // 2
            draw.text((tx, ty), text, font=font, fill=config.text_color)

    def _get_value(self, entry: RankingEntry, col: str) -> str:
        return {
            "CONF":   entry.conference or "—",
            "RECORD": "—",       # poll data doesn't include record; can be enriched later
            "POINTS": str(entry.points) if entry.points else "—",
            "1ST":    str(entry.first_place_votes) if entry.first_place_votes else "—",
        }.get(col, "")

    # ------------------------------------------------------------------

    def _draw_footer(self, draw, block, config, footer_y, footer_h, W, cols):
        font  = get_font(max(8, round(footer_h * 0.32)), italic=True)
        lines = []

        if config.show_col_explainers:
            parts = [
                f"{c}={COL_EXPLAINERS[c]}"
                for c in cols
                if c in COL_EXPLAINERS and c not in ("RANK", "TEAM")
            ]
            if parts:
                lines.append("  |  ".join(parts))

        if config.show_timestamp:
            lines.append(block.as_of.strftime("Data as of: %b %d, %Y  %I:%M %p"))

        if not lines:
            return

        n = len(lines)
        slot_h = footer_h // n
        for i, line in enumerate(lines):
            bb = draw.textbbox((0, 0), line, font=font)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            tx = (W - tw) // 2
            ty = footer_y + i * slot_h + (slot_h - th) // 2
            draw.text((tx, ty), line, font=font, fill=config.footer_color)
