"""Roster card renderer."""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw

from app.cards.base_card import CardConfig
from app.data.roster_api import RosterBlock, RosterPlayer, GROUP_ORDER
from app.utils.font_manager import get_font


@dataclass
class RosterCardConfig(CardConfig):
    show_logo: bool          = True
    show_timestamp: bool     = False
    group_by_position: bool  = True
    show_jersey: bool        = True
    show_year: bool          = True
    show_hometown: bool      = True
    show_height_weight: bool = False
    hide_ol: bool            = False
    hide_st: bool            = False
    team: str                = ""
    use_team_colors: bool    = False

    title_bg: str       = "#1a3a5c"
    title_fg: str       = "#FFFFFF"
    group_hdr_bg: str   = "#2c5f8a"
    group_hdr_fg: str   = "#FFFFFF"
    row_alt_color: str  = "#EEF2F7"
    row_color: str      = "#FFFFFF"
    divider_color: str  = "#CCCCCC"
    text_color: str     = "#111111"
    footer_color: str   = "#888888"


_TITLE_PCT  = 0.08
_FOOTER_PCT = 0.05
_GROUP_H_PT = 0.022   # group header as fraction of card height


class RosterCardRenderer:

    CELL_PAD = 5

    def render(
        self,
        block: RosterBlock,
        config: RosterCardConfig,
        working_dir: str,
    ) -> Image.Image:
        W = config.width_px
        H = config.height_px

        title_h  = round(H * _TITLE_PCT)
        footer_h = round(H * _FOOTER_PCT) if config.show_timestamp else 0
        body_h   = H - title_h - footer_h

        img  = config.new_canvas()
        draw = ImageDraw.Draw(img)

        self._draw_title(draw, img, block, config, W, title_h, working_dir)

        # Collect rows to draw
        rows = self._build_rows(block, config)
        n_rows = len(rows)

        if n_rows == 0:
            draw.text((10, title_h + 10), "No roster data.", font=get_font(12), fill=config.text_color)
        else:
            row_h = max(12, body_h // n_rows)
            y = title_h
            for row in rows:
                if row.get("group_header"):
                    self._draw_group_header(draw, row["label"], config, y, row_h, W)
                else:
                    bg = config.row_color if row["idx"] % 2 == 0 else config.row_alt_color
                    draw.rectangle([0, y, W - 1, y + row_h - 1], fill=bg)
                    self._draw_player_row(draw, row["player"], config, y, row_h, W)
                    draw.line([(0, y + row_h - 1), (W - 1, y + row_h - 1)],
                              fill=config.divider_color, width=1)
                y += row_h

        if config.show_timestamp:
            fy = H - footer_h
            draw.line([(0, fy), (W - 1, fy)], fill=config.divider_color, width=1)
            font = get_font(max(7, round(footer_h * 0.35)), italic=True)
            ts   = block.as_of.strftime("Data as of: %b %d, %Y %I:%M %p")
            draw.text((8, fy + 3), ts, font=font, fill=config.footer_color)

        return img

    # ------------------------------------------------------------------

    def _build_rows(self, block: RosterBlock, config: RosterCardConfig) -> list[dict]:
        rows = []
        if config.group_by_position:
            grouped = block.grouped()
            player_idx = 0
            for group, players in grouped.items():
                if config.hide_ol and group == "OL":
                    continue
                if config.hide_st and group == "ST":
                    continue
                rows.append({"group_header": True, "label": group})
                for p in players:
                    rows.append({"group_header": False, "player": p, "idx": player_idx})
                    player_idx += 1
        else:
            for i, p in enumerate(block.players):
                if config.hide_ol and p.pos_group == "OL":
                    continue
                if config.hide_st and p.pos_group == "ST":
                    continue
                rows.append({"group_header": False, "player": p, "idx": i})
        return rows

    def _draw_title(self, draw, img, block, config, W, title_h, working_dir):
        draw.rectangle([0, 0, W - 1, title_h - 1], fill=config.title_bg)

        logo_sz   = round(title_h * 0.78)
        inner_gap = round(title_h * 0.10)
        logo      = None
        if config.show_logo:
            from app.data.logo_cache import get_logo, slugify
            logo = get_logo(slugify(block.team), logo_sz, working_dir)

        title_text = f"{block.season} {block.team} Roster"
        tf   = get_font(max(10, round(title_h * 0.38)), bold=True)
        tb   = draw.textbbox((0, 0), title_text, font=tf)
        text_w = tb[2]-tb[0]

        block_w = (logo_sz + inner_gap + text_w) if logo else text_w
        start_x = (W - block_w) // 2
        ty      = (title_h - (tb[3]-tb[1])) // 2

        if logo:
            ly = (title_h - logo_sz) // 2
            img.paste(logo, (start_x, ly), logo)
            text_x = start_x + logo_sz + inner_gap
        else:
            text_x = start_x

        draw.text((text_x, ty), title_text, font=tf, fill=config.title_fg)

    def _draw_group_header(self, draw, label, config, y, row_h, W):
        draw.rectangle([0, y, W - 1, y + row_h - 1], fill=config.group_hdr_bg)
        font = get_font(max(7, round(row_h * 0.55)), bold=True, condensed=True)
        bb   = draw.textbbox((0, 0), label, font=font)
        ty   = y + (row_h - (bb[3] - bb[1])) // 2
        draw.text((self.CELL_PAD, ty), label, font=font, fill=config.group_hdr_fg)

    def _draw_player_row(self, draw, player: RosterPlayer, config, y, row_h, W):
        font_sz = max(7, round(row_h * 0.50))
        font    = get_font(font_sz)
        font_b  = get_font(font_sz, bold=True)
        pad     = self.CELL_PAD

        x = pad
        # Jersey
        if config.show_jersey and player.jersey:
            jtext = f"#{player.jersey}"
            jb    = draw.textbbox((0, 0), jtext, font=font)
            jw    = jb[2] - jb[0]
            jy    = y + (row_h - (jb[3] - jb[1])) // 2
            draw.text((x, jy), jtext, font=font, fill=config.footer_color)
            x += jw + pad * 2

        # Name
        name = f"{player.first_name} {player.last_name}"
        nb   = draw.textbbox((0, 0), name, font=font_b)
        ny   = y + (row_h - (nb[3] - nb[1])) // 2
        draw.text((x, ny), name, font=font_b, fill=config.text_color)
        x += (nb[2] - nb[0]) + pad * 2

        # Position
        pos_text = player.position
        pb = draw.textbbox((0, 0), pos_text, font=font)
        py = y + (row_h - (pb[3] - pb[1])) // 2
        draw.text((x, py), pos_text, font=font, fill=config.footer_color)
        x += (pb[2] - pb[0]) + pad * 2

        # Right-side metadata (right-aligned)
        right_parts = []
        if config.show_year and player.year_str:
            right_parts.append(player.year_str)
        if config.show_height_weight:
            hw = " ".join(filter(None, [player.height_str,
                                         f"{player.weight}lbs" if player.weight else ""]))
            if hw:
                right_parts.append(hw)
        if config.show_hometown and player.hometown:
            right_parts.append(player.hometown)

        if right_parts:
            right_text = "  ·  ".join(right_parts)
            rb  = draw.textbbox((0, 0), right_text, font=font)
            rx  = W - (rb[2] - rb[0]) - pad
            ry  = y + (row_h - (rb[3] - rb[1])) // 2
            draw.text((rx, ry), right_text, font=font, fill=config.footer_color)
