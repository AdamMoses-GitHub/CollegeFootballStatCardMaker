"""Matchup card renderer — side-by-side team comparison."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from app.cards.base_card import CardConfig
from app.data.matchup_api import MatchupBlock, TeamSeasonStats
from app.utils.font_manager import get_font


@dataclass
class MatchupCardConfig(CardConfig):
    show_logos: bool          = True
    show_timestamp: bool      = False
    stat_set: str             = "Standard"
    win_highlight: str        = "#D4EDDA"
    use_team_colors: bool     = False
    # Per-team colors for the side columns (set programmatically when use_team_colors=True)
    team_a_color: str         = "#1a3a5c"
    team_a_fg: str            = "#FFFFFF"
    team_b_color: str         = "#1a3a5c"
    team_b_fg: str            = "#FFFFFF"

    title_bg: str       = "#1a3a5c"
    title_fg: str       = "#FFFFFF"
    row_alt_color: str  = "#EEF2F7"
    row_color: str      = "#FFFFFF"
    divider_color: str  = "#CCCCCC"
    text_color: str     = "#111111"
    label_color: str    = "#444444"
    footer_color: str   = "#888888"
    subhdr_bg: str      = "#2c5f8a"
    subhdr_fg: str      = "#FFFFFF"


_STANDARD_ROWS = [
    ("Record",          "record"),
    ("PPG",             "ppg"),
    ("Opp PPG",         "opp_ppg"),
    ("Yards/Game",      "total_yards_pg"),
    ("Opp Yards/Game",  "opp_yards_pg"),
    ("Turnovers",       "turnovers"),
]
_ADVANCED_ROWS = [
    ("Record",          "record"),
    ("PPG",             "ppg"),
    ("EPA/Play",        "epa_per_play"),
    ("Success Rate",    "success_rate"),
    ("Explosiveness",   "explosiveness"),
    ("Opp PPG",         "opp_ppg"),
]

_TITLE_PCT  = 0.16
_TEAMS_PCT  = 0.14
_FOOTER_PCT = 0.06


class MatchupCardRenderer:

    CELL_PAD = 8

    def render(
        self,
        block: MatchupBlock,
        config: MatchupCardConfig,
        working_dir: str,
    ) -> Image.Image:
        W = config.width_px
        H = config.height_px

        title_h  = round(H * _TITLE_PCT)
        teams_h  = round(H * _TEAMS_PCT)
        footer_h = round(H * _FOOTER_PCT) if config.show_timestamp else 0
        body_h   = H - title_h - teams_h - footer_h

        rows = _ADVANCED_ROWS if block.stat_set == "Advanced" else _STANDARD_ROWS
        n_rows = len(rows)
        row_h  = max(14, body_h // n_rows)

        img  = config.new_canvas()
        draw = ImageDraw.Draw(img)

        # Column widths: left stat = 1/3, centre label = 1/3, right stat = 1/3
        col_w  = W // 3
        left_x  = 0
        mid_x   = col_w
        right_x = col_w * 2

        self._draw_title(draw, block, config, W, title_h)
        self._draw_teams_header(draw, img, block, config,
                                W, title_h, teams_h,
                                left_x, mid_x, right_x, col_w, working_dir)

        y = title_h + teams_h
        for i, (label, key) in enumerate(rows):
            row_bg = config.row_color if i % 2 == 0 else config.row_alt_color
            draw.rectangle([0, y, W - 1, y + row_h - 1], fill=row_bg)
            self._draw_stat_row(draw, block, config, label, key,
                                y, row_h, W, left_x, mid_x, right_x, col_w)
            draw.line([(0, y + row_h - 1), (W - 1, y + row_h - 1)],
                      fill=config.divider_color, width=1)
            y += row_h

        if config.show_timestamp:
            fy = H - footer_h
            draw.line([(0, fy), (W - 1, fy)], fill=config.divider_color, width=1)
            font = get_font(max(8, round(footer_h * 0.38)), italic=True)
            ts   = block.as_of.strftime("Data as of: %b %d, %Y  %I:%M %p")
            bb   = draw.textbbox((0, 0), ts, font=font)
            tw, th = bb[2]-bb[0], bb[3]-bb[1]
            draw.text(((W - tw) // 2, fy + (footer_h - th) // 2),
                      ts, font=font, fill=config.footer_color)

        return img

    # ------------------------------------------------------------------

    def _draw_title(self, draw, block, config, W, title_h):
        draw.rectangle([0, 0, W - 1, title_h - 1], fill=config.title_bg)
        pad        = self.CELL_PAD
        title_text = f"{block.season} Matchup"
        sub_text   = f"{block.team_a}  vs  {block.team_b}"
        atw        = f"All-time: {block.all_time_wins_a}–{block.all_time_wins_b}"
        if block.all_time_ties:
            atw += f"–{block.all_time_ties}"

        tf = get_font(max(12, round(title_h * 0.28)), bold=True)
        sf = get_font(max(10, round(title_h * 0.22)))
        af = get_font(max(8,  round(title_h * 0.17)), italic=True)

        tb = draw.textbbox((0, 0), title_text, font=tf)
        sb = draw.textbbox((0, 0), sub_text,   font=sf)
        ab = draw.textbbox((0, 0), atw,         font=af)

        gap  = round(title_h * 0.04)
        tot  = (tb[3]-tb[1]) + gap + (sb[3]-sb[1]) + gap + (ab[3]-ab[1])
        ty   = (title_h - tot) // 2

        # Centre all lines
        for text, font, bbox in [(title_text, tf, tb), (sub_text, sf, sb), (atw, af, ab)]:
            tx = (W - (bbox[2] - bbox[0])) // 2
            draw.text((tx, ty), text, font=font, fill=config.title_fg)
            ty += (bbox[3] - bbox[1]) + gap

    def _draw_teams_header(
        self, draw, img, block, config, W, y0, h,
        left_x, mid_x, right_x, col_w, working_dir,
    ):
        pad      = self.CELL_PAD
        logo_sz  = round(h * 0.70)
        font     = get_font(max(10, round(h * 0.28)), bold=True)

        # Per-team background colors
        bg_a = config.team_a_color if config.use_team_colors else config.subhdr_bg
        fg_a = config.team_a_fg    if config.use_team_colors else config.subhdr_fg
        bg_b = config.team_b_color if config.use_team_colors else config.subhdr_bg
        fg_b = config.team_b_fg    if config.use_team_colors else config.subhdr_fg

        # Draw per-team coloured panels
        draw.rectangle([left_x, y0, left_x + col_w - 1, y0 + h - 1], fill=bg_a)
        draw.rectangle([right_x, y0, right_x + col_w - 1, y0 + h - 1], fill=bg_b)
        # Centre panel always uses title_bg
        draw.rectangle([mid_x, y0, mid_x + col_w - 1, y0 + h - 1], fill=config.title_bg)

        for team, col_x, anchor, bg, fg in [
            (block.team_a, left_x,  "left",  bg_a, fg_a),
            (block.team_b, right_x, "right", bg_b, fg_b),
        ]:
            logo: Optional[Image.Image] = None
            if config.show_logos:
                from app.data.logo_cache import get_logo, slugify
                logo = get_logo(slugify(team), logo_sz, working_dir)

            tb = draw.textbbox((0, 0), team, font=font)
            tw = tb[2] - tb[0]

            if anchor == "left":
                lx = col_x + pad
                if logo:
                    ly = y0 + (h - logo_sz) // 2
                    img.paste(logo, (lx, ly), logo)
                    lx += logo_sz + pad
                ty = y0 + (h - (tb[3]-tb[1])) // 2
                draw.text((lx, ty), team, font=font, fill=fg)
            else:
                rx = col_x + col_w - pad
                if logo:
                    lx = rx - logo_sz
                    ly = y0 + (h - logo_sz) // 2
                    img.paste(logo, (lx, ly), logo)
                    rx = lx - pad
                tx = rx - tw
                ty = y0 + (h - (tb[3]-tb[1])) // 2
                draw.text((tx, ty), team, font=font, fill=fg)

        # Centre: "vs" label
        vs_font = get_font(max(10, round(h * 0.30)), bold=True)
        vb = draw.textbbox((0, 0), "vs", font=vs_font)
        draw.text(
            (mid_x + (col_w - (vb[2]-vb[0])) // 2,
             y0 + (h - (vb[3]-vb[1])) // 2),
            "vs", font=vs_font, fill=config.title_fg,
        )

    def _draw_stat_row(
        self, draw, block: MatchupBlock, config,
        label: str, key: str,
        y, row_h, W, left_x, mid_x, right_x, col_w,
    ):
        val_a = self._get_val(block.stats_a, key)
        val_b = self._get_val(block.stats_b, key)

        better_a, better_b = self._compare(key, block.stats_a, block.stats_b)

        font_sz = max(8, round(row_h * 0.48))
        font    = get_font(font_sz)
        font_b  = get_font(font_sz, bold=True)
        font_lbl= get_font(max(7, round(row_h * 0.40)))
        pad     = self.CELL_PAD

        # Highlight winner — use team color tint when team colors are enabled
        if config.use_team_colors:
            from app.data.teams_api import _tint
            hl_a = _tint(config.team_a_color, 0.20)
            hl_b = _tint(config.team_b_color, 0.20)
        else:
            hl_a = hl_b = config.win_highlight

        if better_a:
            draw.rectangle([left_x, y, left_x + col_w - 1, y + row_h - 1], fill=hl_a)
        if better_b:
            draw.rectangle([right_x, y, right_x + col_w - 1, y + row_h - 1], fill=hl_b)

        # Team A value (right-aligned in left column)
        fa   = font_b if better_a else font
        ab   = draw.textbbox((0, 0), val_a, font=fa)
        ax   = left_x + col_w - (ab[2]-ab[0]) - pad
        ay   = y + (row_h - (ab[3]-ab[1])) // 2
        draw.text((ax, ay), val_a, font=fa, fill=config.text_color)

        # Centre label
        lb   = draw.textbbox((0, 0), label, font=font_lbl)
        lx   = mid_x + (col_w - (lb[2]-lb[0])) // 2
        ly   = y + (row_h - (lb[3]-lb[1])) // 2
        draw.text((lx, ly), label, font=font_lbl, fill=config.label_color)

        # Team B value (left-aligned in right column)
        fb   = font_b if better_b else font
        bb_  = draw.textbbox((0, 0), val_b, font=fb)
        bx   = right_x + pad
        by   = y + (row_h - (bb_[3]-bb_[1])) // 2
        draw.text((bx, by), val_b, font=fb, fill=config.text_color)

        # Column dividers
        draw.line([(mid_x, y), (mid_x, y + row_h - 1)],
                  fill=config.divider_color, width=1)
        draw.line([(right_x, y), (right_x, y + row_h - 1)],
                  fill=config.divider_color, width=1)

    # ------------------------------------------------------------------

    def _get_val(self, stats: TeamSeasonStats, key: str) -> str:
        if key == "record":
            return f"{stats.wins}–{stats.losses}"
        v = getattr(stats, key, None)
        if v is None:
            return "—"
        if key in ("success_rate",):
            return f"{v}%"
        return str(v)

    def _compare(self, key: str, a: TeamSeasonStats, b: TeamSeasonStats):
        """Return (a_is_better, b_is_better)."""
        lower_is_better = {"opp_ppg", "opp_yards_pg", "turnovers"}
        if key == "record":
            if a.wins > b.wins:   return True, False
            if b.wins > a.wins:   return False, True
            return False, False
        va = getattr(a, key, None)
        vb = getattr(b, key, None)
        if va is None or vb is None:
            return False, False
        if va == vb:
            return False, False
        if key in lower_is_better:
            return va < vb, vb < va
        return va > vb, vb > va
