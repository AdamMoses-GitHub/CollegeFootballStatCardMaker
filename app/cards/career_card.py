"""Player career card renderer."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from app.cards.base_card import CardConfig
from app.data.career_api import CareerBlock, CareerSeasonRow, CAREER_COLS, CAREER_COL_EXPLAINERS
from app.utils.font_manager import get_font


@dataclass
class CareerCardConfig(CardConfig):
    show_logo: bool            = True
    show_timestamp: bool       = False
    show_col_explainers: bool  = False
    highlight_recent: bool     = True
    stat_type: str             = "Passing"

    title_bg: str       = "#1a3a5c"
    title_fg: str       = "#FFFFFF"
    header_bg: str      = "#1a3a5c"
    header_fg: str      = "#FFFFFF"
    highlight_bg: str   = "#FFF9C4"
    row_alt_color: str  = "#EEF2F7"
    row_color: str      = "#FFFFFF"
    divider_color: str  = "#CCCCCC"
    text_color: str     = "#111111"
    footer_color: str   = "#888888"


_COL_FRACS_BASE: dict[str, float] = {
    "YEAR": 0.10, "TEAM": 0.18, "G": 0.07,
    "CMP": 0.08, "ATT": 0.08, "YDS": 0.10, "TD": 0.07, "INT": 0.07, "RATING": 0.10,
    "CAR": 0.08, "AVG": 0.09, "REC": 0.08,
    "TKL": 0.09, "SACKS": 0.09, "PD": 0.08, "FF": 0.08,
}
_TITLE_PCT  = 0.10
_HEADER_PCT = 0.07
_FOOTER_PCT = 0.07
_CELL_PAD   = 6


class CareerCardRenderer:

    def render(
        self,
        block: CareerBlock,
        config: CareerCardConfig,
        working_dir: str,
    ) -> Image.Image:
        W = config.width_px
        H = config.height_px

        cols     = CAREER_COLS.get(block.stat_type, CAREER_COLS["Passing"])
        title_h  = round(H * _TITLE_PCT)
        header_h = round(H * _HEADER_PCT)
        has_footer = config.show_timestamp or config.show_col_explainers
        footer_h = round(H * _FOOTER_PCT) if has_footer else 0
        data_h   = H - title_h - header_h - footer_h
        n_rows   = max(len(block.rows), 1)
        row_h    = max(14, data_h // n_rows)

        col_widths = self._col_widths(cols, W)

        img  = config.new_canvas()
        draw = ImageDraw.Draw(img)

        self._draw_title(draw, img, block, config, W, title_h, working_dir)
        y = title_h
        self._draw_header(draw, cols, col_widths, config, y, header_h, W)
        y += header_h

        most_recent_season = max((r.season for r in block.rows), default=0)

        for i, row in enumerate(block.rows):
            is_recent = config.highlight_recent and row.season == most_recent_season
            row_bg = config.highlight_bg if is_recent else (
                config.row_color if i % 2 == 0 else config.row_alt_color
            )
            draw.rectangle([0, y, W - 1, y + row_h - 1], fill=row_bg)
            self._draw_row(draw, row, cols, col_widths, config, y, row_h, is_recent)
            draw.line([(0, y + row_h - 1), (W - 1, y + row_h - 1)],
                      fill=config.divider_color, width=1)
            y += row_h

        if has_footer:
            fy = H - footer_h
            draw.line([(0, fy), (W - 1, fy)], fill=config.divider_color, width=1)
            self._draw_footer(draw, block, config, cols, fy, footer_h)

        return img

    # ------------------------------------------------------------------

    def _col_widths(self, cols: list[str], total_w: int) -> list[int]:
        widths = [round(total_w * _COL_FRACS_BASE.get(c, 0.10)) for c in cols]
        diff   = total_w - sum(widths)
        widths[-1] += diff
        return widths

    def _col_xs(self, col_widths):
        xs, x = [], 0
        for w in col_widths:
            xs.append(x); x += w
        return xs

    def _draw_title(self, draw, img, block, config, W, title_h, working_dir):
        draw.rectangle([0, 0, W - 1, title_h - 1], fill=config.title_bg)
        pad = 8
        title_text = f"{block.player_name} — Career {block.stat_type}"
        font = get_font(max(10, round(title_h * 0.40)), bold=True)
        tb   = draw.textbbox((0, 0), title_text, font=font)
        ty   = (title_h - (tb[3] - tb[1])) // 2
        draw.text(((W - (tb[2]-tb[0])) // 2, ty), title_text, font=font, fill=config.title_fg)

    def _draw_header(self, draw, cols, col_widths, config, y, header_h, W):
        draw.rectangle([0, y, W - 1, y + header_h - 1], fill=config.header_bg)
        font = get_font(max(7, round(header_h * 0.48)), bold=True, condensed=True)
        xs   = self._col_xs(col_widths)
        for i, col in enumerate(cols):
            col_x = xs[i]; col_w = col_widths[i]
            bb    = draw.textbbox((0, 0), col, font=font)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            ty    = y + (header_h - th) // 2
            if col in ("YEAR", "TEAM"):
                draw.text((col_x + _CELL_PAD, ty), col, font=font, fill=config.header_fg)
            else:
                draw.text((col_x + col_w - tw - _CELL_PAD, ty), col, font=font, fill=config.header_fg)
            if i > 0:
                draw.line([(col_x, y), (col_x, y + header_h - 1)], fill="#3d6a96", width=1)

    def _draw_row(self, draw, row: CareerSeasonRow, cols, col_widths, config, y, row_h, bold_row):
        font_sz = max(7, round(row_h * 0.48))
        font    = get_font(font_sz, bold=bold_row)
        xs      = self._col_xs(col_widths)
        for i, col in enumerate(cols):
            col_x = xs[i]; col_w = col_widths[i]
            if col == "YEAR":
                val = str(row.season)
            elif col == "TEAM":
                val = row.team
            elif col == "G":
                val = str(row.games) if row.games else "—"
            else:
                val = row.stats.get(col, "—")
            bb = draw.textbbox((0, 0), val, font=font)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            ty = y + (row_h - th) // 2
            if col in ("YEAR", "TEAM"):
                draw.text((col_x + _CELL_PAD, ty), val, font=font, fill=config.text_color)
            else:
                draw.text((col_x + col_w - tw - _CELL_PAD, ty), val, font=font, fill=config.text_color)
                draw.line([(col_x, y), (col_x, y + row_h - 1)], fill=config.divider_color, width=1)

    def _draw_footer(self, draw, block, config, cols, fy, footer_h):
        W     = config.width_px
        font  = get_font(max(8, round(footer_h * 0.32)), italic=True)
        lines = []

        if config.show_col_explainers:
            parts = [f"{c}={CAREER_COL_EXPLAINERS[c]}" for c in cols
                     if c in CAREER_COL_EXPLAINERS and c not in ("YEAR","TEAM","G")]
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
            ty = fy + i * slot_h + (slot_h - th) // 2
            draw.text((tx, ty), line, font=font, fill=config.footer_color)
