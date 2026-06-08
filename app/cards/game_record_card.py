"""Game record card renderer."""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from PIL import Image, ImageDraw

from app.cards.base_card import CardConfig
from app.data.game_record_api import GameRecordBlock, GameResult
from app.utils.font_manager import get_font


@dataclass
class GameRecordCardConfig(CardConfig):
    show_logo: bool       = True
    show_summary: bool    = True
    show_timestamp: bool  = False
    date_sort: str        = "desc"
    team: str             = ""
    use_team_colors: bool = False
    show_week: bool       = False   # show WK column (auto-enabled in full_season mode)
    show_scores: bool     = True    # show score column; hide for spoiler-free schedule

    title_bg: str      = "#1a3a5c"
    title_fg: str      = "#FFFFFF"
    header_bg: str     = "#1a3a5c"
    header_fg: str     = "#FFFFFF"
    win_bg: str        = "#D4EDDA"
    loss_bg: str       = "#F8D7DA"
    tie_bg: str        = "#FFF3CD"
    row_alt_color: str = "#EEF2F7"
    row_color: str     = "#FFFFFF"
    divider_color: str = "#CCCCCC"
    text_color: str    = "#111111"
    footer_color: str  = "#888888"


_COLS_BASE        = ["DATE", "OPP", "H/A", "RESULT", "SCORE"]
_COLS_WITH_WK     = ["WK", "DATE", "OPP", "H/A", "TIME", "RESULT", "SCORE"]
_COL_FRACS_BASE   = {"DATE": 0.18, "OPP": 0.38, "H/A": 0.10, "RESULT": 0.12, "SCORE": 0.22}
_COL_FRACS_WK     = {"WK": 0.06, "DATE": 0.15, "OPP": 0.29, "H/A": 0.08, "TIME": 0.14, "RESULT": 0.10, "SCORE": 0.18}
_COL_FRACS_NO_SCR = {"DATE": 0.22, "OPP": 0.50, "H/A": 0.12, "RESULT": 0.16}
_COL_FRACS_WK_NO_SCR = {"WK": 0.07, "DATE": 0.17, "OPP": 0.36, "H/A": 0.09, "TIME": 0.15, "RESULT": 0.16}
_CELL_PAD   = 6
_TITLE_PCT  = 0.10
_HEADER_PCT = 0.065
_FOOTER_PCT = 0.07

# ---------------------------------------------------------------------------
# Time formatting helper
# ---------------------------------------------------------------------------

def _format_game_time(game) -> str:
    """Return a formatted kickoff time string in US Eastern, or 'TBD'."""
    if game.time_tbd or game.start_time_utc is None:
        return "TBD"
    # Only show time for upcoming games; completed games show score instead
    if game.team_score is not None:
        return ""
    try:
        import datetime as _dt
        utc = game.start_time_utc
        if utc.tzinfo is None:
            # Assume UTC
            utc = utc.replace(tzinfo=_dt.timezone.utc)
        # Convert to Eastern (UTC-4 in summer / EDT, UTC-5 in winter / EST)
        # Simple heuristic: EDT (UTC-4) from Mar to Nov, EST (UTC-5) otherwise
        month = utc.month
        offset = -4 if 3 <= month <= 11 else -5
        eastern = utc + _dt.timedelta(hours=offset)
        # Format: "12:00 PM ET"
        h = eastern.hour
        m = eastern.minute
        ampm = "PM" if h >= 12 else "AM"
        h12 = h % 12 or 12
        time_str = f"{h12}:{m:02d} {ampm} ET"
        return time_str
    except Exception:
        return "TBD"


class GameRecordCardRenderer:

    def render(
        self,
        block: GameRecordBlock,
        config: GameRecordCardConfig,
        working_dir: str,
    ) -> Image.Image:
        W = config.width_px
        H = config.height_px

        cols = self._cols(config)

        title_h  = round(H * _TITLE_PCT)
        header_h = round(H * _HEADER_PCT)
        has_footer = config.show_summary or config.show_timestamp
        footer_h = round(H * _FOOTER_PCT) if has_footer else 0

        data_h  = H - title_h - header_h - footer_h
        n_rows  = max(len(block.games), 1)
        row_h   = max(16, data_h // n_rows)

        col_widths = self._col_widths(W, cols)

        img  = config.new_canvas()
        draw = ImageDraw.Draw(img)

        self._draw_title(draw, img, block, config, W, title_h, working_dir)
        y = title_h
        self._draw_header(draw, cols, col_widths, config, y, header_h, W)
        y += header_h

        for i, game in enumerate(block.games):
            row_bg = self._row_bg(game, config, i)
            draw.rectangle([0, y, W - 1, y + row_h - 1], fill=row_bg)
            self._draw_row(draw, game, cols, col_widths, config, y, row_h)
            draw.line([(0, y + row_h - 1), (W - 1, y + row_h - 1)],
                      fill=config.divider_color, width=1)
            y += row_h

        if has_footer:
            fy = H - footer_h
            draw.line([(0, fy), (W - 1, fy)], fill=config.divider_color, width=1)
            self._draw_footer(draw, block, config, fy, footer_h, W)

        return img

    # ------------------------------------------------------------------

    def _cols(self, config: GameRecordCardConfig) -> list[str]:
        base = _COLS_WITH_WK if config.show_week else _COLS_BASE
        if not config.show_scores:
            return [c for c in base if c != "SCORE"]
        return base

    def _col_widths(self, total_w: int, cols: list[str]) -> list[int]:
        use_wk  = "WK" in cols
        use_scr = "SCORE" in cols
        if use_wk and use_scr:   fracs = _COL_FRACS_WK
        elif use_wk:             fracs = _COL_FRACS_WK_NO_SCR
        elif not use_scr:        fracs = _COL_FRACS_NO_SCR
        else:                    fracs = _COL_FRACS_BASE
        widths = [round(total_w * fracs.get(c, 0.10)) for c in cols]
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

        logo_sz   = round(title_h * 0.75)
        inner_gap = round(title_h * 0.10)
        logo      = None
        if config.show_logo:
            from app.data.logo_cache import get_logo, slugify
            logo = get_logo(slugify(block.team), logo_sz, working_dir)

        title_text = f"{block.season} {block.team}"
        sub_text   = "Season Schedule" if config.show_week else "Game Results"
        tf  = get_font(max(11, round(title_h * 0.36)), bold=True)
        sf  = get_font(max(8,  round(title_h * 0.22)), italic=True)
        tb  = draw.textbbox((0, 0), title_text, font=tf)
        sb  = draw.textbbox((0, 0), sub_text,   font=sf)
        text_w = max(tb[2]-tb[0], sb[2]-sb[0])
        gap    = round(title_h * 0.05)

        block_w = (logo_sz + inner_gap + text_w) if logo else text_w
        start_x = (W - block_w) // 2

        tot = (tb[3]-tb[1]) + gap + (sb[3]-sb[1])
        ty  = (title_h - tot) // 2

        if logo:
            ly = (title_h - logo_sz) // 2
            img.paste(logo, (start_x, ly), logo)
            text_start_x = start_x + logo_sz + inner_gap
        else:
            text_start_x = start_x

        draw.text((text_start_x + (text_w - (tb[2]-tb[0])) // 2, ty),
                  title_text, font=tf, fill=config.title_fg)
        draw.text((text_start_x + (text_w - (sb[2]-sb[0])) // 2, ty + (tb[3]-tb[1]) + gap),
                  sub_text, font=sf, fill=config.title_fg)

    def _draw_header(self, draw, cols, col_widths, config, y, header_h, W):
        draw.rectangle([0, y, W - 1, y + header_h - 1], fill=config.header_bg)
        font = get_font(max(7, round(header_h * 0.48)), bold=True, condensed=True)
        xs   = self._col_xs(col_widths)
        labels = {"WK": "WK", "DATE": "DATE", "OPP": "OPPONENT", "H/A": "H/A",
                  "RESULT": "W/L", "SCORE": "SCORE"}
        for i, col in enumerate(cols):
            col_x = xs[i]
            col_w = col_widths[i]
            lbl   = labels.get(col, col)
            bb    = draw.textbbox((0, 0), lbl, font=font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            ty = y + (header_h - th) // 2
            if col == "OPP":
                draw.text((col_x + _CELL_PAD, ty), lbl, font=font, fill=config.header_fg)
            else:
                draw.text((col_x + (col_w - tw) // 2, ty), lbl, font=font, fill=config.header_fg)
            if i > 0:
                draw.line([(col_x, y), (col_x, y + header_h - 1)], fill="#3d6a96", width=1)

    def _row_bg(self, game: GameResult, config: GameRecordCardConfig, idx: int) -> str:
        if game.result == "W":
            return config.win_bg
        if game.result == "L":
            return config.loss_bg
        if game.result == "T":
            return config.tie_bg
        return config.row_color if idx % 2 == 0 else config.row_alt_color

    def _draw_row(self, draw, game: GameResult, cols, col_widths, config, y, row_h):
        font_sz = max(7, round(row_h * 0.48))
        font    = get_font(font_sz)
        font_b  = get_font(font_sz, bold=True)
        xs      = self._col_xs(col_widths)

        is_upcoming = game.team_score is None
        values = {
            "WK":     str(game.week) if game.week else "",
            "DATE":   game.date.strftime("%b %d") if game.date else f"Wk {game.week}",
            "OPP":    game.opponent,
            "H/A":    "N" if game.is_neutral else ("H" if game.is_home else "A"),
            "TIME":   _format_game_time(game),
            "RESULT": game.result if game.result else ("▶" if is_upcoming else "—"),
            "SCORE":  (f"{game.team_score}–{game.opp_score}"
                       if game.team_score is not None else ("TBD" if is_upcoming else "—")),
        }
        result_colors = {"W": "#006600", "L": "#aa2200", "T": "#886600"}

        for i, col in enumerate(cols):
            col_x = xs[i]
            col_w = col_widths[i]
            val   = values.get(col, "")
            use_font = font_b if col == "OPP" else font
            bb    = draw.textbbox((0, 0), val, font=use_font)
            tw, th = bb[2] - bb[0], bb[3] - bb[1]
            ty    = y + (row_h - th) // 2

            color = config.text_color
            if col == "RESULT":
                color = result_colors.get(val, config.text_color)

            if col == "OPP":
                tx = col_x + _CELL_PAD
            else:
                tx = col_x + (col_w - tw) // 2

            draw.text((tx, ty), val, font=use_font, fill=color)
            if i > 0:
                draw.line([(col_x, y), (col_x, y + row_h - 1)],
                          fill=config.divider_color, width=1)

    def _draw_footer(self, draw, block, config, fy, footer_h, W):
        font  = get_font(max(8, round(footer_h * 0.32)), italic=True)
        lines = []

        if config.show_summary:
            lines.append(f"Season Record: {block.total_wins}–{block.total_losses}")

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
