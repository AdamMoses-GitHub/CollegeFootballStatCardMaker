"""CFP Playoff bracket card renderer for CFB Stat Card Maker.

Layout algorithm
----------------
All rounds share a common base grid whose cell count = max games in any round.
Game i in a round with n_games occupies cells [i * step .. (i+1) * step)
where step = max_games / n_games.  Its vertical centre = cell_h * (i + 0.5) * step.

This guarantees that a game in round R+1 is always centred exactly at the
midpoint of the two games from round R that feed into it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PIL import Image, ImageDraw

from app.cards.base_card import CardConfig
from app.data.playoffs_api import PlayoffBracket, PlayoffGame, is_12_team_format
from app.utils.font_manager import get_font


# ---------------------------------------------------------------------------
# Card config
# ---------------------------------------------------------------------------

@dataclass
class PlayoffsCardConfig(CardConfig):
    show_logos: bool      = True
    show_scores: bool     = True
    show_seeds: bool      = True
    show_timestamp: bool  = False
    season: int           = 0

    title_bg: str         = "#1a3a5c"
    title_fg: str         = "#FFFFFF"
    game_box_bg: str      = "#FFFFFF"
    game_box_border: str  = "#1a3a5c"
    winner_bg: str        = "#D4EDDA"
    loser_fg: str         = "#999999"
    connector_color: str  = "#1a3a5c"
    text_color: str       = "#111111"
    round_label_fg: str   = "#1a3a5c"
    champion_bg: str      = "#D4AF37"
    footer_color: str     = "#888888"


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

class PlayoffsCardRenderer:

    TITLE_H_PCT   = 0.10
    FOOTER_H_PCT  = 0.06
    PAD_X         = 18    # outer left/right padding
    PAD_Y         = 12    # body top/bottom padding
    COL_GAP       = 28    # horizontal gap between round columns
    ROUND_LBL_H   = 22    # reserved height for round label above games
    TEAM_ROW_H    = 22    # height of each team row inside a game box (at 150 dpi)
    NOTE_H        = 16    # height reserved below game box for bowl name

    def render(
        self,
        bracket: PlayoffBracket,
        config: PlayoffsCardConfig,
        working_dir: str,
    ) -> Image.Image:
        img  = config.new_canvas()
        draw = ImageDraw.Draw(img)

        W = config.width_px
        H = config.height_px

        scale    = config.dpi / 150
        note_h   = max(10, round(self.NOTE_H     * scale))
        lbl_h    = max(14, round(self.ROUND_LBL_H * scale))
        col_gap  = max(8,  round(self.COL_GAP    * scale))
        pad_x    = max(8,  round(self.PAD_X      * scale))
        pad_y    = max(4,  round(self.PAD_Y      * scale))

        title_h  = round(H * self.TITLE_H_PCT)
        footer_h = round(H * self.FOOTER_H_PCT) if config.show_timestamp else 0

        self._draw_title(draw, bracket, config, W, title_h, scale)

        body_y = title_h + pad_y
        body_h = H - title_h - footer_h - pad_y * 2

        rounds = bracket.rounds()
        if not rounds:
            font = get_font(max(12, round(14 * scale)))
            draw.text((pad_x, body_y + 20), "No bracket data available.",
                      font=font, fill=config.text_color)
            if config.show_timestamp:
                self._draw_footer(draw, bracket, config, H - footer_h, footer_h, pad_x, scale)
            return img

        sorted_rounds = sorted(rounds.keys())
        n_cols        = len(sorted_rounds)
        max_games     = max(len(rounds[r]) for r in sorted_rounds)

        # column width (equal)
        total_gap = col_gap * (n_cols - 1)
        col_w     = (W - pad_x * 2 - total_gap) // n_cols

        # Slot height — divide available body into max_games equal rows
        usable_h  = body_h - lbl_h - pad_y
        cell_h    = usable_h / max_games

        # Game box: two team rows + a note strip inside the border
        # Base two-row height from slot
        two_row_h = max(round(self.TEAM_ROW_H * 2 * scale),
                        round(cell_h * 0.62))
        if two_row_h % 2 != 0:
            two_row_h += 1
        team_row   = two_row_h // 2
        # Note strip inside the box (bowl game name)
        note_row_h = max(10, round(team_row * 0.40))
        game_box_h = two_row_h + note_row_h
        # note_h (used for centre_y calc below — no longer drawn outside)
        note_h     = 0

        # Build winner routing: (rnd_a, slot_a) -> (rnd_b, slot_b)
        routing = self._compute_routing(rounds, sorted_rounds)

        # Compute visual order: (rnd_num, slot) -> visual_index (0-based)
        # so that each R1 winner sits at the same vertical position as its R2 target
        vis_order = self._compute_visual_order(rounds, sorted_rounds, routing)

        # Centre_y for every game using visual_order
        centres: dict[tuple, int] = {}
        for rnd_num in sorted_rounds:
            n    = len(rounds[rnd_num])
            step = max_games / n
            for g in rounds[rnd_num]:
                vi = vis_order.get((rnd_num, g.slot), g.slot - 1)
                cy = body_y + lbl_h + (vi + 0.5) * step * cell_h
                centres[(rnd_num, g.slot)] = round(cy)

        # column x positions
        col_xs: dict[int, int] = {}
        for idx, rnd_num in enumerate(sorted_rounds):
            col_xs[rnd_num] = pad_x + idx * (col_w + col_gap)

        lw = max(2, round(2 * scale))   # connector line width

        # Pass 1: game boxes + round labels
        for rnd_num in sorted_rounds:
            _games    = rounds[rnd_num]
            _cx       = col_xs[rnd_num]
            _lbl      = _games[0].round_name if _games else f"Round {rnd_num}"
            _lbl_font = get_font(max(8, round(lbl_h * 0.60)), bold=True)
            _lb       = draw.textbbox((0, 0), _lbl, font=_lbl_font)
            _lw_px    = _lb[2] - _lb[0]
            draw.text((_cx + (col_w - _lw_px) // 2, body_y + 2), _lbl,
                      font=_lbl_font, fill=config.round_label_fg)
            for _game in _games:
                _cy    = centres[(rnd_num, _game.slot)]
                _box_y = _cy - game_box_h // 2
                self._draw_game_box(draw, img, _game, config,
                                    _cx, _box_y, col_w, game_box_h, team_row,
                                    note_row_h, working_dir, scale)

        # Pass 2: connector lines using winner routing
        for i in range(len(sorted_rounds) - 1):
            rnd_a   = sorted_rounds[i]
            rnd_b   = sorted_rounds[i + 1]
            right_a = col_xs[rnd_a] + col_w
            left_b  = col_xs[rnd_b]
            mid_x   = (right_a + left_b) // 2
            n_a     = len(rounds[rnd_a])
            n_b     = len(rounds[rnd_b])

            if n_a == n_b:
                # 1:1 routing — line from each source game to its routed target
                for g_a in rounds[rnd_a]:
                    ya     = centres[(rnd_a, g_a.slot)]
                    target = routing.get((rnd_a, g_a.slot))
                    yb     = centres[target] if target else ya
                    if ya == yb:
                        draw.line([(right_a, ya), (left_b, yb)],
                                  fill=config.connector_color, width=lw)
                    else:
                        # Angled connector via midpoint
                        draw.line([(right_a, ya), (mid_x, ya)],
                                  fill=config.connector_color, width=lw)
                        draw.line([(mid_x, ya), (mid_x, yb)],
                                  fill=config.connector_color, width=lw)
                        draw.line([(mid_x, yb), (left_b, yb)],
                                  fill=config.connector_color, width=lw)
            else:
                # N:1 routing — Y-connectors grouped by target slot
                groups: dict[int, list[int]] = {}  # slot_b -> [centre_y from rnd_a]
                for g_a in rounds[rnd_a]:
                    target = routing.get((rnd_a, g_a.slot))
                    if target:
                        groups.setdefault(target[1], []).append(centres[(rnd_a, g_a.slot)])

                for g_b in rounds[rnd_b]:
                    yb    = centres[(rnd_b, g_b.slot)]
                    group = sorted(groups.get(g_b.slot, []))
                    if not group:
                        continue
                    y_top = group[0]
                    y_bot = group[-1]
                    for ya in group:
                        draw.line([(right_a, ya), (mid_x, ya)],
                                  fill=config.connector_color, width=lw)
                    draw.line([(mid_x, y_top), (mid_x, y_bot)],
                              fill=config.connector_color, width=lw)
                    draw.line([(mid_x, yb), (left_b, yb)],
                              fill=config.connector_color, width=lw)

        if config.show_timestamp:
            self._draw_footer(draw, bracket, config,
                              H - footer_h, footer_h, pad_x, scale)
        return img

    # ------------------------------------------------------------------
    # Routing helpers
    # ------------------------------------------------------------------

    def _compute_routing(
        self, rounds: dict, sorted_rounds: list
    ) -> dict[tuple, tuple]:
        """Build (rnd_a, slot_a) -> (rnd_b, slot_b) based on which team advances."""
        routing: dict[tuple, tuple] = {}
        for i in range(len(sorted_rounds) - 1):
            rnd_a = sorted_rounds[i]
            rnd_b = sorted_rounds[i + 1]
            # All teams that appear in round B
            teams_b: dict[str, int] = {}
            for g in rounds[rnd_b]:
                teams_b[g.home_team] = g.slot
                teams_b[g.away_team] = g.slot

            for g_a in rounds[rnd_a]:
                # Determine which team advances (winner if complete, else either)
                advancing: Optional[str] = None
                if g_a.completed and g_a.home_score is not None and g_a.away_score is not None:
                    advancing = g_a.home_team if g_a.home_score > g_a.away_score else g_a.away_team
                else:
                    for t in (g_a.home_team, g_a.away_team):
                        if t in teams_b:
                            advancing = t
                            break

                if advancing and advancing in teams_b:
                    routing[(rnd_a, g_a.slot)] = (rnd_b, teams_b[advancing])

        return routing

    def _compute_visual_order(
        self, rounds: dict, sorted_rounds: list, routing: dict[tuple, tuple]
    ) -> dict[tuple, int]:
        """
        Assign a visual_index (0-based) to each (rnd_num, slot) so that
        games that feed into the same next-round game are vertically adjacent,
        producing a bracket with no unnecessary line crossings.

        Works backwards from the last round:
        - Last round: visual_index = slot-1 (keep API order)
        - Earlier rounds: visual_index = index of their routing target, expanded
        """
        vis: dict[tuple, int] = {}

        # Seed the last round
        last = sorted_rounds[-1]
        for g in sorted(rounds[last], key=lambda x: x.slot):
            vis[(last, g.slot)] = g.slot - 1

        # Build reverse routing: (rnd_b, slot_b) -> [(rnd_a, slot_a)]
        rev: dict[tuple, list[tuple]] = {}
        for (ra, sa), (rb, sb) in routing.items():
            rev.setdefault((rb, sb), []).append((ra, sa))

        # Walk backwards
        for i in range(len(sorted_rounds) - 2, -1, -1):
            rnd_a = sorted_rounds[i]
            rnd_b = sorted_rounds[i + 1]

            # Sort round B games by their visual index
            games_b_sorted = sorted(
                rounds[rnd_b],
                key=lambda g: vis.get((rnd_b, g.slot), g.slot - 1),
            )

            n_a = len(rounds[rnd_a])
            n_b = len(rounds[rnd_b])

            if n_a == n_b:
                # 1:1: each round-A game gets the same visual index as its target
                for g_a in rounds[rnd_a]:
                    target = routing.get((rnd_a, g_a.slot))
                    if target:
                        vis[(rnd_a, g_a.slot)] = vis.get(target, g_a.slot - 1)
                    else:
                        vis[(rnd_a, g_a.slot)] = g_a.slot - 1
            else:
                # N:1 halving: feeders of each round-B game get consecutive indices
                counter = 0
                for g_b in games_b_sorted:
                    feeders = sorted(
                        rev.get((rnd_b, g_b.slot), []), key=lambda x: x[1]
                    )
                    for (ra, sa) in feeders:
                        vis[(ra, sa)] = counter
                        counter += 1

        return vis

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------

    def _draw_title(self, draw, bracket, config, W, title_h, scale):
        draw.rectangle([0, 0, W - 1, title_h - 1], fill=config.title_bg)

        pad        = max(8, round(self.PAD_X * scale))
        fmt_label  = "12-Team CFP" if bracket.format == "12-team" else "CFP"
        title_text = f"{bracket.season} {fmt_label} Playoff Bracket"
        font       = get_font(max(12, round(title_h * 0.38)), bold=True)
        tb         = draw.textbbox((0, 0), title_text, font=font)
        ty         = (title_h - (tb[3] - tb[1])) // 2

        if bracket.champion:
            # Split: title left-of-centre, champion right
            cf     = get_font(max(9, round(title_h * 0.28)), bold=True)
            c_text = f"\U0001f3c6  {bracket.champion}"
            cb     = draw.textbbox((0, 0), c_text, font=cf)
            cw, ch = cb[2]-cb[0], cb[3]-cb[1]
            draw.text((pad, ty), title_text, font=font, fill=config.title_fg)
            draw.text((W - cw - pad, (title_h - ch) // 2),
                      c_text, font=cf, fill=config.champion_bg)
        else:
            # No champion yet — centre the title
            draw.text(((W - (tb[2]-tb[0])) // 2, ty),
                      title_text, font=font, fill=config.title_fg)

    # ------------------------------------------------------------------
    # Game box
    # ------------------------------------------------------------------

    def _draw_game_box(
        self, draw, img, game: PlayoffGame, config,
        x, y, box_w, box_h, team_row, note_h, working_dir, scale,
    ):
        # Determine winner
        winner: Optional[str] = None
        if game.completed and game.home_score is not None and game.away_score is not None:
            winner = game.home_team if game.home_score >= game.away_score else game.away_team

        # Box fill + explicit thick outline
        border_w = max(2, round(2 * scale))
        draw.rectangle([x, y, x + box_w - 1, y + box_h - 1],
                       fill=config.game_box_bg)
        # Draw each side of the border individually for consistent thickness
        draw.rectangle(
            [x, y, x + box_w - 1, y + box_h - 1],
            outline=config.game_box_border,
            width=border_w,
        )

        # Mid-line between the two team rows
        mid_y = y + team_row
        draw.line([(x + border_w, mid_y), (x + box_w - border_w - 1, mid_y)],
                  fill=config.game_box_border, width=1)

        # Team rows: away on top, home on bottom
        for row_idx, (team, seed, score) in enumerate([
            (game.away_team, game.away_seed, game.away_score),
            (game.home_team, game.home_seed, game.home_score),
        ]):
            ry = y + row_idx * team_row
            is_winner = (team == winner)
            row_bg    = config.winner_bg if is_winner else config.game_box_bg
            draw.rectangle([x + border_w, ry + (border_w if row_idx == 0 else 0),
                             x + box_w - border_w - 1, ry + team_row - 1], fill=row_bg)

            txt_color = config.text_color if (is_winner or winner is None) else config.loser_fg
            font_sz   = max(7, round(team_row * 0.50))
            font      = get_font(font_sz, bold=is_winner)
            font_sm   = get_font(max(6, round(team_row * 0.38)))

            inner_x = x + border_w + 4
            inner_y = ry + max(1, (team_row - font_sz) // 2)

            # Seed badge
            if config.show_seeds and seed is not None:
                seed_txt = str(seed)
                sb  = draw.textbbox((0, 0), seed_txt, font=font_sm)
                sw  = sb[2] - sb[0]
                sy  = ry + (team_row - (sb[3] - sb[1])) // 2
                draw.text((inner_x, sy), seed_txt, font=font_sm, fill=config.loser_fg)
                inner_x += sw + 3

            # Logo
            if config.show_logos:
                logo_sz = max(10, team_row - 4)
                from app.data.logo_cache import get_logo, slugify
                logo   = get_logo(slugify(team), logo_sz, working_dir)
                if logo:
                    ly = ry + (team_row - logo_sz) // 2
                    img.paste(logo, (inner_x, ly), logo)
                    inner_x += logo_sz + 3

            # Team name — truncate to fit, leave room for score
            name      = team
            score_str = str(score) if (config.show_scores and score is not None) else ""
            if score_str:
                sc_b    = draw.textbbox((0, 0), score_str, font=font)
                score_w = (sc_b[2] - sc_b[0]) + 6
            else:
                score_w = 0

            avail = x + box_w - 2 - inner_x - score_w
            while name:
                nb = draw.textbbox((0, 0), name, font=font)
                if (nb[2] - nb[0]) <= avail:
                    break
                name = name[:-2].rstrip() + "…"

            draw.text((inner_x, inner_y), name, font=font, fill=txt_color)

            # Score (right-aligned)
            if score_str:
                sc_b = draw.textbbox((0, 0), score_str, font=font)
                sx   = x + box_w - (sc_b[2] - sc_b[0]) - 4
                sy   = ry + (team_row - (sc_b[3] - sc_b[1])) // 2
                draw.text((sx, sy), score_str, font=font, fill=txt_color)

        # Bowl name inside box — a thin strip at the bottom
        if game.notes:
            note_y  = y + team_row * 2   # top of the note strip
            note_bg = "#F5F5F5"
            draw.rectangle([x + border_w, note_y,
                             x + box_w - border_w - 1, y + box_h - border_w - 1],
                           fill=note_bg)
            # thin separator line above the note strip
            draw.line([(x + border_w, note_y), (x + box_w - border_w - 1, note_y)],
                      fill=config.game_box_border, width=1)
            nf   = get_font(max(6, round(note_h * 0.58)), italic=True)
            note = game.notes
            avail_note = box_w - border_w * 2 - 6
            while True:
                nb = draw.textbbox((0, 0), note, font=nf)
                if (nb[2] - nb[0]) <= avail_note or len(note) <= 4:
                    break
                note = note[:-2].rstrip() + "…"
            nb = draw.textbbox((0, 0), note, font=nf)
            nw = nb[2] - nb[0]
            nh = nb[3] - nb[1]
            draw.text(
                (x + (box_w - nw) // 2,
                 note_y + (note_h - nh) // 2),
                note, font=nf, fill=config.footer_color,
            )

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------

    def _draw_footer(self, draw, bracket, config, fy, footer_h, pad_x, scale):
        W    = config.width_px
        font = get_font(max(8, round(footer_h * 0.38)), italic=True)
        ts   = bracket.as_of.strftime("Data as of: %b %d, %Y  %I:%M %p")
        bb   = draw.textbbox((0, 0), ts, font=font)
        tw, th = bb[2]-bb[0], bb[3]-bb[1]
        draw.text(((W - tw) // 2, fy + (footer_h - th) // 2),
                  ts, font=font, fill=config.footer_color)
