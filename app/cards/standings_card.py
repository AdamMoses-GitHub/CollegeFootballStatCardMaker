"""Standings card renderer for CFB Stat Card Maker."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from app.cards.base_card import CardConfig
from app.data.cfb_api import StandingsBlock, StandingsEntry
from app.utils.font_manager import get_font


# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

STANDARD_COLS = ["RK", "TEAM", "W", "L", "PCT"]
EXTENDED_COLS = ["RK", "TEAM", "W", "L", "PCT", "CONF_W", "CONF_L", "PF", "PA", "STK"]

COL_EXPLAINERS: dict[str, str] = {
    "W":      "Wins",
    "L":      "Losses",
    "PCT":    "Win %",
    "CONF_W": "Conf Wins",
    "CONF_L": "Conf Losses",
    "PF":     "Points For",
    "PA":     "Points Against",
    "STK":    "Current Streak",
}

# Column width fractions for non-TEAM columns; TEAM gets the remainder
_COL_FRACS_STANDARD: dict[str, float] = {
    "RK":     0.07,
    "W":      0.09,
    "L":      0.09,
    "PCT":    0.13,
}
_COL_FRACS_EXTENDED: dict[str, float] = {
    "RK":     0.06,
    "W":      0.07,
    "L":      0.07,
    "PCT":    0.10,
    "CONF_W": 0.08,
    "CONF_L": 0.08,
    "PF":     0.08,
    "PA":     0.08,
    "STK":    0.07,
}

_EXTENDED_THRESHOLD = 7.5
_MIN_ROW_H = 18
_MAX_ROWS   = 30


def suggest_column_mode(width_in: float) -> str:
    return "extended" if width_in >= _EXTENDED_THRESHOLD else "standard"


# ---------------------------------------------------------------------------
# Card config
# ---------------------------------------------------------------------------

@dataclass
class StandingsCardConfig(CardConfig):
    show_logos: bool = True
    show_timestamp: bool = False
    show_col_explainers: bool = False
    column_mode: str = "auto"
    season: int = 0
    conference: str = "SEC"
    max_rows: int = 0   # 0 = use _MAX_ROWS cap

    header_bg: str     = "#1a3a5c"
    header_fg: str     = "#FFFFFF"
    title_bg: str      = "#1a3a5c"
    title_fg: str      = "#FFFFFF"
    row_alt_color: str = "#EEF2F7"
    row_color: str     = "#FFFFFF"
    divider_color: str = "#CCCCCC"
    div_header_bg: str = "#2c5f8a"
    div_header_fg: str = "#FFFFFF"
    text_color: str    = "#111111"
    footer_color: str  = "#888888"


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class StandingsCardRenderer:

    TITLE_H_PCT  = 0.12
    HEADER_H_PCT = 0.07
    FOOTER_H_PCT = 0.08
    CELL_PAD_X   = 8

    def render(
        self,
        block: StandingsBlock,
        config: StandingsCardConfig,
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
            self._draw_row(draw, img, entry, cols, col_widths, config, y, row_h, working_dir, rank=i + 1)
            y += row_h

        if has_footer:
            fy = H - footer_h
            draw.line([(0, fy), (W - 1, fy)], fill=config.divider_color, width=1)
            self._draw_footer(draw, block, config, fy, footer_h, W, cols)

        return img

    # ------------------------------------------------------------------

    def _resolve_cols(self, config: StandingsCardConfig) -> list[str]:
        mode = config.column_mode
        if mode == "auto":
            mode = suggest_column_mode(config.width_in)
        return EXTENDED_COLS if mode == "extended" else STANDARD_COLS

    def _cap_entries(self, entries: list[StandingsEntry], config: StandingsCardConfig) -> list[StandingsEntry]:
        cap = config.max_rows if config.max_rows > 0 else _MAX_ROWS
        return entries[:cap]

    def _calc_col_widths(self, cols: list[str], total_w: int) -> list[int]:
        fracs = _COL_FRACS_EXTENDED if len(cols) > 5 else _COL_FRACS_STANDARD
        non_team: dict[str, int] = {}
        used = 0
        for col in cols:
            if col == "TEAM":
                continue
            w = round(total_w * fracs.get(col, 0.09))
            non_team[col] = w
            used += w
        team_w = total_w - used
        widths = [team_w if col == "TEAM" else non_team[col] for col in cols]
        widths[-1] += total_w - sum(widths)   # absorb rounding
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

        logo_size  = round(title_h * 0.72)
        inner_gap  = round(title_h * 0.10)  # gap between logo and text
        logo_img: Optional[Image.Image] = None

        if config.show_logos and config.conference != "Independents":
            from app.data.logo_cache import get_conference_logo
            logo_img = get_conference_logo(config.conference, logo_size, working_dir)

        title_text  = f"{block.season} CFB Standings"
        sub_text    = config.conference
        title_font  = get_font(max(12, round(title_h * 0.38)), bold=True)
        sub_font    = get_font(max(9,  round(title_h * 0.22)), italic=True)

        tb  = draw.textbbox((0, 0), title_text, font=title_font)
        sb  = draw.textbbox((0, 0), sub_text,   font=sub_font)
        text_w = max(tb[2]-tb[0], sb[2]-sb[0])
        gap    = round(title_h * 0.05)

        # Total block width and starting x
        if logo_img:
            block_w = logo_size + inner_gap + text_w
        else:
            block_w = text_w
        start_x = (W - block_w) // 2

        total_text_h = (tb[3]-tb[1]) + gap + (sb[3]-sb[1])
        text_y = (title_h - total_text_h) // 2

        if logo_img:
            ly = (title_h - logo_size) // 2
            img.paste(logo_img, (start_x, ly), logo_img)
            text_start_x = start_x + logo_size + inner_gap
        else:
            text_start_x = start_x

        title_x = text_start_x + (text_w - (tb[2]-tb[0])) // 2
        sub_x   = text_start_x + (text_w - (sb[2]-sb[0])) // 2

        draw.text((title_x, text_y), title_text, font=title_font, fill=config.title_fg)
        draw.text((sub_x, text_y + (tb[3]-tb[1]) + gap), sub_text,
                  font=sub_font, fill=config.title_fg)

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

            if col in ("RK", "TEAM"):
                draw.text((col_x + self.CELL_PAD_X, ty), label,
                          font=font, fill=config.header_fg)
            else:
                draw.text((col_x + col_w - tw - self.CELL_PAD_X, ty), label,
                          font=font, fill=config.header_fg)
                # Divider before this column
                draw.line([(col_x, y), (col_x, y + header_h - 1)],
                          fill="#3d6a96", width=1)

    # ------------------------------------------------------------------

    def _draw_row(self, draw, img, entry, cols, col_widths, config, y, row_h, working_dir, rank: int = 0):
        font_sz   = max(8, round(row_h * 0.48))
        font      = get_font(font_sz)
        font_bold = get_font(font_sz, bold=True)
        xs        = self._col_xs(col_widths)
        values    = self._entry_values(entry, rank)

        for i, col in enumerate(cols):
            col_x = xs[i]
            col_w = col_widths[i]
            val   = values.get(col, "")

            if col == "RK":
                bbox = draw.textbbox((0, 0), val, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                tx = col_x + (col_w - tw) // 2
                ty = y + (row_h - th) // 2
                draw.text((tx, ty), val, font=font, fill=config.footer_color)
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

                bbox = draw.textbbox((0, 0), val, font=font_bold)
                ty   = y + (row_h - (bbox[3] - bbox[1])) // 2
                draw.text((col_x + self.CELL_PAD_X + logo_offset, ty),
                          val, font=font_bold, fill=config.text_color)
            else:
                bbox = draw.textbbox((0, 0), val, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                tx = col_x + col_w - tw - self.CELL_PAD_X
                ty = y + (row_h - th) // 2
                draw.text((tx, ty), val, font=font, fill=config.text_color)
                # Vertical divider (skip after RK — it has no divider; draw for all stat cols)
                draw.line([(col_x, y), (col_x, y + row_h - 1)],
                          fill=config.divider_color, width=1)

        # Horizontal row divider
        draw.line([(0, y + row_h - 1), (config.width_px - 1, y + row_h - 1)],
                  fill=config.divider_color, width=1)

    # ------------------------------------------------------------------

    def _entry_values(self, entry: StandingsEntry, rank: int = 0) -> dict[str, str]:
        pf = round(entry.points_for)
        pa = round(entry.points_against)
        return {
            "RK":     str(rank) if rank else "",
            "TEAM":   entry.team_name,
            "W":      str(entry.wins),
            "L":      str(entry.losses),
            "PCT":    entry.pct_str,
            "CONF_W": str(entry.conf_wins),
            "CONF_L": str(entry.conf_losses),
            "PF":     str(pf) if pf else "—",
            "PA":     str(pa) if pa else "—",
            "STK":    entry.streak or "—",
        }

    # ------------------------------------------------------------------

    def _draw_footer(self, draw, block, config, footer_y, footer_h, W, cols):
        font    = get_font(max(8, round(footer_h * 0.32)), italic=True)
        sep     = "="
        lines   = []

        if config.show_col_explainers:
            parts = [
                f"{col}{sep}{COL_EXPLAINERS[col]}"
                for col in cols
                if col in COL_EXPLAINERS and col not in ("TEAM", "RK")
            ]
            if parts:
                lines.append("  |  ".join(parts))

        if config.show_timestamp:
            lines.append(block.as_of.strftime("Data as of: %b %d, %Y  %I:%M %p"))

        if not lines:
            return

        # Distribute lines evenly across footer height
        n        = len(lines)
        slot_h   = footer_h // n
        for i, line in enumerate(lines):
            bb   = draw.textbbox((0, 0), line, font=font)
            tw   = bb[2] - bb[0]
            th   = bb[3] - bb[1]
            tx   = (W - tw) // 2
            ty   = footer_y + i * slot_h + (slot_h - th) // 2
            draw.text((tx, ty), line, font=font, fill=config.footer_color)
