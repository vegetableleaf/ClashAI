"""Opt-in inference choices. No gate, tower-HP, card-priority or reward rules."""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
import math
import re
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F

# 1x | 2x | OT boundaries (obs_contract DOUBLE_ELIXIR_S / OVERTIME_S); the epsilon absorbs tick * 0.05 rounding.
PHASE_EDGES_S = (120.0, 180.0)
# Lead-approved X-Bow reach (xbow_reach_public.json, 13038.4048 milli), centre to centre, plus 1e-4 tile slack.
XBOW_REACH_TILES = 13.0384 + 1e-4
# Enemy crown towers in the board frame (me at the bottom), tiles: K, L (x < 0.5), R -- BoardState.towers[3:6] order.
# RoyaleSim: side-0 king (9000, 3000), princesses (3500, 6500) / (14500, 6500); mirrored for side 1.
ENEMY_TOWERS_TILES = ((9.0, 3.0), (3.5, 6.5), (14.5, 6.5))


@dataclass(frozen=True)
class DecisionOptions:
    card_choice: str = 'argmax'
    card_ratio: float = 0.7
    card_T: float = 1.0
    spell_aim: str = 'argmax'
    tau_phase: Optional[tuple] = None       # (1x, 2x, OT) gate thresholds; None = the single cfg tau
    xbow_class: str = 'argmax'
    xbow_class_floor: float = 0.2
    log_aim: str = 'argmax'
    log_air: str = 'off'                    # 'retarget' / 'block': a Log whose roll corridor holds only flyers (log_air_cell)
    gate_decode: str = 'threshold'          # 'hazard' / 'hazard_below_tau': execute the gate's learned play RATE (W4)
    gate_hazard_min_elixir: float = 0.0     # hazard draws only at own elixir >= this (0 = everywhere)
    gate_hazard_quiet: bool = False         # hazard draws only with no enemy unit on the board (public bodies)
    gate_hazard_threatened: float = 0.0     # hazard draws ALSO while a tower of mine lost HP within this many s (0 = off)
    gate_hazard_threat_radius: float = 0.0  # ... or while an enemy unit is within this many tiles of my alive tower
    lethal_rocket: str = 'off'
    lethal_log: str = 'off'                 # 'on': the lethal finisher also uses the Log (rides on lethal_rocket's mode)
    barrel_lane: str = 'off'                # owner 10-25 'on': Knight / Ice Wizard / Skeletons / Tornado answering an enemy
                                            # Goblin Barrel go to ITS lane (log_barrel's fix ported to the troop answers)
    lethal_quiet: float = 0.0               # owner 10-25: > 0 = the finisher skips a princess whose HP dropped in the last
                                            # this many s (an X-Bow / troop already finishing it: the Rocket would be overkill)
    xbow_dead_lane: str = 'allow'           # 'block': no X-Bow cell that reaches only the king / a destroyed princess
    rocket_dead_target: str = 'allow'       # 'block': no Rocket on a fallen tower / the king with nothing alive in it
    tau_threatened: Optional[float] = None  # gate threshold while threatened (tau_threat_state); None = the phase tau
    rocket_value: float = 0.0               # > 0: Rocket a clump of >= this much enemy elixir value on my half (rocket_value_choice)
    rocket_value_mode: str = 'cost'         # 'damage': the share of each body's value the Rocket destroys; 'kill': only bodies it kills
    rocket_value_min_y: float = 16.0        # the blast centre must be at board y >= this (16 = my half; 21+ = near my towers)
    rocket_value_max_left: float = 99.0     # no fire when the bodies in the blast would KEEP more than this much value after the Rocket
    rocket_value_threat: str = 'off'        # 'on': only while a tower of mine is under fire with an enemy body near it (tau_threat_state)
    rocket_tornado: str = 'off'             # 'on': + Rocket and Tornado on a clump too spread for one blast; 'only': without the lone rule;
                                            # 'rocket_only': SIM measurement ablation (the same Rocket, no Tornado)
    tornado_river: str = 'off'              # 'on' (owner 10-14): a Tornado cannot drag GROUND troops over the river (RoyaleSim 0.1.33
                                            # status.ATTRACT_WATER_EDGE): combo aim + own-effects look-ahead hold them at the bank;
                                            # 'full' (10-17): + both banks and the bridge edges, from the pull's path (pull_river_ends)
    rocket_tornado_window: str = 'v1'       # 'measured' (10-17): pull-landing window + Rocket flight re-fit (PULL_LANDS_V2, FLIGHT_V2_OFFSET)
    rocket_tornado_order: str = 'rocket'    # 'either' (10-17): also Tornado first + the Rocket as its follow-up, when that window is wider
    rocket_tornado_lone: str = 'skip'       # 'best' (10-17): a clump one Rocket covers gets the combo if its pull gathers more value, else
                                            # that lone Rocket (COMBO_GAIN_MIN; 'only' mode used to leave it with neither play); 'combo':
                                            # the same combo, but no lone Rocket (the model plays where the pull adds nothing);
                                            # 'margin' (10-18): the combo only where no lone blast holds V AND the pull adds >= the
                                            # Tornado's elixir (COMBO_MARGIN_ELIXIR) over the best lone blast, else the model plays
    rocket_value_towers: str = 'off'        # 'on' (10-17): an alive enemy PRINCESS in the blast adds ROCKET_TOWER_VALUE elixir
    rocket_tornado_lead: str = 'off'        # 'drift' (10-17): the pull is judged where enemy-half / bridge bodies will have walked to
                                            # when the Tornado lands (combo_drift); my-half bodies stay (mostly engaged at my towers)
    rocket_value_hitbox: str = 'centre'     # 'edge': a body is in the blast when its hitbox touches the radius
    rocket_value_lead: str = 'off'          # 'on' / 'drift' / 'blend': aim at where the bodies will be when the Rocket lands
    rocket_value_idle: str = 'off'          # 'on': only at a decision where the model itself would not play (displaces nothing)
    rocket_value_min_elixir: float = 0.0    # fire only with at least this much elixir (the Rocket leaves the rest)
    card_levels: Optional[tuple] = None     # ((catalog name, level), ...) for the lethal rules; None = my tower level

    def __post_init__(self):
        if self.card_choice not in ('argmax', 'filtered'):
            raise ValueError('card_choice must be argmax or filtered')
        if not math.isfinite(self.card_ratio) or not 0 < self.card_ratio <= 1:
            raise ValueError('card_ratio must be in (0, 1]')
        if not math.isfinite(self.card_T) or self.card_T <= 0:
            raise ValueError('card_T must be positive and finite')
        if self.spell_aim not in ('argmax', 'rocket_area'):
            raise ValueError('spell_aim must be argmax or rocket_area')
        if self.tau_phase is not None:
            taus = tuple(float(t) for t in self.tau_phase)
            if len(taus) != 3 or not all(math.isfinite(t) and 0 <= t <= 1 for t in taus):
                raise ValueError('tau_phase must be three thresholds in [0, 1] (1x, 2x, OT)')
            object.__setattr__(self, 'tau_phase', taus)
        if self.xbow_class not in ('argmax', 'class_sample'):
            raise ValueError('xbow_class must be argmax or class_sample')
        if not math.isfinite(self.xbow_class_floor) or not 0 <= self.xbow_class_floor <= 0.5:
            raise ValueError('xbow_class_floor must be in [0, 0.5]')
        if self.log_aim not in ('argmax', 'log_barrel'):
            raise ValueError('log_aim must be argmax or log_barrel')
        if self.log_air not in ('off', 'retarget', 'block'):
            raise ValueError('log_air must be off, retarget or block')
        if self.gate_decode not in ('threshold', 'hazard', 'hazard_below_tau', 'timing_head'):
            raise ValueError('gate_decode must be threshold, hazard or hazard_below_tau (or timing_head)')
        if not math.isfinite(self.gate_hazard_min_elixir) or not 0 <= self.gate_hazard_min_elixir <= 10:
            raise ValueError('gate_hazard_min_elixir must be in [0, 10]')
        for k in ('gate_hazard_threatened', 'gate_hazard_threat_radius'):
            if not math.isfinite(getattr(self, k)) or getattr(self, k) < 0:
                raise ValueError(f'{k} must be finite and >= 0')
        if self.barrel_lane not in ('off', 'on'):
            raise ValueError('barrel_lane must be off or on')
        if not math.isfinite(self.lethal_quiet) or self.lethal_quiet < 0:
            raise ValueError('lethal_quiet must be finite and >= 0 (0 = off)')
        if self.lethal_rocket not in ('off', 'ot', 'ot_behind'):
            raise ValueError('lethal_rocket must be off, ot or ot_behind')
        if self.xbow_dead_lane not in ('allow', 'block'):
            raise ValueError('xbow_dead_lane must be allow or block')
        if self.rocket_dead_target not in ('allow', 'block'):
            raise ValueError('rocket_dead_target must be allow or block')
        if self.lethal_log not in ('off', 'on'):
            raise ValueError('lethal_log must be off or on')
        if self.tau_threatened is not None and not (math.isfinite(self.tau_threatened) and 0 <= self.tau_threatened <= 1):
            raise ValueError('tau_threatened must be a threshold in [0, 1]')
        if not math.isfinite(self.rocket_value) or self.rocket_value < 0:
            raise ValueError('rocket_value must be finite and >= 0')
        for k, ok in (('rocket_value_mode', ('cost', 'damage', 'kill')), ('rocket_value_hitbox', ('centre', 'edge')),
                      ('rocket_value_lead', ('off', 'on', 'drift', 'blend')), ('rocket_value_idle', ('off', 'on')),
                      ('rocket_value_threat', ('off', 'on')), ('rocket_tornado', ('off', 'on', 'only', 'rocket_only')),
                      ('tornado_river', ('off', 'on', 'full')), ('rocket_tornado_window', ('v1', 'measured')),
                      ('rocket_tornado_order', ('rocket', 'either')), ('rocket_tornado_lone', ('skip', 'best', 'combo', 'margin')),
                      ('rocket_value_towers', ('off', 'on')), ('rocket_tornado_lead', ('off', 'drift'))):
            if getattr(self, k) not in ok:
                raise ValueError(f'{k} must be one of {ok}')
        if not math.isfinite(self.rocket_value_min_elixir) or not 0 <= self.rocket_value_min_elixir <= 10:
            raise ValueError('rocket_value_min_elixir must be in [0, 10]')
        if not math.isfinite(self.rocket_value_min_y) or not 0.0 <= self.rocket_value_min_y <= 32.0:
            raise ValueError('rocket_value_min_y must be in [0, 32] tiles (16 = my half; below 16 reaches onto the enemy half)')
        if self.rocket_value_min_y < 16.0 and self.tornado_river == 'on':
            raise ValueError("tornado_river on holds only enemy-bank bodies (a centre on my half): use 'full' with rocket_value_min_y < 16")
        if self.rocket_tornado_order == 'either' and self.rocket_tornado == 'rocket_only':
            raise ValueError('rocket_tornado_order either has no rocket_only ablation (its Rocket may be the follow-up)')
        if not math.isfinite(self.rocket_value_max_left) or self.rocket_value_max_left < 0:
            raise ValueError('rocket_value_max_left must be finite and >= 0 (99 = off)')
        if self.rocket_tornado != 'off' and self.rocket_value <= 0:
            raise ValueError('rocket_tornado needs rocket_value > 0 (its V)')
        if self.card_levels is not None:
            object.__setattr__(self, 'card_levels', parse_card_levels(self.card_levels))

    @property
    def active(self):
        return (self.card_choice != 'argmax' or self.spell_aim != 'argmax' or self.tau_phase is not None
                or self.xbow_class != 'argmax' or self.log_aim != 'argmax' or self.gate_decode != 'threshold'
                or self.lethal_rocket != 'off' or self.xbow_dead_lane != 'allow' or self.rocket_dead_target != 'allow'
                or self.tau_threatened is not None or self.log_air != 'off' or self.rocket_value > 0
                or self.rocket_tornado != 'off' or self.barrel_lane != 'off')

    @property
    def uses_barrels(self):
        """The Goblin Barrel landing points are read (log_barrel's aim; log_air's exclusion)."""
        return self.log_aim != 'argmax' or self.log_air != 'off' or self.barrel_lane != 'off'


def options_from_config(cfg=None):
    cfg = cfg or {}
    return DecisionOptions(**{k: cfg[k] for k in DecisionOptions.__dataclass_fields__ if k in cfg})


def add_arguments(parser):
    parser.add_argument('--card-choice', choices=('argmax', 'filtered'), default='argmax')
    parser.add_argument('--card-ratio', type=float, default=0.7)
    parser.add_argument('--card-T', type=float, default=1.0)
    parser.add_argument('--spell-aim', choices=('argmax', 'rocket_area'), default='argmax',
                        help='rocket_area: maximise learned cell probability inside the catalog Rocket radius')
    parser.add_argument('--tau-phase', type=float, nargs=3, default=None, metavar=('T1X', 'T2X', 'TOT'),
                        help='play iff P(play) > the phase threshold: 1x t<120 s, 2x 120-180 s, OT t>=180 s '
                             '(replaces --tau / the plain tau for the gate; anti-stall unchanged)')
    parser.add_argument('--xbow-class', choices=('argmax', 'class_sample'), default='argmax',
                        help='class_sample: draw offensive/defensive X-Bow class from the cell mass, then argmax inside it')
    parser.add_argument('--xbow-class-floor', type=float, default=0.2,
                        help='class_sample draws only when the minority class mass >= this; else the majority class')
    parser.add_argument('--log-aim', choices=('argmax', 'log_barrel'), default='argmax',
                        help='log_barrel: with an enemy Goblin Barrel in flight (visible target), aim the Log / '
                             'Barbarian Barrel at the cells whose rolling corridor covers its landing point, '
                             'highest learned cell probability among them; else the plain argmax')
    parser.add_argument('--log-air', choices=('off', 'retarget', 'block'), default='off',
                        help='owner 2026-10-09 (a Log on air troops): when the Log the model plays has only flyers in its roll '
                             'corridor (no ground unit, building or enemy tower; a Goblin Barrel landing in it exempts it), '
                             'retarget: keep the Log but aim it at the cell whose corridor holds the most enemy ground '
                             'elixir, else at the lower-HP enemy princess (the lethal-Log cast cell), else unchanged; '
                             'block: do not play it (WAIT, no other card). Lethal Logs are never touched')
    parser.add_argument('--gate-decode', choices=('threshold', 'hazard', 'hazard_below_tau'), default='threshold',
                        help='hazard: per decision play with probability 1 - exp(-rate(p) * step), rate = the play '
                             'rate the gate learned on 2-s WAIT rows (gate_rate); hazard_below_tau: play iff p > tau '
                             'as before, else the same draw')
    parser.add_argument('--gate-hazard-min-elixir', type=float, default=0.0,
                        help='hazard draws only when my elixir >= this (0 = at any elixir)')
    parser.add_argument('--gate-hazard-quiet', action='store_true',
                        help='hazard draws only when no enemy unit is on the board')
    parser.add_argument('--gate-hazard-threatened', type=float, default=0.0, metavar='SECONDS',
                        help='hazard draws ALSO (OR with --gate-hazard-min-elixir) while one of my towers lost HP within '
                             'the last SECONDS of decision-board time (public tower HP); 0 = off')
    parser.add_argument('--gate-hazard-threat-radius', type=float, default=0.0, metavar='TILES',
                        help='hazard draws ALSO while an enemy unit is within TILES of one of my alive towers; 0 = off')
    parser.add_argument('--lethal-rocket', choices=('off', 'ot', 'ot_behind'), default='off',
                        help='ot: in overtime (t >= 180 s, the tau_phase edge) play Rocket NOW, whatever the gate, at the '
                             'centre of an alive enemy PRINCESS tower whose HP <= my Rocket crown-tower damage (lower HP '
                             'first; never the king), when Rocket is in hand and affordable; else unchanged. ot_behind: '
                             'also in regulation while the opponent has more crowns, if the Rocket can still land '
                             'before 3:00')
    parser.add_argument('--lethal-log', choices=('off', 'on'), default='off',
                        help='on: the --lethal-rocket finisher (same phase / crown / landing rules; inert when it is off) '
                             'also uses the Log: an alive enemy PRINCESS with HP <= my Log crown-tower damage gets the '
                             'Log, cast on my side at (tower x, y 17.5 tiles) so its roll reaches the tower; preferred over '
                             'the Rocket when both finish')
    parser.add_argument('--barrel-lane', choices=('off', 'on'), default='off',
                        help='owner 2026-10-25: on = a Knight / Ice Wizard / Skeletons / Tornado the model places on MY half while '
                             'an enemy Goblin Barrel lands (in flight: its visible target) or its goblins stand on my half, in ONE lane '
                             'only, is moved to that lane: the model\'s best cell within BARREL_LANE_TILES of the barrel / goblins '
                             '(--log-aim log_barrel\'s lane fix for the troop answers); a placement on the enemy half, both lanes '
                             'threatened or already the right lane = unchanged; off = unchanged')
    parser.add_argument('--lethal-quiet', type=float, default=0.0, metavar='SEC',
                        help='owner 2026-10-25: the --lethal-rocket / --lethal-log finisher skips an enemy princess whose public '
                             'HP dropped within the last SEC s of decision snapshots (something else -- a locked X-Bow, a troop -- '
                             'is already damaging it, so the finishing spell would be overkill); 0 = off (unchanged)')
    parser.add_argument('--xbow-dead-lane', choices=('allow', 'block'), default='allow',
                        help='block (owner 2026-10-08, never the king): the X-Bow never takes a cell within reach of the '
                             'enemy king or of a DESTROYED enemy princess that reaches no alive enemy princess '
                             '(xbow_dead_lane_cells); it aims at its best remaining cell. With no cell left the X-Bow is '
                             'not chosen and the next card by the model ranking is; nothing is forced')
    parser.add_argument('--rocket-dead-target', choices=('allow', 'block'), default='allow',
                        help='block (owner 2026-10-08 "rocket on a fallen tower"; never the king): a Rocket whose usual '
                             'aim covers a DESTROYED enemy tower (dead >= 60 ticks) with no alive princess or enemy body, '
                             'or the enemy king with no enemy body (unless it finishes the king), is re-aimed at the best '
                             'cell with a real target (body / alive princess) by the same scoring, else NOT cast: the '
                             'next card by the model ranking, else WAIT (rocket_target_cells). Unblocked aims unchanged')
    parser.add_argument('--card-levels', nargs='+', default=None, metavar='NAME=LEVEL',
                        help='LIVE ONLY (the SIM decision path ignores it: its cards are level 11): my card levels for '
                             'the lethal Rocket / Log rules (tower damage, in-flight guard, the --rocket-dead-target '
                             'king-lethal exception), e.g. Rocket=16 Log=15 (list BOTH lethal spells); names from '
                             'the card catalog, each level within its range; a card not listed falls back to my tower '
                             'level (the default for every card)')
    parser.add_argument('--tau-threatened', type=float, default=None, metavar='X',
                        help='while threatened (one of my towers lost HP within the last 2 s of board time AND an enemy '
                             'unit is within 8 tiles of that tower, public) the gate threshold is X instead of the phase '
                             'tau: play iff P(play) > X. Card and cell stay the model own choices; default off')
    parser.add_argument('--rocket-value', type=float, default=0.0, metavar='V',
                        help='owner 2026-10-09 (a Lava Hound push never Rocketed): with Rocket in hand and affordable and nothing '
                             'pending, play it when the best blast centred on MY half holds >= V elixir of enemy value, aimed by '
                             'the rocket_area logic among the cells that cover that whole clump; the lethal rules keep priority. '
                             'The sub-options below change how the value is counted. 0 = off')
    parser.add_argument('--rocket-value-mode', choices=('cost', 'damage', 'kill'), default='cost',
                        help='cost: a body is worth card cost / bodies x hp fraction; damage: x the share of its hp the Rocket '
                             'takes instead (min(Rocket damage, hp now) / max hp), so a Giant counts for a third and a Skeleton '
                             'Dragon pair in full; kill: only the bodies the Rocket kills outright count, at their full value')
    parser.add_argument('--rocket-value-threat', choices=('off', 'on'), default='off',
                        help='on: only while one of my towers lost public HP within the last 2 s AND an enemy body is within 8 tiles of '
                             'it (the --tau-threatened state): the clump is attacking, not merely crossing the river')
    parser.add_argument('--rocket-tornado', choices=('off', 'on', 'only', 'rocket_only'), default='off',
                        help='owner 2026-10-09 (needs --rocket-value V and the pipelined follow-up tap, GenPilot.plan_follow_up): on a clump '
                             'too spread for one Rocket blast (the Tornado pull holds >= V, no single blast does) with Rocket and Tornado '
                             'in hand and both affordable: Rocket at the pull centre now, the Tornado there as a follow-up tap timed so the '
                             'Rocket lands inside the pull (rocket_tornado_plan). on = alongside the lone rule, only = the combo without the lone rule, '
                             'rocket_only = SIM measurement ablation: the same Rocket at the same moment, no Tornado (not for live)')
    parser.add_argument('--tornado-river', choices=('off', 'on', 'full'), default='off',
                        help='owner 2026-10-14: a Tornado cannot drag GROUND troops over the river (held at the bank; air crosses; '
                             'bridges are walkable). on: the Rocket+Tornado aim counts an enemy-bank ground body only where the river '
                             'holds it, and the own-effects look-ahead stops ground bodies at the bank. full (10-17): the aim follows each '
                             'ground body\'s pull path instead (either bank, and a body on a bridge pulled sideways stops at the bridge '
                             'edge, RoyaleSim per-axis water stop) and counts it only if the blast covers where it ends. off = unchanged')
    parser.add_argument('--rocket-tornado-window', choices=('v1', 'measured'), default='v1',
                        help='owner 2026-10-17: measured = the Rocket must land 7..24 ticks after the Tornado (7..40 at a centre on my side '
                             'past the bridge, y >= 19) and its flight is d / 0.35 + 0.5 ticks (fork36 sweep, L74/combo/fit_window.py); '
                             'v1 = 12..33 and round(d / .35) + 2 (unchanged)')
    parser.add_argument('--rocket-tornado-order', choices=('rocket', 'either'), default='rocket',
                        help='owner 2026-10-17: either = also Tornado now and the Rocket as its follow-up tap, whichever order leaves the '
                             'wider timing window (short flights near my towers); rocket = Rocket first only (unchanged)')
    parser.add_argument('--rocket-tornado-lone', choices=('skip', 'best', 'combo', 'margin'), default='skip',
                        help='owner 2026-10-17: best = where one Rocket blast already holds V, the combo when its pull gathers more '
                             'value than that blast (> COMBO_GAIN_MIN elixir), else that lone Rocket; skip = no combo there (unchanged; '
                             'with --rocket-tornado only such a clump got neither play); combo = that combo, but never the lone Rocket '
                             '(10-17 SIM: lone Rockets of best lost net 12 of 110 changed matches); margin (10-18) = the combo only '
                             'where no lone blast holds V and the pull adds >= 3 elixir (the Tornado) over the best lone blast, else '
                             'the model plays')
    parser.add_argument('--rocket-tornado-lead', choices=('off', 'drift'), default='off',
                        help='owner 2026-10-17: drift = judge the pull where the bodies on the enemy half or a bridge will have walked to '
                             'when the Tornado lands (decision -> Tornado deploy: 26 ticks + the follow-up gap): ground bodies toward '
                             'their nearest bridge, then along it; air straight at my side; my half stays put. off = unchanged')
    parser.add_argument('--rocket-value-towers', choices=('off', 'on'), default='off',
                        help='owner 2026-10-17: on = an alive enemy PRINCESS tower inside the Rocket blast adds ROCKET_TOWER_VALUE elixir to '
                             'the value (lone and combo); the enemy king is never in a blast or a Tornado (doctrine). off = unchanged')
    parser.add_argument('--rocket-value-max-left', type=float, default=99.0, metavar='L',
                        help='no fire when the bodies in the best blast would still hold more than L elixir of value after the '
                             'Rocket (a Golem keeps 5.7 of its 8): the Rocket then only strips the support and the elixir it '
                             'cost is missing against the tank. 99 = off')
    parser.add_argument('--rocket-value-min-y', type=float, default=16.0, metavar='Y',
                        help='the blast centre must be at board y >= Y tiles (me at the bottom, my half starts at 16, my princess '
                             'towers stand at 25.5): a deep centre is short in the air and on a clump already at my towers; '
                             'Y < 16 reaches onto the enemy half (with --tornado-river off or full)')
    parser.add_argument('--rocket-value-hitbox', choices=('centre', 'edge'), default='centre',
                        help='edge: a body is in the blast when its HITBOX touches the radius (centre distance <= radius + its '
                             'collision radius, the RoyaleSim rule); centre: its centre must be inside the radius')
    parser.add_argument('--rocket-value-lead', choices=('off', 'on', 'drift', 'blend'), default='off',
                        help='aim at where the bodies will be when the Rocket lands (flight from my king tower): on = each body moved '
                             'at the velocity measured from the last 2 s of decisions; drift = every body walks toward my side at its '
                             'catalog speed; blend = the measured velocity where it moves, the drift otherwise')
    parser.add_argument('--rocket-value-idle', choices=('off', 'on'), default='off',
                        help='on: only at a decision where the model itself would not play (gate WAIT after the hazard draw), so '
                             'the Rocket displaces no play of the model')
    parser.add_argument('--rocket-value-min-elixir', type=float, default=0.0, metavar='E',
                        help='fire only with at least E elixir (the Rocket leaves E - 6 for the defence); 0 = any affordable')
    parser.add_argument('--decision-seed', type=int, default=0,
                        help='separate seeded card-choice stream; recorded with each experiment')


def config_from_args(args):
    cfg = {k: getattr(args, k) for k in DecisionOptions.__dataclass_fields__}
    options_from_config(cfg)  # fail before loading models / starting a match
    if args.decision_seed < 0:
        raise ValueError('decision_seed must be nonnegative')
    return {**cfg, 'decision_seed': int(args.decision_seed)}


def filtered_probabilities(logits, allowed, ratio=0.7, temperature=1.0):
    """Exact expected categorical distribution; filter BEFORE temperature.

    Row shapes may be [slots] or [batch, slots]. All-unaffordable rows are zero.
    Probability ratios are exp(logit - top_logit), so no preliminary softmax is
    needed. There is deliberately no extra confidence threshold.
    """
    DecisionOptions(card_ratio=ratio, card_T=temperature)
    x = np.asarray(logits, dtype=np.float64)
    allowed = np.asarray(allowed, dtype=bool)
    if x.shape != allowed.shape or x.ndim not in (1, 2):
        raise ValueError('logits and allowed must have matching one- or two-dimensional shapes')
    if np.any(allowed & (np.isnan(x) | np.isposinf(x))):
        raise ValueError('invalid affordable card logits')
    masked = np.where(allowed, x, -np.inf)
    valid = np.isfinite(masked).any(axis=-1, keepdims=True)
    top = np.where(valid, masked.max(axis=-1, keepdims=True), 0.0)
    candidates = allowed & np.isfinite(masked) & ((masked - top) >= math.log(ratio))
    weights = np.exp(np.where(candidates, (masked - top) / temperature, -np.inf))
    return weights / np.maximum(weights.sum(axis=-1, keepdims=True), np.finfo(float).tiny)


def choose_slot(logits, allowed, options, rng=None, *, playing=True):
    """Return an affordable slot, or -1. WAIT and singleton choices consume no RNG."""
    allowed = np.asarray(allowed, dtype=bool)
    if not allowed.any():
        return -1
    if torch.is_tensor(logits):
        masked = logits.masked_fill(~torch.as_tensor(allowed, device=logits.device), -torch.inf)
        top = int(masked.argmax())
    else:
        top = int(np.where(allowed, logits, -np.inf).argmax())
    if options.card_choice == 'argmax' or not playing:
        return top
    if rng is None:
        raise ValueError('filtered card choice requires a per-match RNG')
    values = logits.detach().cpu().numpy() if torch.is_tensor(logits) else logits
    probabilities = filtered_probabilities(values, allowed, options.card_ratio, options.card_T)
    if np.count_nonzero(probabilities) == 1:
        return top
    if not probabilities.any():
        raise ValueError('no finite affordable card logits')
    return int(rng.choice(len(probabilities), p=probabilities))


@lru_cache(maxsize=1)
def rocket_radius_tiles():
    from .public_geometry import constants
    radius = float(constants()['rocket_radius']) / 1000.0
    if not math.isfinite(radius) or radius <= 0:
        raise ValueError('invalid catalog Rocket radius')
    return radius


def rocket_area_scores(probabilities):
    """Disk mass on a 36x64 half-tile lattice; zero padding, no edge renormalisation.

    Floor and lattice grids share the same relative half-tile distances. Using
    board-normalised x/y distances here would incorrectly stretch the disk.
    """
    from .model_v3 import GRID_X, GRID_Y
    if probabilities.ndim != 2 or probabilities.shape[-1] != GRID_X * GRID_Y:
        raise ValueError('Rocket area aim requires [batch, 2304] cell probabilities')
    radius = rocket_radius_tiles()
    pad = math.ceil(radius * 2)
    offsets = torch.arange(-pad, pad + 1, dtype=probabilities.dtype, device=probabilities.device) / 2
    disk = ((offsets[:, None] ** 2 + offsets[None, :] ** 2) <= radius ** 2).to(probabilities.dtype)
    return F.conv2d(probabilities.reshape(-1, 1, GRID_Y, GRID_X), disk[None, None],
                    padding=pad).flatten(1)


def phase_index(t_sec):
    """0 = 1x (t < 120 s), 1 = 2x (120 <= t < 180 s), 2 = OT (t >= 180 s)."""
    t = np.asarray(t_sec, dtype=np.float64) + 1e-6
    return (t >= PHASE_EDGES_S[0]).astype(np.int64) + (t >= PHASE_EDGES_S[1])


def gate_taus(options, tau, t_sec, n):
    """Per-row gate threshold: the scalar ``tau`` unless ``tau_phase`` is set."""
    if options.tau_phase is None:
        return tau
    if t_sec is None or len(t_sec) != n:
        raise ValueError('tau_phase requires the decision time of every row')
    return np.asarray(options.tau_phase)[phase_index(t_sec)]


# dataset.build_replay: one WAIT row per 40 ticks (2 s), none within 20 ticks (1 s) before a play.
WAIT_STRIDE_S, PLAY_WINDOW_S = 2.0, 1.0


def gate_rate(p):
    """Play rate (1/s) implied by the gate's row probability. For a pro playing at rate r, the row odds are
    plays / WAIT rows = r S exp(r W) (S = WAIT_STRIDE_S, W = PLAY_WINDOW_S): inverted by Newton (convex, monotone)."""
    p = np.clip(np.asarray(p, dtype=np.float64), 1e-9, 1 - 1e-9)
    o = p / (1 - p)
    r = np.log1p(o / WAIT_STRIDE_S)                       # >= the root, so Newton descends monotonically
    for _ in range(40):
        e = np.exp(r * PLAY_WINDOW_S)
        r = r - (WAIT_STRIDE_S * r * e - o) / (WAIT_STRIDE_S * e * (1 + PLAY_WINDOW_S * r))
    return np.maximum(r, 0.0)


# P2 opponents (REPORT_opponents 2, "Decoding in the SIM"): gate_decode 'timing_head' = the decode of a checkpoint with
# the slot timing head (model_gen SLOT_TICKS): at every 10-tick grid tick draw Bernoulli(h_s), then the tick inside the
# slot; at that tick the card and the cell are drawn (temperature T; the timing head is always T = 1). No gate, tau or
# anti-stall. e1_eval runs it (timing_decide_batch / SelfPlaySide); ``decide`` refuses it.
TIMING_SLOT_TICKS = 10


def timing_slot_draw(hazard_logit: float, tick_logits, rng):
    """Stage 1 of timing_head, one row: -> the tick inside the slot of a play (0..9), or None (no play this slot)."""
    h = 1.0 / (1.0 + math.exp(-float(hazard_logit)))
    if rng.random() >= h:
        return None
    z = np.asarray(tick_logits, dtype=np.float64)
    q = np.exp(z - z.max())
    return int(rng.choice(len(q), p=q / q.sum()))


def timing_play_draw(card_logits, allowed, cell_logits_fn, rng, T: float = 1.0):
    """Stage 2 of timing_head, one row at the play tick: -> (slot, cell), or None when no allowed card (no play).
    ``card_logits`` [8] over deck slots, ``cell_logits_fn(slot)`` -> [N_CELLS] logits; both drawn at temperature T."""
    allowed = np.asarray(allowed, dtype=bool)
    if not allowed.any():
        return None
    z = np.where(allowed, np.asarray(card_logits, dtype=np.float64) / T, -np.inf)
    q = np.exp(z - z.max())
    slot = int(rng.choice(len(q), p=q / q.sum()))
    c = np.asarray(cell_logits_fn(slot), dtype=np.float64) / T
    q = np.exp(c - c.max())
    return slot, int(rng.choice(len(q), p=q / q.sum()))


def hazard_play(p, step_s, rng):
    """One draw: play with probability 1 - exp(-gate_rate(p) * step_s)."""
    if rng is None:
        raise ValueError('hazard gate decoding requires a per-match RNG')
    return bool(rng.random() < -math.expm1(-float(gate_rate(p)) * float(step_s)))


def threat_on(options):
    return options.gate_hazard_threatened > 0 or options.gate_hazard_threat_radius > 0


def tower_threat(options, prev, bs):
    """-> (state, threatened) for gate_hazard_threatened / _threat_radius on one decision's BoardState (my frame).
    ``prev`` = the state this helper returned at the previous decision of the match (None at the first). Threatened =
    one of MY towers' public hp_frac fell since the previous decision at most gate_hazard_threatened s ago (board time
    ``bs.t_sec``), or an enemy unit (side != 0, as enemy_unit_count) is within gate_hazard_threat_radius tiles of an
    alive tower of mine. Idempotent on a repeated board. Both SIM match_kwargs and live_gen_v2 call it."""
    from .obs_contract import _ANCHOR_XY, TILES_X, TILES_Y, TOWER_ORDER
    t, hp = float(bs.t_sec), tuple(tw.hp_frac for tw in bs.towers[:3])
    last = prev[2] if prev else None
    if prev and any(a is not None and b is not None and b < a - 1e-9 for a, b in zip(prev[1], hp)):
        last = t
    threatened = (options.gate_hazard_threatened > 0 and last is not None
                  and t - last <= options.gate_hazard_threatened + 1e-6)
    R = options.gate_hazard_threat_radius
    if R > 0 and not threatened:
        anchors = [_ANCHOR_XY[kl] for kl, tw in zip(TOWER_ORDER, bs.towers[:3]) if tw.alive]
        threatened = any(math.hypot((u.x - x) * TILES_X, (u.y - y) * TILES_Y) <= R
                         for u in bs.units if int(u.side) != 0 for x, y in anchors)
    return (t, hp, last), bool(threatened)


def hazard_draw(options, p, step_s, rng, *, elixir=None, enemy_units=None, threatened=None):
    """The ONE hazard decision for a row where a play is possible and the threshold said wait (SIM decide_batch and
    live_gen_v2 both call it). Scopes: elixir >= gate_hazard_min_elixir OR ``threatened`` (tower_threat, when
    gate_hazard_threatened / _threat_radius is set); no scope set = everywhere. Out of scope, or an enemy unit on the
    board with gate_hazard_quiet -> False without drawing. Missing context for an active scope raises, never a silent
    no-op."""
    if step_s is None:
        raise ValueError('hazard gate decoding requires the decision step (seconds)')
    scopes = []
    if options.gate_hazard_min_elixir > 0:
        if elixir is None:
            raise ValueError('gate_hazard_min_elixir requires the own elixir of every row')
        scopes.append(float(elixir) >= options.gate_hazard_min_elixir)
    if threat_on(options):
        if threatened is None:
            raise ValueError('gate_hazard_threatened / _threat_radius require the tower threat of every row')
        scopes.append(bool(threatened))
    if scopes and not any(scopes):
        return False
    if options.gate_hazard_quiet:
        if enemy_units is None:
            raise ValueError('gate_hazard_quiet requires the enemy unit count of every row')
        if int(enemy_units):
            return False
    return hazard_play(p, step_s, rng)


# --tau-threatened: M4 "frozen under fire" (L74 catalogue): a tower losing HP with an enemy body within 8 tiles of it.
TAU_THREAT_WINDOW_S, TAU_THREAT_RADIUS_TILES = 2.0, 8.0


def tau_threat_state(prev, bs):
    """-> (state, threatened) on one decision's BoardState (my frame). ``prev`` = the state returned at the previous
    decision of the match (None at the first). Threatened = some tower of mine lost public HP within the last
    TAU_THREAT_WINDOW_S of board time (``bs.t_sec``) AND an enemy unit (side != 0, as enemy_unit_count) is within
    TAU_THREAT_RADIUS_TILES of THAT tower. A fallen tower keeps its position. Idempotent on a repeated board."""
    from .obs_contract import _ANCHOR_XY, TILES_X, TILES_Y, TOWER_ORDER
    t, hp = float(bs.t_sec), tuple(tw.hp_frac for tw in bs.towers[:3])
    last = list(prev[1]) if prev else [None] * 3
    if prev:
        for i, (a, b) in enumerate(zip(prev[0], hp)):
            if a is not None and b is not None and b < a - 1e-9:
                last[i] = t
    threatened = False
    enemies = [u for u in bs.units if int(u.side) != 0] if any(
        l is not None and t - l <= TAU_THREAT_WINDOW_S + 1e-6 for l in last) else []
    for l, kl in zip(last, TOWER_ORDER):
        if l is not None and t - l <= TAU_THREAT_WINDOW_S + 1e-6:
            x, y = _ANCHOR_XY[kl]
            threatened = threatened or any(math.hypot((u.x - x) * TILES_X, (u.y - y) * TILES_Y) <= TAU_THREAT_RADIUS_TILES
                                           for u in enemies)
    return (hp, tuple(last)), threatened


def threat_taus(options, tau, threatened):
    """The gate threshold with tau_threatened applied: X on the threatened rows, ``tau`` (scalar or per row) elsewhere."""
    if options.tau_threatened is None:
        return tau
    if threatened is None:
        raise ValueError('tau_threatened requires the threat flag of every row')
    return np.where(np.asarray(threatened, dtype=bool), options.tau_threatened, tau)


def enemy_unit_count(bs):
    """Visible bodies not known to be mine (side 0) on a BoardState: public; an unknown team (-1, live only) counts."""
    return sum(int(u.side) != 0 for u in bs.units)


def is_xbow(name):
    return re.sub(r'[^a-z]', '', str(name).split('@')[0].lower()) in ('xbow', 'xbowevo')


@lru_cache(maxsize=16)
def xbow_offensive_cells(enemy_alive, grid):
    """[2304] bool: the cell centre is within X-Bow reach of an ALIVE enemy tower (K, L, R board-frame order)."""
    from .model_v3 import GRID_X, GRID_Y
    if grid not in ('floor', 'lattice'):
        raise ValueError(f'unknown grid {grid!r}')
    off = 0.5 if grid == 'floor' else 0.0
    c = np.arange(GRID_X * GRID_Y)
    x, y = (c % GRID_X + off) * 18.0 / GRID_X, (c // GRID_X + off) * 32.0 / GRID_Y
    hit = np.zeros(len(c), dtype=bool)
    for alive, (tx, ty) in zip(enemy_alive, ENEMY_TOWERS_TILES):
        if alive:
            hit |= np.hypot(x - tx, y - ty) <= XBOW_REACH_TILES
    return hit


def xbow_dead_lane_cells(enemy_alive, grid):
    """[2304] bool, the cells xbow_dead_lane='block' removes: within X-Bow reach of the enemy king's or a DESTROYED enemy
    princess's position, and of no ALIVE enemy princess (``enemy_alive`` = (K, L, R) in my board frame). With a
    princess down this is the dead lane's lock cell (live 10-05..10-08: 152 of 168 dead-lane X-Bows sat exactly there,
    board y 19.5, reaching nothing) plus every king-only cell; cells that lock the remaining princess and dead-lane
    cells beyond the dead princess's reach (deeper defensive rows) stay. Kings never count as alive targets here."""
    _, left, right = (bool(a) for a in enemy_alive)
    return xbow_offensive_cells((True, True, True), grid) & ~xbow_offensive_cells((False, left, right), grid)


PROBE_XBOW_DAMAGED = 0.95   # an enemy princess counts as damaged below this public hp_frac


def probe_xbow_focus_princess(alive, hp):
    """SIM-ONLY measurement probe (owner 2026-10-15; search_s0 --probe-xbow-focus; NOT a DecisionOptions field, so no
    live parser / LIVE_OPTIONS can carry it). ``alive`` = enemy (K, L, R) alive, ``hp`` = enemy (L, R) hp_frac (None =
    full). -> 1 (L) / 2 (R), the princess offensive X-Bows are concentrated on, or None (no restriction): both alive ->
    the strictly weaker one once either is below PROBE_XBOW_DAMAGED (exact tie -> None); one alive -> it; none -> None."""
    _, al, ar = (bool(a) for a in alive)
    hl, hr = (1.0 if h is None else float(h) for h in hp)
    if al and ar:
        if min(hl, hr) >= PROBE_XBOW_DAMAGED or hl == hr:
            return None
        return 1 if hl < hr else 2
    return 1 if al else 2 if ar else None


def probe_xbow_focus_cell(logits, cell, alive, hp, grid):
    """-> the X-Bow cell under the probe (``cell`` when unchanged). Only an OFFENSIVE cell (reaches an alive enemy tower,
    xbow_offensive_cells) that misses the focus princess moves, to the highest-logit cell reaching the focus princess
    (the class-restricted argmax today's decode takes, masked); defensive cells, a cell already on the focus princess,
    no focus, or no finite focus cell -> ``cell``. Focus cells reach an alive princess, so none is xbow_dead_lane-blocked."""
    focus = probe_xbow_focus_princess(alive, hp)
    if focus is None:
        return cell
    reach = xbow_offensive_cells((False, focus == 1, focus == 2), grid)
    if reach[cell] or not xbow_offensive_cells(tuple(bool(a) for a in alive), grid)[cell]:
        return cell
    masked = logits.masked_fill(~torch.as_tensor(reach, device=logits.device), -torch.inf)
    return int(masked.argmax()) if bool(torch.isfinite(masked).any()) else cell


# ponytail: a body counts as hit when its centre is within the Rocket radius + this slack (no per-card hitbox radii);
# generous on purpose -- a near-miss body keeps the cell allowed, so the block never removes a Rocket that would hit.
ROCKET_BODY_SLACK_TILES = 0.5


def rocket_target_cells(board, grid):
    """-> (blocked, target), [2304] bool each, for rocket_dead_target='block'. ``board`` = (enemy (K, L, R) alive in my
    board frame AFTER the reader-glitch filter (princess_dead_state), enemy body tiles (enemy_body_tiles), the Rocket
    finishes the enemy king (rocket_kills_king)). A blast covers a tower when the cell centre is within the catalog
    Rocket radius + the catalog tower collision radius, a body when within the radius + ROCKET_BODY_SLACK_TILES.
      blocked: no enemy body in the blast, and it covers a DESTROYED enemy tower and no alive princess (owner 10-08:
               "the model cast rocket on a fallen tower"), or it covers the alive enemy KING (owner: never the king),
               unless that Rocket finishes the king (the logged exception).
      target:  an enemy body, an alive enemy princess, or a king the Rocket finishes is in the blast.
    Live 10-05..10-08: 16 of 334 confirmed Rockets (4.8%) were fallen-tower shots (L74/rocket_dead/measure.out)."""
    from .public_geometry import constants
    alive, bodies, kills_king = board
    x, y = cell_centres_tiles(grid)
    radius, radii = rocket_radius_tiles(), constants()['tower_radius']
    over = [np.hypot(x - tx, y - ty) <= radius + radii[k] / 1000.0
            for (tx, ty), k in zip(ENEMY_TOWERS_TILES, ('KingTower', 'PrincessTower', 'PrincessTower'))]
    body = np.zeros(len(x), dtype=bool)
    for bx, by in bodies:
        body |= np.hypot(x - bx, y - by) <= radius + ROCKET_BODY_SLACK_TILES
    princess = (over[1] & bool(alive[1])) | (over[2] & bool(alive[2]))
    dead = (over[1] & (not alive[1])) | (over[2] & (not alive[2])) | (over[0] & (not alive[0]))
    king = over[0] & bool(alive[0])
    blocked = ~body & ((dead & ~princess & ~(king & kills_king)) | (king & (not kills_king)))
    return blocked, body | princess | (king & bool(kills_king))


def rocket_covers_king(cell, grid):
    """The Rocket blast at ``cell`` covers the enemy king's footprint (rocket_target_cells' rule)."""
    from .public_geometry import constants
    x, y = cell_centres_tiles(grid)
    (kx, ky), r = ENEMY_TOWERS_TILES[0], constants()['tower_radius']['KingTower'] / 1000.0
    return bool(math.hypot(x[cell] - kx, y[cell] - ky) <= rocket_radius_tiles() + r)


def enemy_body_tiles(bs):
    """Board tiles (x, y) of the BoardState bodies not known to be mine (enemy_unit_count's rule), for rocket_dead_target."""
    return tuple((float(u.x) * 18.0, float(u.y) * 32.0) for u in bs.units if int(u.side) != 0)


# Reader glitch (verifier 10-09: in 68 of 600 live matches an enemy princess read destroyed for ~10-30 ticks, then alive
# again, 71 times): for rocket_dead_target a princess counts as destroyed only after reading dead this many ticks running.
PRINCESS_DEAD_CONFIRM_TICKS = 60


def princess_dead_state(prev, bs):
    """-> (state, (K, L, R) alive as rocket_dead_target sees it). ``prev`` = the state returned at the previous decision
    of the match (None at the first): per enemy princess, the board tick it first read dead in its current dead run.
    A princess reading dead for < PRINCESS_DEAD_CONFIRM_TICKS (board ticks, bs.t_sec / 0.05) still counts as alive.
    Public alive flags only. SIM match_kwargs and live_gen_v2 call it at every decision."""
    tick = int(round(float(bs.t_sec) / 0.05))
    since = list(prev) if prev else [None, None]
    flags = [bool(t.alive) for t in bs.towers[3:6]]
    eff = [flags[0]]
    for j in (0, 1):
        if flags[j + 1]:
            since[j] = None
        elif since[j] is None:
            since[j] = tick
        eff.append(flags[j + 1] or tick - since[j] < PRINCESS_DEAD_CONFIRM_TICKS)
    return tuple(since), tuple(eff)


def my_rocket_damage(crown_towers, side, levels=None):
    """My Rocket's crown-tower damage from my own tower max HP (lethal_rocket_target's level rule), or None.
    ``levels`` (card_levels, live only): {catalog name: level}; a listed Rocket uses its own level."""
    from .body_identity import level_of_factor
    mine = next((t for t in crown_towers if int(t['side']) == side and t.get('max_hp')), None)
    level = mine and level_of_factor(float(mine['max_hp']) / (4824.0 if mine.get('type') == 'king' else 3052.0))
    if level is None:
        return None
    return tower_damage_or_none(levels['Rocket'] if levels and 'Rocket' in levels else level)


def rocket_kills_king(crown_towers, side, levels=None):
    """True when the alive enemy king's public HP <= my Rocket's crown-tower damage (the never-the-king exception)."""
    damage = my_rocket_damage(crown_towers, side, levels) if levels else my_rocket_damage(crown_towers, side)
    return bool(damage) and any(int(t['side']) != side and t.get('type') == 'king' and not t.get('destroyed')
                                and 0 < t['hp'] <= damage for t in crown_towers)


def xbow_class_choice(logits, offensive, floor, rng):
    """-> (cell, defensive, sampled). D = defensive mass; draw Bernoulli(D) iff min(D, 1-D) >= floor, else the
    majority class; then the argmax cell inside the chosen class. Confident classes consume no RNG."""
    x = logits.detach().double() if torch.is_tensor(logits) else torch.as_tensor(logits, dtype=torch.float64)
    off = torch.as_tensor(np.asarray(offensive, dtype=bool), device=x.device)
    d = float(x.softmax(-1).masked_fill(off, 0).sum().clamp(0, 1))
    sampled = min(d, 1 - d) >= floor
    if sampled:
        if rng is None:
            raise ValueError('xbow class_sample requires a per-match RNG')
        defensive = bool(rng.random() < d)
    else:
        defensive = d > 0.5
    keep = ~off if defensive else off
    return int(x.masked_fill(~keep, -torch.inf).argmax()), defensive, sampled


BARREL_KEY = 'goblin-barrel'      # vocab base key: the evolved barrel and its decoy share it
ROLLING_CARDS = {'log': 'Log', 'thelog': 'Log', 'barblog': 'BarbLog', 'barbarianbarrel': 'BarbLog'}


def rolling_corridor(name):
    """(half-width, half-depth, roll range) in tiles for the Log / Barbarian Barrel, else None."""
    card = ROLLING_CARDS.get(re.sub(r'[^a-z]', '', str(name).split('@')[0].lower()))
    if card is None:
        return None
    from .public_geometry import constants
    return tuple(float(v) / 1000.0 for v in constants()['rolling'][card])


def barrel_landings(projectiles, barrel_id):
    """Enemy Goblin Barrels in flight with a visible target, from the model's own projectile tokens
    (projectile_observation.PROJECTILE_COLS: card, enemy, x, y, target_x, target_y, ...; board-normalised, my
    frame) -> [(target_x, target_y)]. Unknown targets are -1 and are skipped."""
    if barrel_id is None:
        return []
    p = projectiles.detach().cpu().numpy() if torch.is_tensor(projectiles) else np.asarray(projectiles)
    p = p.astype(np.float64).reshape(-1, p.shape[-1])
    keep = (p[:, 0] == barrel_id) & (p[:, 1] == 1) & ((p[:, 4:6] >= 0) & (p[:, 4:6] <= 1)).all(1)
    return [tuple(t) for t in p[keep, 4:6]]


@lru_cache(maxsize=4)
def cell_centres_tiles(grid):
    from .model_v3 import GRID_X, GRID_Y
    if grid not in ('floor', 'lattice'):
        raise ValueError(f'unknown grid {grid!r}')
    off = 0.5 if grid == 'floor' else 0.0
    c = np.arange(GRID_X * GRID_Y)
    return (c % GRID_X + off) * 18.0 / GRID_X, (c // GRID_X + off) * 32.0 / GRID_Y


def log_barrel_cell(logits, corridor, barrels, grid):
    """The cell whose rolling corridor covers the most barrel landing points (covering: |dx| <= half-width and the
    landing lies between half-depth behind the cell and the roll range ahead; my Log rolls toward decreasing board y),
    highest logit among those. None (= keep the plain choice) without a barrel or a finite covering cell.
    Static geometry only: it ignores the barrel's time to impact (tokens carry tti_s) and the Log's travel time.
    UNVALIDATED live (recorded live logs carry no projectile arrays); SIM A/B 192 games: no win benefit. Off by default."""
    if not barrels:
        return None
    half, depth, reach = corridor
    x, y = cell_centres_tiles(grid)
    count = np.zeros(len(x), dtype=np.int64)
    for bx, by in barrels:
        ahead = y - by * 32.0
        count += (np.abs(x - bx * 18.0) <= half) & (ahead >= -depth) & (ahead <= reach)
    if count.max() == 0:
        return None
    keep = torch.as_tensor(count == count.max(), device=logits.device)
    masked = logits.masked_fill(~keep, -torch.inf)
    return int(masked.argmax()) if bool(torch.isfinite(masked).any()) else None


# ---- log_air (owner 2026-10-09: "played log on yet another air troop"; "log should still be cyclable") ----
# The Log hits ground only (catalog Log projectile: aoe_to_air false, aoe_to_ground true). A Log whose roll corridor holds
# only flyers does nothing, but the play can still be right (it cycles the hand), so retarget keeps the cast and re-aims it.
LOG_AIR_UNIT_RADIUS = 0.5       # tiles: a unit is in the corridor when its centre is within this of the rolling box
LOG_AIR_UNKNOWN_VALUE = 0.5     # elixir credited to a ground body the catalog has no card row for (sub-spawns)
LOG_AIR_GROUND_SPAWNERS = ('skeleton_barrel',)   # flyers whose death spawns ground skeletons: exempt, counted as ground (owner 10-09)
LOG_AIR_BLOCKED = -2            # choose_cells result: the Log is not played at all (block mode; the caller WAITs)


@lru_cache(maxsize=1)
def log_air_traits():
    """{vocab id: (flying, ground elixir value)} for every troop / building class. Flying = catalog flying_height > 0
    (the base class for evolution / hero forms; Lava Pups added: a sub-spawn with no card row). A Skeleton Barrel is
    exempt (LOG_AIR_GROUND_SPAWNERS: the Log at its landing hits the skeletons it drops), like a Goblin Barrel in flight. Value = card elixir / body
    count (a Skeleton 1/3, a Tesla 4). A class with no row is ground at LOG_AIR_UNKNOWN_VALUE: an unknown body can only
    make the gate refuse to act, never invent a flyer."""
    import json
    from . import vocab
    from .body_identity import CATALOG
    rows = {}
    for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards']:
        rows.setdefault(vocab.engine_key(c['name']), c)
    out = {}
    for i, name in enumerate(vocab.UNIT_VOCAB):
        if vocab.is_spell(i):
            continue
        c = rows.get(name) or rows.get(vocab.base_key(name))
        out[i] = ((name == 'lava_pups', LOG_AIR_UNKNOWN_VALUE) if c is None else
                  ((c.get('flying_height') or 0) > 0 and vocab.base_key(name) not in LOG_AIR_GROUND_SPAWNERS
                   and not name.endswith('_ability'),
                   float(c['elixir']) / max(int(c.get('count') or 1), 1)))
    return out


@lru_cache(maxsize=1)
def log_air_ground_children():
    """{engine key of a FLYING parent card: {max_hp, ...}} of its bodies that have no vocab class of their own and so
    carry the parent's class (body_identity reason 'child_no_class' and an HP no parent body has: the Phoenix egg, 124 x the level ladder = 317 at
    level 11; the respawned flying Phoenix has the parent's HP and stays air). They are
    GROUND bodies (catalog PhoenixEgg flying_height 0) that a Log hits, but the board shows them as the flying parent."""
    from . import vocab
    from .body_identity import tables
    flying = {vocab.UNIT_VOCAB[i] for i, (f, _) in log_air_traits().items() if f}
    out = {}
    for (parent, _form), by_hp in tables().items():
        if parent not in flying:
            continue
        for hp, idents in by_hp.items():
            if any(x[2] == 'child_no_class' for x in idents) and not any(x[2] == 'parent' for x in idents):
                out.setdefault(parent, set()).add(int(hp))      # not the flying PhoenixNoRespawn: it has the parent's HP
    return out


def log_air_ground_child_tiles(entities, my_side):
    """Tile positions (x, y; my frame) of the enemy bodies in raw engine-shaped ``entities`` (dicts: side, x, y in
    millitiles, name, max_hp: SIM ``state['entities']`` / live ``to_observe(...)['entities']``) that are ground children
    of a flying parent (log_air_ground_children): per BODY by its max HP, not per class. () when there are none."""
    from . import vocab
    from .obs_contract import _engine_xy
    kids = log_air_ground_children()
    out = []
    for e in entities or ():
        if int(e['side']) == int(my_side) or e.get('name') in (None, '-1'):
            continue
        hps = kids.get(vocab.engine_key(str(e['name'])))
        if hps and e.get('max_hp') is not None and float(e['max_hp']) == int(e['max_hp']) and int(e['max_hp']) in hps:
            x, y = _engine_xy(float(e['x']), float(e['y']), int(my_side) == 1)
            out.append((x * 18.0, y * 32.0))
    return tuple(out)


LOG_AIR_CHILD_MATCH_TILES = 0.75    # a ground child (an egg does not move) claims the nearest same-position flyer-class unit


def log_air_board(bs, ground_children=()):
    """(ground, air, towers) of a BoardState's enemy side, in tiles of my frame (the Log's): ground = ((x, y, elixir
    value), ...) troops and buildings (side != 0, as enemy_body_tiles), air = ((x, y), ...), towers = alive enemy
    ((x, y, radius, hp fraction, lane or None for the king), ...). Public data only.
    ``ground_children`` (log_air_ground_child_tiles): tiles of ground bodies that wear a flying parent's class (the Phoenix
    egg); the nearest flying-class unit within LOG_AIR_CHILD_MATCH_TILES of each is ground, not air."""
    traits = log_air_traits()
    ground, air = [], []
    claim = list(ground_children)
    for u in bs.units:
        if int(u.side) == 0 or int(u.cls) not in traits:
            continue
        flying, value = traits[int(u.cls)]
        x, y = float(u.x) * 18.0, float(u.y) * 32.0
        if flying and claim:
            near = min(range(len(claim)), key=lambda k: math.hypot(claim[k][0] - x, claim[k][1] - y))
            if math.hypot(claim[near][0] - x, claim[near][1] - y) <= LOG_AIR_CHILD_MATCH_TILES:
                claim.pop(near)
                flying, value = False, LOG_AIR_UNKNOWN_VALUE
        (air.append((x, y)) if flying else ground.append((x, y, value)))
    from .public_geometry import constants
    radius = constants()['tower_radius']
    towers = tuple((tx, ty, float(radius['KingTower' if t.kind == 'king' else 'PrincessTower']) / 1000.0,
                    1.0 if t.hp_frac is None else float(t.hp_frac), t.lane)
                   for t, (tx, ty) in zip(bs.towers[3:6], ENEMY_TOWERS_TILES) if t.alive)
    return tuple(ground), tuple(air), towers


def _covers(x, y, pts, corridor, pad):
    """[len(x), len(pts)] bool: the point lies in the Log's rolling box cast at (x, y) (it rolls toward decreasing y)."""
    half, depth, reach = corridor
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
    ahead = y[:, None] - pts[None, :, 1]
    return (np.abs(x[:, None] - pts[None, :, 0]) <= half + pad) & (ahead >= -(depth + pad)) & (ahead <= reach + pad)


def log_air_cell(logits, corridor, board, barrels, grid, mode, cell):
    """-> the cell for a Log the model aims at ``cell``: ``cell`` unless its corridor holds a flyer and no ground body,
    building, enemy tower or Goblin Barrel landing (it would hit nothing). Then block -> LOG_AIR_BLOCKED; retarget -> (1)
    the legal cell whose corridor holds the most enemy ground elixir (highest logit among ties), else (2) the cast cell
    of the lower-HP alive enemy princess (lethal_log_cell, tower x at LOG_CAST_Y_TILES: the roll ends at the tower; equal
    HP -> logit), else ``cell``. Legal = finite logit (live masks illegal cells) and y >= LOG_CAST_Y_TILES (a Log is cast
    in my own territory). Static geometry like log_barrel_cell: no travel time, no tap snap."""
    ground, air, towers = board
    x, y = cell_centres_tiles(grid)
    at, pad = slice(cell, cell + 1), LOG_AIR_UNIT_RADIUS
    if (not air or not _covers(x[at], y[at], air, corridor, pad).any()
            or _covers(x[at], y[at], [g[:2] for g in ground], corridor, pad).any()
            or any(_covers(x[at], y[at], [t[:2]], corridor, t[2]).any() for t in towers)
            or _covers(x[at], y[at], [(bx * 18.0, by * 32.0) for bx, by in barrels or ()], corridor, 0.0).any()):
        return cell
    if mode == 'block':
        return LOG_AIR_BLOCKED
    legal = np.isfinite(logits.detach().cpu().numpy()) & (y >= LOG_CAST_Y_TILES - 1e-6)
    best = None
    if ground:
        value = _covers(x, y, [g[:2] for g in ground], corridor, pad) @ np.array([g[2] for g in ground])
        if (value[legal] > 0).any():
            best = legal & (value >= value[legal].max() - 1e-9)
    if best is None:
        chip = [(t[3], lethal_log_cell(t[4], grid)) for t in towers if t[4] is not None]
        chip = [(hp, c) for hp, c in chip if legal[c]]
        if not chip:
            return cell
        best = np.zeros(len(x), dtype=bool)
        best[[c for hp, c in chip if hp == min(h for h, _ in chip)]] = True
    return int(logits.masked_fill(~torch.as_tensor(best, device=logits.device), -torch.inf).argmax())


def choose_cells(logits, card_names, options, *, rngs=None, enemy_alive=None, grid=None, barrels=None,
                 rocket_boards=None, log_air_boards=None, log_air_moved=None, barrel_goblins=None):
    """Aim only after card selection. Other cards retain exact argmax behaviour.
    ``barrels`` (log_aim): per row, the enemy Goblin Barrel landing points from ``barrel_landings``.
    xbow_dead_lane 'block': X-Bow rows lose ``xbow_dead_lane_cells`` before any X-Bow aim; a row with no finite cell
    left returns -1 (the caller then drops that X-Bow and takes the next card). rocket_dead_target 'block': applied
    AFTER the usual Rocket aim (rocket_dead_target_choice; ``rocket_boards``: per row, rocket_target_cells' board)."""
    result = logits.argmax(dim=-1)
    if options.xbow_dead_lane == 'block':
        if len(card_names) != len(logits):
            raise ValueError('one card identity required per cell-logit row')
        logits = logits.clone()
        for i, name in enumerate(card_names):
            if not is_xbow(name):
                continue
            if enemy_alive is None or grid is None:
                raise ValueError('xbow_dead_lane requires enemy tower states and the grid')
            blocked = xbow_dead_lane_cells(tuple(bool(a) for a in enemy_alive[i]), grid)
            logits[i] = logits[i].masked_fill(torch.as_tensor(blocked, device=logits.device), -torch.inf)
            result[i] = logits[i].argmax() if bool(torch.isfinite(logits[i]).any()) else -1
    if options.xbow_class == 'class_sample':
        if len(card_names) != len(logits):
            raise ValueError('one card identity required per cell-logit row')
        for i, name in enumerate(card_names):
            if not is_xbow(name) or result[i] < 0:
                continue
            if enemy_alive is None or grid is None or rngs is None:
                raise ValueError('xbow class_sample requires enemy tower states, the grid and per-row RNGs')
            offensive = xbow_offensive_cells(tuple(bool(a) for a in enemy_alive[i]), grid)
            result[i] = xbow_class_choice(logits[i], offensive, options.xbow_class_floor, rngs[i])[0]
    if options.log_aim == 'log_barrel':
        if len(card_names) != len(logits):
            raise ValueError('one card identity required per cell-logit row')
        for i, name in enumerate(card_names):
            corridor = rolling_corridor(name)
            if corridor is None:
                continue
            if barrels is None or grid is None:
                raise ValueError('log_barrel requires the per-row barrel landing points and the grid')
            cell = log_barrel_cell(logits[i], corridor, barrels[i], grid)
            if cell is not None:
                result[i] = cell
    if options.log_air != 'off':
        if len(card_names) != len(logits):
            raise ValueError('one card identity required per cell-logit row')
        for i, name in enumerate(card_names):
            corridor = rolling_corridor(name) if is_log(name) else None
            if corridor is None or result[i] < 0:
                continue
            if log_air_boards is None or grid is None:
                raise ValueError('log_air requires the per-row enemy board and the grid')
            cell = log_air_cell(logits[i], corridor, log_air_boards[i], None if barrels is None else barrels[i],
                                grid, options.log_air, int(result[i]))
            if cell != int(result[i]):
                result[i] = cell
                if log_air_moved is not None:       # the rows the option changed (a log tag; no effect on the decision)
                    log_air_moved.append(i)
    if options.spell_aim != 'argmax':
        if len(card_names) != len(logits):
            raise ValueError('one card identity required per cell-logit row')
        rocket_rows = [i for i, name in enumerate(card_names) if str(name).lower() == 'rocket']
        if rocket_rows:
            ids = torch.as_tensor(rocket_rows, device=logits.device)
            selected = logits[ids]
            mass = rocket_area_scores(selected.softmax(dim=-1))
            maxima = mass == mass.amax(dim=-1, keepdim=True)
            # Mass first, local probability second, first grid index last.
            result[ids] = selected.masked_fill(~maxima, -torch.inf).argmax(dim=-1)
    if options.rocket_dead_target == 'block':
        rocket_dead_target_choice(result, logits, card_names, options, rocket_boards, grid)
    if options.barrel_lane == 'on':
        for i, name in enumerate(card_names):
            if not is_barrel_answer(name) or result[i] < 0:
                continue
            if grid is None:
                raise ValueError('barrel_lane requires the grid')
            pts = [(bx * 18.0, by * 32.0) for bx, by in (barrels[i] if barrels is not None else [])]
            pts += list(barrel_goblins[i]) if barrel_goblins is not None else []
            cell = barrel_lane_cell(logits[i], pts, int(result[i]), grid)
            if cell is not None:
                result[i] = cell
    return result


# ---- barrel_lane (owner 2026-10-25: "the model's log response to enemy goblin barrel follows the correct lane, but its troop
# responses are still wonky: sometimes it plays knight, ice wizard, tornado, or skeletons on the wrong side") ----
BARREL_ANSWERS = ('knight', 'icewizard', 'skeletons', 'tornado')
BARREL_GOBLIN_KEYS = ('goblins', 'goblin_barrel', 'goblin_gang')   # the barrel's goblins (and their class aliases)
BARREL_LANE_TILES = 6.0          # the answer lands within this of the barrel's landing / its goblins
MY_HALF_Y_TILES = 16.0           # my frame: my edge is y = 32, the river y = 16


def is_barrel_answer(name):
    return re.sub(r'[^a-z]', '', str(name).split('@')[0].lower()) in BARREL_ANSWERS


def barrel_goblin_tiles(bs):
    """(x, y) tiles (my frame) of enemy goblins standing on MY half of a BoardState (public bodies)."""
    from . import vocab
    out = []
    for u in bs.units:
        if int(u.side) == 0 or not 0 <= int(u.cls) < len(vocab.UNIT_VOCAB):
            continue
        if vocab.base_key(vocab.UNIT_VOCAB[int(u.cls)]) in BARREL_GOBLIN_KEYS and float(u.y) * 32.0 > MY_HALF_Y_TILES:
            out.append((float(u.x) * 18.0, float(u.y) * 32.0))
    return tuple(out)


def barrel_lane_cell(logits, points, chosen, grid):
    """-> the model's best cell within BARREL_LANE_TILES of the barrel / goblin ``points`` on my half, or None (keep the
    choice): the chosen cell is on the enemy half, no point is on my half, the points span both lanes, or the choice is
    already in their lane."""
    x, y = cell_centres_tiles(grid)
    if y[chosen] <= MY_HALF_Y_TILES:
        return None
    pts = [(px, py) for px, py in points if py > MY_HALF_Y_TILES]
    lanes = {px < 9.0 for px, _ in pts}
    if len(lanes) != 1 or (x[chosen] < 9.0) in lanes:
        return None
    d = np.min([np.hypot(x - px, y - py) for px, py in pts], axis=0)
    keep = torch.as_tensor((d <= BARREL_LANE_TILES) & (y > MY_HALF_Y_TILES), device=logits.device)
    masked = logits.masked_fill(~keep, -torch.inf)
    return int(masked.argmax()) if bool(torch.isfinite(masked).any()) else None


def rocket_dead_target_choice(result, logits, card_names, options, rocket_boards, grid):
    """In place on ``result``: a Rocket row whose usual aim is a rocket_target_cells-blocked cell is re-aimed at the
    best TARGET cell (an enemy body / alive princess / a king it finishes in the blast) that is not blocked, scored
    exactly as the usual aim on the UNMASKED board (rocket_area mass, then local logit; or the plain logit), or -1 when
    there is none: the Rocket is then not cast (the caller takes the next card by the model ranking, else WAIT).
    An unblocked aim is left exactly as with the option off."""
    if len(card_names) != len(logits):
        raise ValueError('one card identity required per cell-logit row')
    for i, name in enumerate(card_names):
        if str(name).lower() != 'rocket' or result[i] < 0:
            continue
        if rocket_boards is None or grid is None:
            raise ValueError('rocket_dead_target requires the per-row rocket board and the grid')
        blocked, target = rocket_target_cells(rocket_boards[i], grid)
        if not blocked[int(result[i])]:
            continue
        row = logits[i]
        keep = torch.as_tensor(target & ~blocked, device=row.device) & torch.isfinite(row)
        if not bool(keep.any()):
            result[i] = -1
            continue
        if options.spell_aim == 'rocket_area':
            mass = rocket_area_scores(row.softmax(dim=-1)[None])[0].masked_fill(~keep, -torch.inf)
            keep = keep & (mass == mass.max())
        result[i] = row.masked_fill(~keep, -torch.inf).argmax()


# ---- lethal_rocket (owner 2026-10-08: "always be rocketing a tower it can finish in one rocket if it's overtime") ----
@lru_cache(maxsize=2)
def _rocket_catalog(name='Rocket'):
    import json
    from .body_identity import CATALOG, CALIBRATION
    rocket = next(c for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards'] if c['name'] == name)
    rounding = json.loads(CALIBRATION.read_text(encoding='utf-8'))['combat']['CROWN_TOWER_DAMAGE_ROUNDING']['value']
    return int(rocket['damage']), int(rocket['crown_tower_damage_percent']), rocket['level_scaling'], rounding


@lru_cache(maxsize=1)
def _catalog_cards():
    """{normalised name / display name: catalog card record} (RoyaleSim cards.json)."""
    import json
    from .body_identity import CATALOG
    out = {}
    for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards']:
        for n in (c['name'], c.get('display_name') or ''):
            out.setdefault(re.sub(r'[^a-z]', '', n.lower()), c)
    return out


def parse_card_levels(spec):
    """``--card-levels`` -> sorted ((catalog name, level), ...). ``spec``: 'NAME=LEVEL' strings, (name, level) pairs or
    a {name: level} dict (a JSON config). Unknown names, repeats and levels outside the card's catalog range raise."""
    items = spec.items() if isinstance(spec, dict) else (s.split('=', 1) if isinstance(s, str) else s for s in spec)
    out = {}
    for item in items:
        if len(item) != 2:
            raise ValueError(f'card_levels entries are NAME=LEVEL, got {item!r}')
        name, level = item
        card = _catalog_cards().get(re.sub(r'[^a-z]', '', str(name).split('@')[0].lower()))
        if card is None:
            raise ValueError(f'card_levels: {name!r} is not a catalog card')
        try:
            level = int(level)
        except (TypeError, ValueError):
            raise ValueError(f'card_levels: {name}={level!r} is not an integer level') from None
        ls = card.get('level_scaling')
        if not ls:
            raise ValueError(f"card_levels: {card['name']} has no level table in the catalog")
        if not (1 <= level - ls['relative_level'] <= ls['level_count']
                and 0 <= level - ls['base_level'] < len(ls['multiplier_percent_by_level'])):
            raise ValueError(f"card_levels: {card['name']} has no level {level}")
        if card['name'] in out:
            raise ValueError(f"card_levels: {card['name']} given twice")
        out[card['name']] = level
    return tuple(sorted(out.items()))


def tower_damage_or_none(level, name='Rocket'):
    """``rocket_tower_damage`` for the live / SIM rules: None instead of a ValueError when the card has no such level.
    MEASURED live (L73/lethal_rocket/level8_scan.out): a lower-level account's King (princess 2352 / king 3768 HP)
    reads as level 8 in 2,912 of 152,711 decisions (10-08 20:20-20:53), and the Log (Legendary) starts at level 9 --
    the unguarded call raised out of GenPilot.decide, and live_play does not catch it (the match is abandoned)."""
    try:
        return rocket_tower_damage(level, name)
    except ValueError:
        return None


@lru_cache(maxsize=32)
def rocket_tower_damage(level, name='Rocket'):
    """My Rocket's crown-tower damage at unified card ``level``: RoyaleSim catalog damage floor(580 x ladder / 100)
    (rocket_teaching.scaled_stat's table), then its 23 % under calibration combat.CROWN_TOWER_DAMAGE_ROUNDING
    (ceil_kept_share). Level 15 = 497 = MEASURED live (live_play_20261008_131352 t4304: 1092 -> 595); level 11 = 342.
    ``name='Log'``: 105 x ladder, 13 % -> level 15 = 51, level 11 = 35 = MEASURED live (1,270 / 175 enemy-princess HP
    drops of exactly 51 / 35 after a confirmed Log, archive 10-01..09, L73/lethal_rocket/log_timing.out)."""
    base, pct, ls, rounding = _rocket_catalog(name)
    local, step = int(level) - ls['relative_level'], int(level) - ls['base_level']
    if not 1 <= local <= ls['level_count'] or not 0 <= step < len(ls['multiplier_percent_by_level']):
        raise ValueError(f'{name} has no level {level}')
    n = base * int(ls['multiplier_percent_by_level'][step]) // 100 * pct
    if rounding == 'ceil_kept_share':
        return -(-n // 100)
    if rounding == 'floor':
        return n // 100
    raise ValueError(f'unknown crown-tower rounding {rounding!r}')


def lethal_rocket_target(crown_towers, side, card='Rocket', own=None, t_sec=None, levels=None, skip=()):
    """The alive ENEMY PRINCESS my Rocket finishes in one hit, lowest HP first -> dict(lane (my frame), hp, damage,
    level), else None. ``crown_towers``: raw ``episode.crown_towers`` rows (side, type, x, y in 1/1000 tile, hp, max_hp;
    live_mem.to_observe / RoyaleSim raw()). My card level = my own tower max HP (from_engine's level factor: level 11
    = 3052 princess / 4824 king -> body_identity.level_of_factor); Rocket assumed at that level. Kings never qualify.
    ``own`` (lethal_log on): my accepted plays -> a princess my own Rocket / Log in flight will finish is skipped.
    ``levels`` (card_levels): {catalog name: level}; a listed card uses its own level, any other my tower level."""
    from .body_identity import level_of_factor
    from .obs_contract import _engine_xy
    mine = next((t for t in crown_towers if int(t['side']) == side and t.get('max_hp')), None)
    level = mine and level_of_factor(float(mine['max_hp']) / (4824.0 if mine.get('type') == 'king' else 3052.0))
    if level is None:
        return None
    tower_level = level                              # in-flight spells: their own listed level, else THIS (never
    if levels and card in levels:                   # the evaluated card's level -- verifier: an unlisted Log costed
        level = levels[card]                        # at Rocket=16's level held a lethal Rocket back)
    damage, best = tower_damage_or_none(level, card), None
    if damage is None:                              # no such card level (e.g. a level-8 King: Log starts at 9): no fire
        return None
    covered = (in_flight_damage(own, t_sec, tower_level, enemy_princess_hps(crown_towers, side), levels=levels)
               if levels else in_flight_damage(own, t_sec, level, enemy_princess_hps(crown_towers, side))) if own else {}
    for t in crown_towers:
        if int(t['side']) == side or t.get('type') != 'princess' or t.get('destroyed') or not 0 < t['hp'] <= damage:
            continue
        x, _ = _engine_xy(float(t['x']), float(t['y']), side == 1)
        if covered.get('L' if x < .5 else 'R', 0) >= t['hp']:
            continue                                # my own spell already on its way finishes it
        if ('L' if x < .5 else 'R') in skip:
            continue                                # lethal_quiet: something else is damaging it right now
        if best is None or t['hp'] < best['hp']:
            best = dict(lane='L' if x < .5 else 'R', hp=int(t['hp']), damage=damage, level=level)
    if best is not None and card != 'Rocket':
        best['card'] = card
    return best


@lru_cache(maxsize=8)
def lethal_rocket_cell(lane, grid):
    """The ``grid`` cell at the enemy princess tower's centre, my frame (model_tower.anchors(): opp L = 4, opp R = 5)."""
    from .model_tower import anchors
    from .model_v3 import cell_label
    return int(cell_label(torch.tensor(anchors()[4 if lane == 'L' else 5]), grid))


# ot_behind landing cutoff: a regulation Rocket counts only if it hits before regulation ends (tick 3600, 180 s; a
# crown lead there ends the match). From the model-board time (decision tick + the 26-tick look-ahead = the SIM landing
# tick under action delay 26; live MEASURED tap -> hand rotation min 24 / median 26-27 ticks) the Rocket still flies
# from my king to the princess: 23.16 tiles / 350 milli per tick (catalog speed, lead) = 66 ticks; MEASURED live
# 10-05..09: 129 of 171 tower hits land 60-80 ticks after the hand rotation (L73/lethal_rocket/timing.out).
# Later fires cannot land before 3:00 and are skipped. ponytail: one flight time for both princesses (same distance).
ROCKET_FLIGHT_TICKS = 66
REGULATION_END_TICK = 3600
# lethal_log: the Log may only be cast in my own troop territory (catalog can_deploy_on_enemy_side false; RoyaleSim
# SpellPlacement::TroopTerritory), so it is cast at (tower x, 17.5 tiles) -- the forward-most own-territory row, a tile
# centre (no tap snap) -- and rolls 10.1 tiles forward (ProjectileRange 10100; half-width 1.95, half-depth 0.6): its end
# box reaches y 6.8, inside the princess's 1-tile collision circle at 6.5 (x margin 2.95). FORWARD MARGIN < 1 tile: a
# cast at y <= 18.2 still reaches (0.7 tile behind 17.5); MEASURED live, casts at y 19.5 hit 0 of 54. MEASURED live:
# casts at (3.5 | 14.5, 17.5) are the bot's commonest tower Logs and hit (553 / 563 HP drops of 35/51). Hit time after
# landing: 3 tiles airborne at 0.36 tile/tick (9 ticks, spells.SPELL_AS_DEPLOY_LAUNCH_MODEL) + the landing tick + 47
# roll steps of 0.2 tile until the front edge meets the tower = 57 ticks; MEASURED live hand rotation -> HP drop median
# 62 (snapshots every ~10 ticks: an upper bound).
LOG_CAST_Y_TILES = 17.5
LOG_HIT_TICKS = 57
# lethal_log in-flight guard (verifier 2026-10-09: Rocket then Log at one tower, and Log then a wasted Rocket): my own
# ACCEPTED Rocket / Log (public: my own play log -- live GenPilot.past, SIM Match.done_plays) counts as in flight from its
# landing until its hit time + the 26-tick look-ahead + this margin, measured to the decision's model-board time.
IN_FLIGHT_MARGIN_TICKS = 20


def enemy_princess_hps(crown_towers, side):
    """{'L' | 'R' (my frame): HP} of the alive enemy princesses in raw ``episode.crown_towers`` rows (public)."""
    from .obs_contract import _engine_xy
    out = {}
    for t in crown_towers:
        if int(t['side']) != side and t.get('type') == 'princess' and not t.get('destroyed') and t['hp'] > 0:
            out['L' if _engine_xy(float(t['x']), float(t['y']), side == 1)[0] < .5 else 'R'] = int(t['hp'])
    return out


def recently_hit(history, tick, window_ticks):
    """lethal_quiet: the lanes ('L' / 'R', my frame) whose enemy princess HP NOW (the snapshot at ``tick``) is below any
    snapshot from the last ``window_ticks`` (``record_hp`` history, one per decision) -> set. No earlier snapshot in the window
    = no evidence = not hit (the finisher may fire). ponytail: decision-snapshot resolution (live decides every few ticks)."""
    now = next((h for t, h in reversed(history) if t == tick), None) if history else None
    if now is None:
        return set()
    out = set()
    for t, hps in history:
        if tick - window_ticks <= t < tick:
            out |= {k for k, v in now.items() if hps.get(k, v) > v}
    return out


def hp_after(history, tick):
    """The FIRST ``enemy_princess_hps`` snapshot at or after raw ``tick`` (a spell's landing) from [(raw tick, hps)],
    else None. Verifier v4: a snapshot from BEFORE the landing can predate another of my spells' hit (185400: the Log's
    pre-play snapshot 345 HP, my Rocket's hit 345 -> 3 two ticks later, the Log confirmed at 4170) and so credit that
    damage to this spell. After the landing nothing of mine but the spell itself is still due on that tower."""
    best = None
    for t, hps in history:
        if t >= tick and (best is None or t < best[0]):
            best = (t, hps)
    return None if best is None else best[1]


# Release (verifier A4): a spell counts as HIT only when the tower lost >= its damage since the landing AND the board
# time has passed a conservative earliest hit -- landing + its nominal hit ticks (Rocket 66, Log 57) - this margin
# (MEASURED live spread ~+-10 ticks: L73/lethal_rocket/timing.out, log_timing.out), on a raw-tick lower bound
# (model-board time - the largest look-ahead, 26). Another source's damage before that no longer releases it.
RELEASE_MARGIN_TICKS = 10
MAX_LOOKAHEAD_TICKS = 26
# HP history kept: every snapshot since the oldest landing still inside its in-flight window (raw ticks; a spell older
# than this no longer counts), not a fixed count -- 64 snapshots at a decision every ~2 ticks spanned only ~128 ticks.
LETHAL_HIST_TICKS = ROCKET_FLIGHT_TICKS + MAX_LOOKAHEAD_TICKS + IN_FLIGHT_MARGIN_TICKS + 8


def record_hp(history, tick, hps):
    """Append this decision's enemy-princess HP (one entry per raw tick) and drop entries older than the window.
    -> the (possibly new) history list; a tick going backwards (a new match) restarts it."""
    if history is None or (history and history[-1][0] > tick):
        history = []
    if not history or history[-1][0] != tick:
        history.append((tick, hps))
    while history and history[0][0] < tick - LETHAL_HIST_TICKS:
        history.pop(0)
    return history


def in_flight_damage(own, t_sec, level, hp_now=None, levels=None):
    """{'L' | 'R': tower damage} of my own Rockets / Logs still due to hit an enemy princess. ``own``: [(card name, x, y
    in my 0-1 frame, landing t_sec[, enemy_princess_hps at or before the landing])]. Rocket: aim within its radius + the
    princess radius of the tower centre; Log: the tower inside its roll corridor (half-width / roll range + half-depth,
    each + the princess radius).
    A spell stops counting once it has HIT (verifier v2: counting it after the hit refused finishing spells): the tower
    has lost at least that spell's damage since its landing (``hp_now`` vs ``hp_after`` the landing: the first public
    snapshot at or after it, None = not seen yet = still counts) AND the conservative earliest hit has passed. The live
    confirmation stamp lags the placement by a few ticks and the hit comes >= ~50 ticks after it, so the first snapshot
    after the stamp is still before the hit; the time-window alone stays the upper bound."""
    from .public_geometry import constants
    tr = constants()['tower_radius']['PrincessTower'] / 1000.0
    half, depth, reach = rolling_corridor('Log')
    out = {}
    for name, x, y, land, *before in own:
        before = before[0] if before else None
        rocket = str(name).lower() == 'rocket'
        if not (rocket or is_log(name)):
            continue
        hit = ROCKET_FLIGHT_TICKS if rocket else LOG_HIT_TICKS
        if not 0 <= round((t_sec - land) / 0.05) <= hit + 26 + IN_FLIGHT_MARGIN_TICKS:
            continue
        x, y = x * 18.0, y * 32.0
        for lane, (tx, ty) in zip('LR', ENEMY_TOWERS_TILES[1:]):
            if (math.hypot(x - tx, y - ty) <= rocket_radius_tiles() + tr if rocket else
                    abs(x - tx) <= half + tr and -(depth + tr) <= y - ty <= reach + depth + tr):
                card = 'Rocket' if rocket else 'Log'
                damage = tower_damage_or_none(levels.get(card, level) if levels else level, card)
                if damage is None:                  # unknown level: count the spell as finishing (never a 2nd cast)
                    out[lane] = math.inf
                    continue
                if (before and hp_now and lane in before and lane in hp_now and before[lane] - hp_now[lane] >= damage
                        and round((t_sec - land) / 0.05) - MAX_LOOKAHEAD_TICKS >= hit - RELEASE_MARGIN_TICKS):
                    continue                        # it already hit: the tower HP includes its damage
                out[lane] = out.get(lane, 0) + damage
    return out


def crowns_behind(crown_towers, side):
    """True when the opponent has destroyed more of my crown towers than I have of theirs (public alive flags of the raw
    ``episode.crown_towers`` rows; a missing row = destroyed, as from_engine's _tower_slots). False without my king."""
    alive = [0, 0]
    for t in crown_towers:
        if t['hp'] > 0 and not t.get('destroyed'):
            alive[int(t['side']) == side] += 1
    if not any(int(t['side']) == side and t.get('type') == 'king' and t['hp'] > 0 for t in crown_towers):
        return False
    return 3 - alive[1] > 3 - alive[0]


@lru_cache(maxsize=8)
def lethal_log_cell(lane, grid):
    """The ``grid`` cell at (enemy princess x, LOG_CAST_Y_TILES), my frame: its roll reaches that princess."""
    from .model_tower import anchors
    from .model_v3 import cell_label
    return int(cell_label(torch.tensor((anchors()[4 if lane == 'L' else 5][0], LOG_CAST_Y_TILES / 32.0)), grid))


def _lethal_phase(options, t_sec, crown_towers, side, hit_ticks):
    """OT, or (ot_behind) regulation while behind on crowns and the card still hits before REGULATION_END_TICK."""
    if phase_index([t_sec])[0] == 2:
        return True
    return (options.lethal_rocket == 'ot_behind' and round(t_sec / 0.05) + hit_ticks <= REGULATION_END_TICK
            and crowns_behind(crown_towers, side))


def is_log(name):
    return ROLLING_CARDS.get(re.sub(r'[^a-z]', '', str(name).split('@')[0].lower())) == 'Log'


def lethal_log_choice(options, t_sec, names, allowed, crown_towers, side, grid, own=None, skip=()):
    """lethal_log: -> (slot, cell, target with card='Log') or None, under lethal_rocket's phase / crown rules."""
    slots = [i for i, n in enumerate(names) if n is not None and is_log(n) and allowed[i]]
    if not slots or not _lethal_phase(options, t_sec, crown_towers, side, LOG_HIT_TICKS):
        return None
    levels = dict(options.card_levels) if options.card_levels else None
    target = (lethal_rocket_target(crown_towers, side, 'Log', own, t_sec, levels=levels, skip=skip) if levels else
              lethal_rocket_target(crown_towers, side, 'Log', own, t_sec, skip=skip))
    return None if target is None else (slots[0], lethal_log_cell(target['lane'], grid), target)


def lethal_rocket_choice(options, t_sec, names, allowed, crown_towers, side, grid, pending=False, own=None, skip=()):
    """-> (slot, cell, target) when lethal_rocket fires, else None: overtime (phase_index 2, the tau_phase edge), no
    card pending, an affordable Rocket slot (``allowed``: in hand and cost <= integer elixir), a lethal princess.
    ``ot_behind`` also fires in regulation while ``crowns_behind`` and the Rocket lands before tick 3600 (cutoff above)."""
    if options.lethal_rocket == 'off' or pending:
        return None
    if options.lethal_log != 'on':
        own = None                                  # off: today's rule exactly (no in-flight guard)
    else:                                           # the Log first: cheaper and it hits sooner
        hit = lethal_log_choice(options, t_sec, names, allowed, crown_towers, side, grid, own, skip=skip)
        if hit is not None:
            return hit
    if phase_index([t_sec])[0] != 2:
        if (options.lethal_rocket != 'ot_behind' or round(t_sec / 0.05) + ROCKET_FLIGHT_TICKS > REGULATION_END_TICK
                or not crowns_behind(crown_towers, side)):
            return None
    slots = [i for i, n in enumerate(names) if n is not None and str(n).lower() == 'rocket' and allowed[i]]
    levels = dict(options.card_levels) if options.card_levels else None
    if levels:                                       # card_levels: the Rocket's own level (default: my tower level)
        target = lethal_rocket_target(crown_towers, side, own=own, t_sec=t_sec, levels=levels, skip=skip) if slots else None
    else:
        target = (lethal_rocket_target(crown_towers, side, own=own, t_sec=t_sec, skip=skip) if own else
                  lethal_rocket_target(crown_towers, side, skip=skip)) if slots else None
    if target is None:
        return None
    return slots[0], lethal_rocket_cell(target['lane'], grid), target


# ---- rocket_value (owner 2026-10-09 01:4x: "WHY IS THE MODEL NOT ROCKETING A FULL LAVAHOUND PUSH WITH 15+ ELIXIR OF VALUE?";
# iteration 2 10:00: "failure at the first attempt does not validate discarding the strategy") ----
# With Rocket in hand and affordable and nothing pending, play it when the best blast on MY half holds >= V of enemy elixir value.
# Sub-options (each one change, each its own value of a field so arms differ by exactly one thing):
#   rocket_value_mode  cost   (iteration 1) a body is worth its card's cost / bodies x its hp fraction, whatever the Rocket does to it
#                      damage a body is worth cost / bodies x min(Rocket damage, hp now) / max hp: the share of its value the
#                             Rocket destroys (a Giant at full hp is worth 1.9 of its 5, a Skeleton Dragon pair all 4)
#   rocket_value_hitbox centre the blast covers a body whose CENTRE is within the Rocket radius (iteration 1)
#                      edge   ... whose HITBOX touches it: centre distance <= radius + the body's collision radius (the RoyaleSim
#                             rule, spells.AOE_HIT_TEST = EdgeInclusive; Lava Hound 0.75, Balloon 0.5, Skeleton Dragons 0.9 tiles)
#   rocket_value_threat on    only while a tower of mine is under fire with an enemy body near it (tau_threat_state)
#   rocket_value_lead  off    aim at the bodies where they are now
#                      on     aim at where they will be when it lands: each body moves on at the velocity measured from the decision
#                             history over the residual lag + the Rocket flight from my king tower (rocket_lands_in)
#                      drift  ... every body walks toward my side (+y) at its catalog speed, no history
#                      blend  ... the measured velocity where the body moves, the drift where it does not (just deployed, standing)
#                      MEASURED (L74/rocket_value2/diag_lead.py, 440 bodies of 113 SIM fires): the bodies move 2.3 tiles by impact; the
#                      best blast aimed at the static / history / drift positions covers 38 / 42 / 46 % of their value (oracle 79 %)
# All numbers are RoyaleSim catalog ratios (the unified-level ladder cancels: Rocket 580 and every hp share it).
ROCKET_UNIT_DAMAGE = 580.0        # catalog Rocket damage to a non-tower body, level-1 scale (the same scale as every catalog hitpoints)
ROCKET_LAG_TICKS = 2              # decision -> deploy NOT already in the decision board: the SIM benchmark lands a play at once (0); live
                                  # decides on a board extrapolated 24 ticks ahead of a ~28-tick confirmation (4). With --action-delay 26 the
                                  # SIM needs --extrapolate 26 for the same thing.
ROCKET_SPEED_TILES_PER_TICK = 0.35   # catalog Rocket projectile speed 350, from my king tower (9.0, 28.65) in the board frame
MY_HALF_MIN_Y_TILES = 16.0        # board frame (me at the bottom): y tiles >= 16 is my half; a cell centre there is "on my half"
_CHILD_SHARE = {'golemite': ('golem', 2, 'Golemite'), 'lava_pups': ('lava_hound', 6, 'LavaPups'),
                'elixir_golemite': ('elixir_golem', 2, 'ElixirGolem2'), 'elixir_blob': ('elixir_golemite', 2, 'ElixirGolem4'),
                'royal_recruit': ('royal_recruits', 1, 'Recruit')}


@lru_cache(maxsize=1)
def rocket_unit_table():
    """{vocab key: (elixir value of one full-hp body, catalog hitpoints, collision radius in tiles, speed in tiles per tick)}; troops
    and buildings.
    Value = card cost / bodies the card puts out (cards.json count + second_summon.count). A spawned child shares its parent card
    (Lava Pups are the Hound's 7 over 6, golemites the Golem's 8 over 2, blobs a golemite's share over 2). A key missing from it
    is worth 0 (spells, ability markers, anything the catalog does not know)."""
    import json
    from . import vocab
    from .body_identity import CATALOG
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    table = {}
    for c in catalog['cards']:
        key = vocab.engine_key(c['name'])
        if c.get('kind') in ('troop', 'building') and c.get('elixir') and key not in table:
            n = int(c.get('count') or 1) + int((c.get('second_summon') or {}).get('count') or 0)
            table[key] = (float(c['elixir']) / max(n, 1), float(c.get('hitpoints') or 0.0),
                          float(c.get('collision_radius_milli') or 500) / 1000.0, float(c.get('speed') or 60) / 1200.0)
    for child in ('golemite', 'lava_pups', 'elixir_golemite', 'elixir_blob', 'royal_recruit'):   # parents before children
        parent, n, unit = _CHILD_SHARE[child]
        u = catalog['units'][unit]
        table[child] = (table.get(parent, (0.0,))[0] / n if parent in table else 0.0, float(u.get('hitpoints') or 0.0),
                        float(u.get('collision_radius_milli') or 500) / 1000.0, float(u.get('speed') or 60) / 1200.0)
    return table


@lru_cache(maxsize=1)
def immobile_keys():
    """{vocab key} of the bodies that never move, so a Tornado cannot pull them: the catalog cards of kind 'building', plus any
    card whose own unit has speed 0 (the catalog files the Furnace, FirespiritHut, as kind 'troop' but its unit is immobile)."""
    import json
    from . import vocab
    from .body_identity import CATALOG
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    return frozenset(vocab.engine_key(c['name']) for c in catalog['cards'] if c.get('kind') == 'building' or (
        c.get('kind') == 'troop' and (catalog['units'].get(c['name']) or {}).get('speed') == 0))


def unit_values():
    """{vocab key: elixir value of one full-HP body} (rocket_unit_table's first column)."""
    return {k: v[0] for k, v in rocket_unit_table().items()}


def body_value(cls, hp_frac=None):
    """Elixir value of one enemy body of vocab id ``cls`` at hp fraction ``hp_frac`` (None = full); 0 for spells and markers."""
    from . import vocab
    name = vocab.UNIT_VOCAB[int(cls)]
    if vocab.is_spell(int(cls)) or name.endswith('_ability'):
        return 0.0
    return rocket_unit_table().get(vocab.base_key(name), (0.0,))[0] * (1.0 if hp_frac is None else min(max(float(hp_frac), 0.0), 1.0))


def rocket_bodies(bs, mode='cost'):
    """[n, 7] float (class id, x tiles, y tiles, value, collision radius tiles, value left after the Rocket, catalog speed in tiles per
    tick = speed / 1200: catalog speed 60 is 1 tile/s) per enemy body of a BoardState (side != 0,
    as enemy_unit_count) worth > 0 under ``mode``: cost -> cost/bodies x hp fraction; damage -> cost/bodies x the share of its hp
    the Rocket takes (min(ROCKET_UNIT_DAMAGE, hp now) / max hp); kill -> cost/bodies x hp fraction for a body the Rocket kills
    (hp now <= ROCKET_UNIT_DAMAGE), 0 for one that survives it. Unknown hp = full."""
    from . import vocab
    table, rows = rocket_unit_table(), []
    for u in bs.units:
        if int(u.side) == 0 or vocab.is_spell(int(u.cls)):
            continue
        name = vocab.UNIT_VOCAB[int(u.cls)]
        ev, hp, radius, speed = table.get(vocab.base_key(name), (0.0, 0.0, 0.5, 0.05))
        if ev <= 0 or name.endswith('_ability'):
            continue
        f = 1.0 if u.hp_frac is None else min(max(float(u.hp_frac), 0.0), 1.0)
        if mode == 'cost' or hp <= 0:
            value = ev * f
        elif mode == 'kill':
            value = ev * f if f * hp <= ROCKET_UNIT_DAMAGE else 0.0
        else:
            value = ev * min(ROCKET_UNIT_DAMAGE, f * hp) / hp
        left = ev * max(0.0, f * hp - ROCKET_UNIT_DAMAGE) / hp if hp > 0 else 0.0       # what survives the Rocket
        if value > 0 or left > 0:
            rows.append((float(u.cls), float(u.x) * 18.0, float(u.y) * 32.0, value, radius, left, speed))
    return np.array(rows, dtype=np.float64).reshape(-1, 7)


def rocket_lands_in(cx, cy):
    """Ticks from the decision board to the Rocket's impact at board tile (cx, cy): the residual lag (ROCKET_LAG_TICKS), the 2-tick
    launch overhead and the flight at the catalog speed from my king tower (9.0, 28.65). Flight MEASURED in RoyaleSim at
    L74/rocket_value (round(d/.35)+2, +-1)."""
    return ROCKET_LAG_TICKS + int(round(math.hypot(cx - 9.0, cy - 28.65) / ROCKET_SPEED_TILES_PER_TICK)) + 2


def rocket_velocities(history, tick, bodies, max_speed=3.0):
    """[n, 2] tiles per tick for each row of ``bodies`` (rocket_bodies): matched to the nearest body of the same class in the OLDEST
    snapshot of ``history`` ([(tick, bodies)], newest last) that is >= 6 ticks old, within max_speed tiles/s x the gap + 0.75; zero
    when unmatched. A swarm of identical bodies moves as a group, which is what the blast needs."""
    vel = np.zeros((len(bodies), 2))
    ref = next((h for h in history if tick - h[0] >= 6), None)
    if ref is None or not len(bodies) or not len(ref[1]):
        return vel
    gap = tick - ref[0]
    for i, b in enumerate(bodies):
        same = ref[1][ref[1][:, 0] == b[0]]
        if not len(same):
            continue
        d = np.hypot(same[:, 1] - b[1], same[:, 2] - b[2])
        j = int(d.argmin())
        if d[j] <= max_speed * 0.05 * gap + 0.75:
            vel[i] = ((b[1] - same[j, 1]) / gap, (b[2] - same[j, 2]) / gap)
    return vel


def rocket_track(holder, tick, bodies, keep_ticks=40):
    """Append the decision's bodies to ``holder.rv_hist`` (the SIM match / the live pilot) and forget snapshots older than
    ``keep_ticks``; -> the history BEFORE this decision. A snapshot closer than 4 ticks to the last one replaces nothing (live
    decides every frame)."""
    hist = getattr(holder, 'rv_hist', None)
    if hist is None:
        hist = holder.rv_hist = []
    before = list(hist)
    if not hist or tick - hist[-1][0] >= 4:
        hist.append((tick, bodies))
    while hist and tick - hist[0][0] > keep_ticks:
        hist.pop(0)
    return before


def best_rocket_clump(bodies, grid, hitbox='centre', lead=None, min_y=MY_HALF_MIN_Y_TILES, with_left=False, towers=None):
    """-> (value, eligible) for the best Rocket blast CENTRED on my half: its value, and the [2304] bool cells (on my half) whose
    blast covers every body of that best clump. (0.0, None) with no body worth anything. ``hitbox`` 'centre' counts a body whose
    centre is within the Rocket radius, 'edge' one whose hitbox touches it (radius + the body's collision radius). ``lead`` =
    None, or the (decision tick, history, mode) of rocket_track / 'drift': the bodies are moved to where they will be when a Rocket aimed at the
    cell lands (rocket_lands_in at the cell, found by one refinement from the static best cell). ``towers`` (rocket_value_towers on) =
    the (L, R) enemy princess alive flags: a blast with bodies in it gains ROCKET_TOWER_VALUE per alive princess it covers (and its
    eligible cells must cover that princess too). A blast never covers the enemy king (no cell on my half can)."""
    if not len(bodies):
        return (0.0, None, 0.0) if with_left else (0.0, None)
    x, y = cell_centres_tiles(grid)
    reach = rocket_radius_tiles() + (bodies[:, 4] if hitbox == 'edge' else np.zeros(len(bodies)))
    cover = tower_cover_cells(grid, rocket_radius_tiles())
    mine = (y >= min_y) & ~cover[0]                     # never the enemy king (doctrine): no-op for min_y >= 16
    bonus = None if towers is None else tower_bonus(cover, towers)

    def blast(pos):
        inside = np.hypot(x[:, None] - pos[None, :, 0], y[:, None] - pos[None, :, 1]) <= reach[None, :]
        v = inside @ bodies[:, 3]
        if bonus is not None:                           # a princess counts only along with a clump
            v = np.where(v > 0, v + bonus, v)
        return inside, np.where(mine, v, -1.0)

    pos = bodies[:, 1:3]
    inside, value = blast(pos)
    if lead is not None:
        vel = rocket_velocities(lead[1], lead[0], bodies) if lead[2] != 'drift' else np.zeros((len(bodies), 2))
        if lead[2] != 'on':                         # drift / blend: toward my side (+y) at the catalog speed where nothing measured moves
            drift = np.stack([np.zeros(len(bodies)), bodies[:, 6]], axis=1)
            vel = drift if lead[2] == 'drift' else np.where((np.hypot(vel[:, 0], vel[:, 1]) > 0.01)[:, None], vel, drift)
        for _ in range(2):          # the flight depends on the aimed cell, the cell on where the bodies will be: two refinements
            best = int(value.argmax())
            horizon = rocket_lands_in(x[best], y[best])
            pos = np.clip(bodies[:, 1:3] + vel * horizon, (0.0, 0.0), (18.0, 32.0))
            inside, value = blast(pos)
    best = int(value.argmax())
    if value[best] <= 0:
        return (0.0, None, 0.0) if with_left else (0.0, None)
    members = inside[best] & (bodies[:, 3] > 0)         # the clump: the bodies that count; a zero-value survivor need not be covered
    eligible = mine & inside[:, members].all(axis=1)
    if bonus is not None:                               # ... and every alive princess that value counted
        for j, alive in enumerate(towers):
            if alive and cover[j + 1][best]:
                eligible = eligible & cover[j + 1]
    return (float(value[best]), eligible, float(inside[best] @ bodies[:, 5])) if with_left else (float(value[best]), eligible)


# ---- rocket_value_towers (owner 2026-10-17: "even more so if an enemy princess tower is caught in the blast radius along with the clump") ----
# The Rocket's princess hit in elixir: rho = 22.5 (2x) / 25.1 (OT) elixir per whole princess tower (L74/reward/RHO_FIT_R1.txt, win model;
# 1x 43 [23, 147] too wide to use) x the measured Rocket tower damage 497 / 4424 princess HP at live level 16 = 0.112 -> ~2.8 elixir.
# ponytail: one constant (no phase, level or tower-HP scaling); a princess the Rocket finishes is the lethal rules' business.
ROCKET_TOWER_VALUE = 2.8


@lru_cache(maxsize=8)
def tower_cover_cells(grid, reach):
    """[3, 2304] bool (read-only): the cell centre is within ``reach`` tiles + the tower's catalog collision radius of the enemy
    K, L, R (ENEMY_TOWERS_TILES)."""
    from .public_geometry import constants
    x, y = cell_centres_tiles(grid)
    radii = constants()['tower_radius']
    out = np.stack([np.hypot(x - tx, y - ty) <= reach + radii[k] / 1000.0
                    for (tx, ty), k in zip(ENEMY_TOWERS_TILES, ('KingTower', 'PrincessTower', 'PrincessTower'))])
    out.setflags(write=False)
    return out


def tower_bonus(cover, alive):
    """[2304] elixir: ROCKET_TOWER_VALUE for each alive enemy princess (``alive`` = (L, R)) a blast at the cell covers."""
    return ROCKET_TOWER_VALUE * (cover[1] * bool(alive[0]) + cover[2] * bool(alive[1]))


def enemy_princesses_alive(bs):
    """(L, R) public alive flags of the enemy princesses on a BoardState (towers[4:6]); (False, False) when it has no towers."""
    t = tuple(getattr(bs, 'towers', ()) or ())
    return (bool(t[4].alive), bool(t[5].alive)) if len(t) >= 6 else (False, False)


def rocket_value_choice(options, names, allowed, bs, grid, pending=False, holder=None, playing=False):
    """-> (slot, eligible cells, value) when rocket_value fires, else None: an affordable Rocket slot (``allowed``), no card
    pending, and the best blast centred on my half (best_rocket_clump) holds >= options.rocket_value. Public bodies only; the
    enemy king is out of reach (a centre on my half is >= 13 tiles from it). With lead on, ``holder`` keeps the decision history
    (rocket_track); called at EVERY decision, even with no Rocket in hand, so the history has no gaps."""
    if options.rocket_value <= 0:
        return None
    slots = [i for i, n in enumerate(names) if n is not None and str(n).lower() == 'rocket' and allowed[i]]
    track = options.rocket_value_lead in ('on', 'blend') and holder is not None
    watch = options.rocket_value_threat == 'on'
    threatened = False
    if watch and holder is not None:                # the tower-fire state is kept on EVERY decision, like the lead history
        holder.rv_threat_state, threatened = tau_threat_state(getattr(holder, 'rv_threat_state', None), bs)
        holder.rv_threatened = threatened
    if not slots and not track:
        return None                                 # nothing to cast, no history to keep
    bodies = rocket_bodies(bs, options.rocket_value_mode)
    lead = None
    if track:
        tick = int(round(float(bs.t_sec) / 0.05))
        lead = (tick, rocket_track(holder, tick, bodies), options.rocket_value_lead)
    elif options.rocket_value_lead == 'drift':
        lead = (0, [], 'drift')
    if pending or not slots or (options.rocket_value_idle == 'on' and playing):
        return None
    if float(bs.my_elixir) + 1e-9 < options.rocket_value_min_elixir or (watch and not threatened):
        return None
    value, eligible, left = best_rocket_clump(bodies, grid, options.rocket_value_hitbox, lead, options.rocket_value_min_y, True,
                                              towers=enemy_princesses_alive(bs) if options.rocket_value_towers == 'on' else None)
    if eligible is None or value + 1e-9 < options.rocket_value or left > options.rocket_value_max_left + 1e-9:
        return None
    return slots[0], eligible, value


def rocket_value_cell(logits, eligible):
    """The rocket_area aim restricted to ``eligible``: most learned cell mass inside the Rocket radius, then the cell's
    own logit, then the first index (choose_cells' tie order). With no finite eligible logit: the first eligible cell."""
    logits = logits.reshape(-1)
    keep = torch.as_tensor(np.asarray(eligible, dtype=bool), device=logits.device) & torch.isfinite(logits)
    if not bool(keep.any()):
        return int(np.flatnonzero(eligible)[0])
    mass = rocket_area_scores(logits.softmax(dim=-1)[None])[0].masked_fill(~keep, -torch.inf)
    return int(logits.masked_fill(mass != mass.max(), -torch.inf).argmax())


# ---- rocket_tornado (owner 2026-10-09 ~01:55: "rocket tornado combo also applies, especially for clumps that are too far apart for a lone
# rocket to hit all of them"; coordinator 10-09: the pipelined second tap works live, branch worktree-agent-a996a070b47df363e 34e5a85) ----
# The Tornado pulls every body within its radius toward the centre for 21 ticks; the Rocket must LAND while the pull has gathered them.
# MEASURED in RoyaleSim (L74/rocket_value/measure_combo.out): Tornado lives 21 ticks, radius 5.5; 8 Knights / Giants spread within ~2 tiles of
# the centre fit one 2.0-radius blast from 15 (Knights) / 21 (Giants) ticks after the cast and for >= 30 more: the Rocket must land
# PULL_LANDS_FROM..PULL_LANDS_TO ticks after the Tornado is deployed. Rocket flight (decision -> impact) = round(d / .35) + 2 ticks from
# my king tower. With a Rocket decision at T and a Tornado tap at T + g, the Rocket lands at T + flight and the Tornado at T + g:
# g in [max(min_gap, flight - PULL_LANDS_TO), flight - PULL_LANDS_FROM]. min_gap = LIVE_FOLLOW_MIN_GAP_TICKS (the pipelined second tap:
# both cards landed 0-3 ticks apart at a 4-tick decision gap in 11 of 12 live pairs); the SIM's pending lock needs 30 (2.9 % of cells).
PULL_LANDS_FROM, PULL_LANDS_TO = 12, 33
LIVE_FOLLOW_MIN_GAP_TICKS = 4
WINDOW_MIN_WIDTH_TICKS = 5                    # a plan narrower than the 2-tick live frame grid is not started
COMBO_ARRIVAL_TICKS = 2                       # e1_eval.FOLLOW_ARRIVAL_TICKS: a follow-up requested after_ticks later lands that many minus this
                                              # after the first play (live, 11 pairs asked 4 apart: 0-3 apart, mean 1.1)


def rocket_tornado_timing(plan):
    """(after_ticks, within_ticks) of the Tornado follow-up for a plan window (lo, hi) of landing gaps: the middle of the window, robust to
    the 2-tick frame grid on both sides, shifted by the arrival lag (e1_eval.FOLLOW_ARRIVAL_TICKS) the request is lost to."""
    after = (plan[0] + plan[1]) // 2 + COMBO_ARRIVAL_TICKS
    return after, plan[1] + COMBO_ARRIVAL_TICKS - after


@lru_cache(maxsize=1)
def tornado_radius_tiles():
    import json
    from .body_identity import CATALOG
    t = next(c for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards'] if c['name'] == 'Tornado')
    return float(t['spell']['radius_milli']) / 1000.0


def rocket_flight_ticks(cx, cy):
    """Ticks from the Rocket's deploy to its impact at board tile (cx, cy) (no residual lag): 2 + round(d / .35) from my king tower."""
    return rocket_lands_in(cx, cy) - ROCKET_LAG_TICKS


def rocket_tornado_plan(cx, cy, min_gap=LIVE_FOLLOW_MIN_GAP_TICKS):
    """-> (earliest, latest) ticks after the Rocket decision at which the Tornado may be tapped so the Rocket lands inside the pull, or
    None when there is no such time (the combo is not started)."""
    flight = rocket_flight_ticks(cx, cy)
    lo, hi = max(min_gap, flight - PULL_LANDS_TO), flight - PULL_LANDS_FROM
    return (lo, hi) if lo <= hi else None


# ---- rocket_tornado_window measured / rocket_tornado_order either (owner 2026-10-17 ~21:30: "make the listed rule changes") ----
# Re-fit on the fast-plays timing sweep (fork36, engine only, oracle aim; pod1017_fastplays/fastplays/sweep.jsonl, L74/combo/fit_window.py):
# L = Rocket impact - Tornado deploy, MEASURED per row. The group damage holds >= 80 % of the best combo and >= 1.5 x a lone Rocket for
# L in: enemy king 4..33, enemy princess 6..29, enemy mid 6..24, enemy bank 6..33 (walking clumps spread again once the pull ends);
# my bridge 3..47, my princess 4..45, my king 7..45 (clumps engaged at my towers stay gathered; the sweep stopped at L ~45). The ramp
# below L ~7 is the pull still gathering. -> 7..24 everywhere (inside every measured window), 7..40 at a centre on my side past the
# bridge exit (y >= 19: the three my-half scenarios sat at y 19.5..23).
# Flight (deploy -> impact) = d / .35 + 0.52 on average (770 rows; measured - round(d / .35) in -1..+2); v1's round(d / .35) + 2 reads
# 1.3-1.6 ticks high (live 182814 t3008: 33-35 measured vs 37 predicted).
PULL_LANDS_V2 = (7, 24)
PULL_LANDS_V2_MINE = (7, 40)
PULL_V2_MINE_Y = 19.0
FLIGHT_V2_OFFSET = 0.5
# rocket_tornado_lone best: the combo when its pull gathers more than the best single blast holds (> COMBO_GAIN_MIN elixir more), else
# the lone Rocket. No 3-elixir Tornado margin: the lone value is the decision instant's and its edge bodies walk out during the flight --
# the fork36 sweep's ORACLE-aimed lone Rocket took 1102 / 2314 / 2200 hp of the my-king / my-princess / my-bridge columns where the
# combo took 4206 / 4441 / 4496, and the 10-17 scenario re-run's lone rule (the margin 3 version) 1476 / 1840 / 1476.
COMBO_GAIN_MIN = 0.5
# rocket_tornado_lone margin (owner 10-18: "only rocket is used when it suffices (no tornado use if not needed for the clump)"): the pull
# must add at least the Tornado's own 3 elixir over the best lone blast (value - single >= this), and no lone blast may hold V already.
COMBO_MARGIN_ELIXIR = 3.0
# rocket_tornado_window measured: the decision board's elixir is a LOOK-AHEAD one (extrapolate: SIM 26 ticks, live --extrapolate 24).
# v1's check (board elixir - 6 + regen x earliest gap >= 3) counted those ticks twice: 6 of 127 cur combos (fast-plays offc) and 10 of 38
# early 10-17 enemy-half combos lost their follow-up 'unaffordable'. measured: the follow-up's own verdict (e1_eval.follow_up_have: its
# elixir FOLLOW_AFFORD_TICKS ahead minus the unlanded first card) at its due tick, from the de-looked-ahead elixir.
COMBO_LOOKAHEAD_TICKS = 26
COMBO_AFFORD_TICKS = 6       # = e1_eval.FOLLOW_AFFORD_TICKS (live_play's)


def combo_flight_ticks(cx, cy, window='v1'):
    """Rocket deploy -> impact at board tile (cx, cy): v1 = rocket_flight_ticks (int); measured = d / .35 + FLIGHT_V2_OFFSET."""
    if window == 'v1':
        return rocket_flight_ticks(cx, cy)
    return math.hypot(cx - 9.0, cy - 28.65) / ROCKET_SPEED_TILES_PER_TICK + FLIGHT_V2_OFFSET


def combo_window(cy, window='v1'):
    """(earliest, latest) Rocket landing after the Tornado deploy, ticks, for a pull centred at board y ``cy``."""
    if window == 'v1':
        return PULL_LANDS_FROM, PULL_LANDS_TO
    return PULL_LANDS_V2_MINE if cy >= PULL_V2_MINE_Y else PULL_LANDS_V2


def combo_plan(cx, cy, order='rocket', window='v1', min_gap=LIVE_FOLLOW_MIN_GAP_TICKS):
    """-> (earliest, latest) deploy gap (ticks) of the follow-up card after the first one so the Rocket lands inside the pull, or None.
    order 'rocket': Rocket first, the Tornado g later -> the Rocket lands F - g after the Tornado; 'tornado': Tornado first, the Rocket
    h later -> it lands F + h after it (F = combo_flight_ticks). v1 + rocket = rocket_tornado_plan exactly."""
    if window == 'v1' and order == 'rocket':
        return rocket_tornado_plan(cx, cy, min_gap)
    f = combo_flight_ticks(cx, cy, window)
    lf, lt = combo_window(cy, window)
    lo, hi = (f - lt, f - lf) if order == 'rocket' else (lf - f, lt - f)
    lo, hi = max(min_gap, math.ceil(lo - 1e-9)), math.floor(hi + 1e-9)
    return (lo, hi) if lo <= hi else None


def elixir_regen_per_tick(bs):
    """Public regeneration of MY elixir per tick on a BoardState: 1 per 2.8 s, x2 from 2:00, x3 in overtime."""
    return (3 if bs.overtime else 2 if bs.double_elixir else 1) / 56.0


COMBO_EDGE_MARGIN_TILES = 1.0     # a combo is never aimed within this of the board's side edge (SIM: EVERY Rocket at the first column, x = 0.0, was refused)


RIVER_Y_TILES = (15.0, 17.0)               # water rows (RoyaleSim arena: y 15000-17000)
BRIDGE_X_TILES = ((2.5, 4.5), (13.5, 15.5))  # walkable bridge columns (x 2500-4500, 13500-15500)


def river_held(bodies):
    """[n] bool: GROUND bodies on the ENEMY bank (board y <= 15, me at the bottom) off the bridge columns -- a Tornado on my half
    holds them at the bank (y 15) instead of dragging them over (owner 10-14; RoyaleSim 0.1.33 client15535_pull_stops, measured
    L74/reward/TORNADO_RIVER.md). Air bodies (catalog flying) cross."""
    if not len(bodies):
        return np.zeros(0, dtype=bool)
    traits = log_air_traits()
    air = np.array([bool(traits.get(int(c), (False, 0.0))[0]) for c in bodies[:, 0]], dtype=bool)
    x = bodies[:, 1]
    on_bridge = np.zeros(len(bodies), dtype=bool)
    for lo, hi in BRIDGE_X_TILES:
        on_bridge |= (x >= lo) & (x <= hi)
    return ~air & ~on_bridge & (bodies[:, 2] <= RIVER_Y_TILES[0])


def water_stop_tiles(x0, y0, x1, y1):
    """extrapolate.water_stop in board tiles, element-wise on arrays (the river and the bridges are symmetric in either side's frame):
    a GROUND body moving (x0, y0) -> (x1, y1) never ends on water -- off a bridge it stops at the bank it came from, on a bridge at
    the bridge's edge. -> (x, y)."""
    r0, r1 = RIVER_Y_TILES
    on1 = np.zeros(np.shape(x1), dtype=bool)
    lo0, hi0 = np.full(np.shape(x0), -np.inf), np.full(np.shape(x0), np.inf)
    on0 = np.zeros(np.shape(x0), dtype=bool)
    for a, b in BRIDGE_X_TILES:
        on1 |= (x1 >= a) & (x1 <= b)
        m = (x0 >= a) & (x0 <= b)
        lo0, hi0, on0 = np.where(m, a, lo0), np.where(m, b, hi0), on0 | m
    wet = (y1 > r0) & (y1 < r1) & ~on1
    bridge = on0 & (y0 > r0) & (y0 < r1)
    return (np.where(wet & bridge, np.clip(x1, lo0, hi0), x1),
            np.where(wet & ~bridge, np.where(y0 >= r1, r1, np.where(y0 <= r0, r0, y1)), y1))


# tornado_river full (owner 10-17, the 182814 t3008 miss): RoyaleSim moves a pulled GROUND body per axis and never into water (TORNADO_RIVER.md;
# L74/combo/bridge_probe.py on fork36: a Knight / Giant on the left bridge pulled toward (8.5, 16) is held at the bridge edge x 4.5 for the
# whole pull, 4 tiles from the centre; toward a centre on land it leaves the bridge and arrives; a Ram Rider walking onto the bridge sticks
# at x 5.0, 3.5 tiles off -- as live 182814 did, 4 tiles off). The value model follows each such body's pull path instead of assuming it
# reaches the centre.
PULL_STEP_PER_SPEED = 4.32      # RoyaleSim ATTRACT step = catalog speed x 360 / 100 milli-tiles per tick (Knight 216; probe 229 with its
                                # walk), per rocket_bodies' speed column (catalog speed / 1200 tiles per tick)
PULL_PATH_TICKS = 16            # pull ticks before the Rocket lands: the middle of PULL_LANDS_V2
BRIDGE_WALK_TICKS = (0, 20, 40) # a ground body in a bridge column may walk this long along it before the pull starts (decision -> Tornado
                                # deploy: ~28 Tornado first, 40 at live 182814): it must end inside the blast from EVERY start
BRIDGE_SLACK_TILES = 0.5        # a body centre this close to a bridge column counts as in it (reader / hitbox: 182814's Mega Knight at x 13.23)


def pull_river_ends(bodies, x, y, inside, dist, blast, fixed):
    """tornado_river full: -> (inside, dist) with every (centre cell, GROUND body) pair whose pull meets the water re-judged by where the
    pull leaves the body after PULL_PATH_TICKS (counted only if the Rocket blast at the centre covers that point; ``dist`` = that end's
    distance, the plateau tie-break). Meets the water = the body and the centre on different banks (a centre in the river is on neither),
    the body on a bridge, or the body in a bridge column within 2 tiles of the river (it may walk onto the bridge first: BRIDGE_WALK_TICKS).
    Per tick: a pull step toward the centre of PULL_STEP_PER_SPEED x its speed, a bridge-column body also walks toward my side at its
    catalog speed, then water_stop_tiles. Air bodies cross (unchanged); buildings never move (unchanged).
    ponytail: straight-line pull + straight walk along the bridge, no pathing, no stop to attack; a simulated engine path is the upgrade."""
    if not len(bodies):
        return inside, dist
    traits = log_air_traits()
    air = np.array([bool(traits.get(int(c), (False, 0.0))[0]) for c in bodies[:, 0]], dtype=bool)
    bx, by = bodies[:, 1], bodies[:, 2]
    r0, r1 = RIVER_Y_TILES
    column = np.zeros(len(bodies), dtype=bool)
    for a, b in BRIDGE_X_TILES:
        column |= (bx >= a - BRIDGE_SLACK_TILES) & (bx <= b + BRIDGE_SLACK_TILES)
    near = column & (by >= r0 - 2.0) & (by <= r1 + 2.0)
    far = (((by[None, :] <= r0) & (y[:, None] > r0)) | ((by[None, :] >= r1) & (y[:, None] < r1))
           | ((by[None, :] > r0) & (by[None, :] < r1)))
    ci, bi = np.nonzero(inside & (~air & ~fixed)[None, :] & (far | near[None, :]))
    if not len(ci):
        return inside, dist
    w = np.array(BRIDGE_WALK_TICKS, dtype=np.float64)
    ci, bi = np.repeat(ci, len(w)), np.repeat(bi, len(w))
    speed = bodies[bi, 6]
    walk = np.where(near[bi], speed, 0.0)
    px = bx[bi].copy()
    for a, b in BRIDGE_X_TILES:                         # a column body (slack) walks ON its bridge
        m = near[bi] & (px >= a - BRIDGE_SLACK_TILES) & (px <= b + BRIDGE_SLACK_TILES)
        px = np.where(m, np.clip(px, a, b), px)
    py = by[bi] + walk * np.tile(w, len(ci) // len(w))
    cx, cy, step = x[ci], y[ci], speed * PULL_STEP_PER_SPEED
    for _ in range(PULL_PATH_TICKS):
        dx, dy = cx - px, cy - py
        d = np.hypot(dx, dy)
        k = np.minimum(step, d) / np.maximum(d, 1e-9)
        px, py = water_stop_tiles(px, py, px + dx * k, py + dy * k + walk)
    end = np.hypot(cx - px, cy - py).reshape(-1, len(w))
    ok = (end <= blast[bi].reshape(-1, len(w))).all(axis=1)
    ci, bi = ci[::len(w)], bi[::len(w)]
    inside, dist = inside.copy(), dist.copy()
    inside[ci, bi] = ok
    dist[ci, bi] = end.max(axis=1)
    return inside, dist


COMBO_DEPLOY_TICKS = 26         # decision -> the first card deployed: the SIM's action_delay_ticks; live tap-to-deploy 22-27 (fastplays)


def combo_drift(bodies, ticks):
    """rocket_tornado_lead drift: ``bodies`` (rocket_bodies rows) moved to where they will have walked ``ticks`` later at their catalog
    speed. A GROUND body on the enemy half (y < 15) walks to its nearest bridge's entrance (the bridge's x range, y 15), then along the
    bridge toward my side; one on a bridge walks along it; an AIR body there flies straight toward my side (+y). My half stays put (clumps
    there are mostly engaged at my towers: the fork36 sweep's my-half windows stay gathered to L ~45); buildings never move.
    (Why: smoke 10-17 seed 741201, an enemy-half combo judged on the decision board -- the push walked ~4 tiles toward the bridge in the
    79 ticks to the Tornado's start and the Rocket took 4.6 of the 9.5 elixir expected.)
    ponytail: straight lines to the bridge, no stop to attack; a measured velocity (rocket_value_lead blend) is the upgrade."""
    out = np.array(bodies, dtype=np.float64, copy=True)
    if not len(out) or ticks <= 0:
        return out
    from . import vocab
    traits, still = log_air_traits(), immobile_keys()
    r0, r1 = RIVER_Y_TILES
    for i, b in enumerate(out):
        x, y, left = float(b[1]), float(b[2]), float(b[6]) * ticks
        if y >= r1 or left <= 0 or vocab.base_key(vocab.UNIT_VOCAB[int(b[0])]) in still:
            continue
        if bool(traits.get(int(b[0]), (False, 0.0))[0]):           # air: straight at my side
            out[i, 2] = y + left
            continue
        lo, hi = min(BRIDGE_X_TILES, key=lambda br: abs((br[0] + br[1]) / 2 - x))
        if y < r0:                                                  # to the bridge entrance first
            tx = min(max(x, lo + .5), hi - .5)
            d = math.hypot(tx - x, r0 - y)
            step = min(d, left)
            if d > 0:
                x, y = x + (tx - x) * step / d, y + (r0 - y) * step / d
            left -= step
        out[i, 1], out[i, 2] = x, y + max(left, 0.0)
    return out


def best_tornado_centre(bodies, grid, hitbox='centre', min_y=MY_HALF_MIN_Y_TILES, river=False, towers=None):
    """-> (value, cell) for the Tornado centre on my half whose pull radius holds the most value; (0.0, None) without bodies.
    Buildings (immobile_keys) are not pulled: they count only inside the Rocket's own blast around the centre (where the Rocket aims).
    Many centres tie on a spread clump (a plateau): the one picked is the plateau's MIDDLE for the bodies it pulls, the cell with the
    smallest value-weighted mean distance to them -- the pull gathers them there and the Rocket (radius 2.0) lands on that point.
    The first-index tie-break of iteration 3 took the plateau's corner, (0.0, 16.0): all 78 of those SIM combos were refused at landing
    (cb5 / cb7 / cb9, pod 10-09) and the pull would have dragged the clump to the edge.
    ``river`` True = tornado_river on (enemy-bank bodies held at the bank), 'full' = pull_river_ends. ``towers`` = rocket_value_towers'
    (L, R) princess alive flags (best_rocket_clump's bonus, for the blast at the centre). A centre whose pull reaches the enemy king is
    never chosen (doctrine: the Tornado's tower damage would wake it; no centre on my half can)."""
    if not len(bodies):
        return 0.0, None
    x, y = cell_centres_tiles(grid)
    reach = tornado_radius_tiles() + (bodies[:, 4] if hitbox == 'edge' else np.zeros(len(bodies)))
    dist = np.hypot(x[:, None] - bodies[None, :, 1], y[:, None] - bodies[None, :, 2])
    inside = dist <= reach[None, :]
    from . import vocab
    fixed = np.array([vocab.base_key(vocab.UNIT_VOCAB[int(c)]) in immobile_keys() for c in bodies[:, 0]], dtype=bool)
    blast = rocket_radius_tiles() + (bodies[:, 4] if hitbox == 'edge' else np.zeros(len(bodies)))
    if fixed.any():      # a building does not move in the pull: it counts only where the Rocket aimed at the centre hits it, where it stands
        inside = inside & (~fixed[None, :] | (dist <= blast[None, :]))
    if river == 'full':
        inside, dist = pull_river_ends(bodies, x, y, inside, dist, blast, fixed)
    elif river:          # --tornado-river: an enemy-bank ground body is held at the bank -- it counts only if the Rocket covers that point
        held = river_held(bodies)
        if held.any():
            at_bank = np.hypot(x[:, None] - bodies[None, :, 1], y[:, None] - RIVER_Y_TILES[0])
            inside = inside & (~held[None, :] | (at_bank <= blast[None, :]))
            dist = np.where(held[None, :], at_bank, dist)      # the plateau tie-break uses where they really end up
    ok = ((y >= min_y) & (x >= COMBO_EDGE_MARGIN_TILES) & (x <= 18.0 - COMBO_EDGE_MARGIN_TILES) & (y <= 32.0 - COMBO_EDGE_MARGIN_TILES)
          & (y >= COMBO_EDGE_MARGIN_TILES) & ~tower_cover_cells(grid, tornado_radius_tiles())[0])
    value = np.where(ok, inside @ bodies[:, 3], -1.0)
    if towers is not None:                              # a princess in the Rocket blast at the centre, only along with a clump
        value = np.where(value > 0, value + tower_bonus(tower_cover_cells(grid, rocket_radius_tiles()), towers), value)
    top = float(value.max())
    if top <= 0:
        return 0.0, None
    plateau = np.flatnonzero(value >= top - 1e-9)
    spread = (np.where(inside[plateau], dist[plateau], 0.0) * bodies[None, :, 3]).sum(axis=1)
    return top, int(plateau[int(spread.argmin())])


def rocket_tornado_choice(options, names, allowed, bs, grid, pending=False, min_gap=LIVE_FOLLOW_MIN_GAP_TICKS):
    """-> (rocket slot, tornado slot, cell, (earliest, latest), value, order) when the combo starts, else None: Rocket AND Tornado in hand
    (``names`` = the hand), the Rocket affordable now and the Tornado affordable at the earliest follow-up time (regeneration counted),
    nothing pending, NO single Rocket blast already holds rocket_value (rocket_value_choice's), the Tornado pull around the best centre
    holds >= rocket_value, and a follow-up time at least WINDOW_MIN_WIDTH_TICKS wide exists. Same value mode / hitbox / min_y / min
    elixir as the lone rule (the caller applies idle / threat).
    ``order`` 'rocket' = Rocket now at the cell, the Tornado there as the follow-up (the only order before 10-17); 'tornado'
    (rocket_tornado_order either) = Tornado now, the Rocket as the follow-up -- the order whose window (combo_plan) is wider, Rocket
    first on a tie, the Tornado then affordable NOW. 'lone' (rocket_tornado_lone best): one blast already holds rocket_value and the
    pull gathers no more than COMBO_GAIN_MIN beyond it, or no combo plan exists -> (rocket slot,
    tornado slot, None, None, the lone value, 'lone'): the caller plays its rocket_value_choice hit, so no such clump is left with
    neither play ('combo': None instead -- the model plays). rocket_tornado_lead drift: the pull is judged on combo_drift's bodies, moved for the decision -> Tornado deploy time
    of the plan found on the decision board (one refinement)."""
    if options.rocket_tornado == 'off' or options.rocket_value <= 0 or pending:
        return None
    rockets = [i for i, n in enumerate(names) if n is not None and str(n).lower() == 'rocket' and allowed[i]]
    tornados = [i for i, n in enumerate(names) if n is not None and str(n).lower() == 'tornado']
    hand = getattr(bs, 'my_hand', None)             # the SIM's names are the whole deck: the Tornado must be in the HAND (live names = the hand)
    if hand is not None and tornados:
        from . import vocab
        tornados = tornados if vocab.unit_id('tornado') in tuple(hand) else []
    if not rockets or not tornados or float(bs.my_elixir) + 1e-9 < options.rocket_value_min_elixir:
        return None
    x, y = cell_centres_tiles(grid)

    def plan_at(c):                                 # -> (order, plan) with the wider window, Rocket first on a tie; None
        plans = []
        for order in ('rocket', 'tornado') if options.rocket_tornado_order == 'either' else ('rocket',):
            plan = combo_plan(x[c], y[c], order, options.rocket_tornado_window, min_gap)
            if plan is not None and plan[1] - plan[0] + 1 >= WINDOW_MIN_WIDTH_TICKS and (order == 'rocket' or allowed[tornados[0]]):
                plans.append((plan[1] - plan[0], order, plan))
        return max(plans, key=lambda q: q[0])[1:] if plans else None    # max keeps the first on a tie

    bodies = rocket_bodies(bs, options.rocket_value_mode)
    towers = enemy_princesses_alive(bs) if options.rocket_value_towers == 'on' else None
    river = 'full' if options.tornado_river == 'full' else options.tornado_river == 'on'
    single, _ = best_rocket_clump(bodies, grid, options.rocket_value_hitbox, None, options.rocket_value_min_y, towers=towers)
    value, cell = best_tornado_centre(bodies, grid, options.rocket_value_hitbox, options.rocket_value_min_y, river=river, towers=towers)
    if options.rocket_tornado_lead == 'drift' and cell is not None:
        first = plan_at(cell)
        if first is not None:
            t = COMBO_DEPLOY_TICKS + ((first[1][0] + first[1][1]) // 2 if first[0] == 'rocket' else 0)
            value, cell = best_tornado_centre(combo_drift(bodies, t), grid, options.rocket_value_hitbox, options.rocket_value_min_y,
                                              river=river, towers=towers)
    lone = options.rocket_tornado_lone in ('best', 'combo') and single + 1e-9 >= options.rocket_value
    no = (rockets[0], tornados[0], None, None, single, 'lone') if lone and options.rocket_tornado_lone == 'best' else None
    if cell is None or (single + 1e-9 >= options.rocket_value and not lone) or value + 1e-9 < options.rocket_value:
        return no
    if lone and value <= single + COMBO_GAIN_MIN + 1e-9:
        return no
    if options.rocket_tornado_lone == 'margin' and value + 1e-9 < single + COMBO_MARGIN_ELIXIR:   # (single >= V: returned above)
        return None
    best = plan_at(cell)
    if best is None:
        return no
    order, plan = best
    if options.rocket_tornado_window == 'measured':  # 9 elixir by the follow-up's due tick, either order (COMBO_LOOKAHEAD_TICKS)
        due = rocket_tornado_timing(plan)[0]
        if float(bs.my_elixir) + elixir_regen_per_tick(bs) * (due + COMBO_AFFORD_TICKS - COMBO_LOOKAHEAD_TICKS) < 9.0 - 1e-9:
            return no
    elif float(bs.my_elixir) - 6.0 + elixir_regen_per_tick(bs) * plan[0] < 3.0:     # v1: Rocket 6 now, Tornado 3 at the earliest gap
        return no
    return rockets[0], tornados[0], int(cell), plan, value, order


# plan1026 Pillar 3 P1 (ticket B): the rules a SAMPLED decide (training rollouts) runs -- the finishers and barrel_lane
# (owner 10-25: it covers a reader issue training cannot fix). Every other option is a greedy-decoder rule (live / SIM eval).
SAMPLE_RULES = ('lethal_rocket', 'lethal_log', 'lethal_quiet', 'card_levels', 'barrel_lane')


def sample_rules(options):
    """``options`` reduced to SAMPLE_RULES (the rest at their defaults)."""
    return DecisionOptions(**{k: getattr(options, k) for k in SAMPLE_RULES})


def model_cell_logits(model, enc, device):
    """-> cell_logits(ids, slots): the card-conditioned cell logits of rows ``ids`` (one batched call per use)."""
    def cell_logits(ids, slots):
        index = torch.as_tensor(ids, device=device)
        return model.cell_logits({k: v[index] for k, v in enc.items()}, torch.tensor(slots, device=device))
    return cell_logits


@torch.no_grad()
def decide(heads, p, allowed, stalled, *, tau, options, rngs, cell_logits, card_names=None, decode='greedy',
           sampler=None, cell_guard=None, follow_up=None, trace=None, choose=None,
           t_sec=None, enemy_alive=None, grid=None, projectiles=None, barrel_id=None, step_s=None, elixir=None,
           enemy_units=None, lethal=None, threatened=None, rocket_boards=None, tau_threat=None, tau_delta=None,
           log_air_boards=None, rocket_value=None, barrel_goblins=None, gate_sample=0.0, gate_rngs=None):
    """THE decision (plan1026 Pillar 3 P1). SIM eval / forks (``decide_batch``), live (``live_gen_v2.GenPilot.decide``)
    and training rollouts (``e1_eval.sample_decide_batch``, decode 'sample') all run this one function; the callers only
    build the per-row context. Rows are independent (each draws only from its own rng); per row, in order:
      1. gate. greedy: p > tau (tau_phase / tau_threatened / tau_delta) or stalled, + the hazard draw (gate_decode).
         sample: Bernoulli(sigmoid((z - logit tau) / T_gate)) from ``sampler['rngs'][r]`` (stalled = forced play).
         greedy + ``gate_sample`` T > 0 (live --gate-sample, pilot 10-28): that same draw at T from ``gate_rngs[r]``, with
         z = ``heads['gate']`` and tau = the phase tau (+ tau_delta) -- the trainer's tau_r; tau_threatened and the hazard
         draw do not apply (the trainer has neither). The draw goes to ``trace`` as 'gate_sample'.
      2. the finishers (lethal_rocket / lethal_log, lethal_quiet's skip): gate, card and cell.
      3. greedy only: rocket_value / rocket_tornado (the combo's second card via ``follow_up``).
      4. card: choose_slot (greedy) | categorical at T (sample); cell: choose_cells with every option (greedy) |
         categorical at T + barrel_lane (sample). xbow_dead_lane / rocket_dead_target leaving no
         cell drop that card for the model's next (greedy), else WAIT; a log_air block = WAIT.
    ``cell_logits(ids, slots)`` -> [len(ids), N_CELLS] logits; ``cell_guard(r, slot, logits)`` (live: the reader's
    legal / failed-spot / UI masks) is applied to every playing row's logits before aiming; ``follow_up(r, first,
    second, cell, after, within, order, value)`` -> the follow-up entry or None (None: no combo, the model decides);
    ``choose`` replaces choose_cells for the playing rows' aim (live passes its module's name);
    ``trace`` (a list, live) gets one dict per row: the tau, hazard draw, rule data, dropped card, log_air flags, the
    final logits and a WAIT row's logged cell. -> per row dict(play, slot, cell, why[, follow_ups]) (+ the sample
    record: allowed, stalled, gate_sampled, lp_gate, lp_card, lp_cell, p_gate, T, and with any SAMPLE_RULES option on,
    ``forced``: a finisher / barrel_lane chose, not the sampled policy -- rl_royale leaves those rows out of PPO)."""
    allowed = np.asarray(allowed, dtype=bool)
    n = len(allowed)
    any_allowed = allowed.any(axis=1)
    p = np.asarray(p, dtype=np.float64)
    sample = decode == 'sample'
    if decode not in ('greedy', 'sample'):
        raise ValueError(f'decode must be greedy or sample, got {decode!r}')
    if options.gate_decode == 'timing_head':
        raise ValueError("gate_decode timing_head has no gate: e1_eval.timing_decide_batch decodes it, not decide()")
    if sample and options != sample_rules(options):
        raise ValueError('a sampled decide runs only the SAMPLE_RULES options (sample_rules)')
    tr = [dict() for _ in range(n)] if trace is not None else None
    hazard = [None] * n
    # ---- 1. gate ----
    if sample:
        s = sampler
        tau_r, T, T_gate, heads_sampled = s['tau_r'], s['T'], s['T_gate'], s['heads']
        gate_sampled = any_allowed & ~stalled                      # forced (stalled) or impossible (no card) -> not sampled
        logit_tau = math.log(tau / (1.0 - tau)) if tau_r is None else np.log(tau_r / (1.0 - tau_r))
        z_gate = heads['gate'].detach().cpu().numpy().astype(np.float64)
        with np.errstate(over='ignore'):
            p_b = 1.0 / (1.0 + np.exp(-(z_gate - logit_tau) / T_gate))
        g = np.zeros(n, dtype=bool)
        lp_gate = np.zeros(n, dtype=np.float64)
        for r in range(n):
            if gate_sampled[r] and 'gate' not in heads_sampled:
                g[r] = p[r] > (tau if tau_r is None else tau_r[r])  # greedy gate, as live_decide
            elif gate_sampled[r]:
                g[r] = s['rngs'][r].random() < p_b[r]
                lp_gate[r] = math.log(p_b[r] if g[r] else 1.0 - p_b[r])
        playing = any_allowed & (stalled | g)
        lp_card = np.zeros(n, dtype=np.float64)
        lp_cell = np.zeros(n, dtype=np.float64)
        base_tau = tau = np.broadcast_to(np.float64(tau) if tau_r is None else tau_r, n)
    elif gate_sample > 0:                           # live --gate-sample: the trainer's sampled gate (above), its own rng
        if options.gate_decode != 'threshold' or gate_rngs is None or 'gate' not in heads:
            raise ValueError('gate_sample needs gate_decode threshold, gate_rngs and the gate logit (heads["gate"])')
        base_tau = tau = np.broadcast_to(np.asarray(gate_taus(options, tau, t_sec, n), dtype=np.float64), n)
        if tau_delta is not None:                   # posture / pipeline shift, as the trainer's tau_r + dtau
            tau = tau + np.asarray(tau_delta, dtype=np.float64)
        logit_tau = np.log(tau / (1.0 - tau))
        z_gate = heads['gate'].detach().cpu().numpy().astype(np.float64).reshape(n)
        with np.errstate(over='ignore'):
            p_b = 1.0 / (1.0 + np.exp(-(z_gate - logit_tau) / float(gate_sample)))
        playing = any_allowed & stalled
        for r in np.flatnonzero(any_allowed & ~stalled):
            u = float(gate_rngs[r].random())
            playing[r] = u < p_b[r]
            if tr is not None:
                tr[r]['gate_sample'] = dict(u=u, p_b=float(p_b[r]), z=float(z_gate[r]), tau=float(tau[r]),
                                            T=float(gate_sample), fire=bool(playing[r]))
        tau, base_tau = np.broadcast_to(tau, n), np.broadcast_to(base_tau, n)
    else:
        base_tau = tau = gate_taus(options, tau, t_sec, n)
        tau = threat_taus(options, tau, tau_threat)
        if tau_delta is not None:                   # pipeline_decisions / posture: a per-row threshold shift
            tau = tau + np.asarray(tau_delta, dtype=np.float64)
        playing = any_allowed & ((p > tau) | stalled)
        if options.gate_decode != 'threshold':
            if step_s is None:
                raise ValueError('hazard gate decoding requires the decision step (seconds)')
            if options.gate_decode == 'hazard':
                playing = any_allowed & stalled
            for r in np.flatnonzero(any_allowed & ~playing):   # a draw only where a play is possible
                playing[r] = hazard[r] = hazard_draw(options, p[r], step_s[r] if np.ndim(step_s) else step_s, rngs[r],
                                                     elixir=None if elixir is None else elixir[r],
                                                     enemy_units=None if enemy_units is None else enemy_units[r],
                                                     threatened=None if threatened is None else threatened[r])
        tau, base_tau = np.broadcast_to(tau, n), np.broadcast_to(base_tau, n)
    if tr is not None:
        for r in range(n):
            tr[r].update(tau=float(tau[r]), hazard=hazard[r])
    out = [None] * n
    # ---- 2. the finishers ----
    if options.lethal_rocket != 'off':
        if lethal is None or t_sec is None or grid is None or card_names is None:
            raise ValueError('lethal_rocket requires per-row crown towers, decision times, the grid and card names')
        for r in np.flatnonzero(any_allowed):
            towers, side, pending, *rest = lethal[r]
            hit = lethal_rocket_choice(options, t_sec[r], card_names[r], allowed[r], towers, side, grid, pending=pending,
                                       own=rest[0] if rest else None, skip=rest[1] if len(rest) > 1 else ())
            if hit is not None:
                out[r] = dict(play=True, slot=hit[0], cell=hit[1],
                              why='lethal_log' if hit[2].get('card') == 'Log' else 'lethal_rocket')
                if sample:
                    out[r]['forced'] = True
                if tr is not None:
                    tr[r].update(rule=out[r]['why'], target=hit[2])
    # ---- 3. rocket_value / rocket_tornado (greedy) ----
    if options.rocket_value > 0:
        if rocket_value is None or grid is None or card_names is None:
            raise ValueError('rocket_value requires per-row boards, the grid and card names')
        hits, lone, combos = {}, {}, {}
        for r in range(n):
            if out[r] is not None:                  # a finisher fired: the rule is not asked (live order)
                continue
            hit = rocket_value_choice(options, card_names[r], allowed[r], rocket_value[r][0], grid, pending=rocket_value[r][1],
                                      holder=rocket_value[r][2], playing=bool(playing[r]))
            if hit is not None and options.rocket_tornado not in ('only', 'rocket_only'):      # those modes: the combo trigger alone
                hits[r] = hit
            elif hit is not None:
                lone[r] = hit                       # ... unless rocket_tornado_lone best picks it over the combo (below)
            if options.rocket_tornado == 'off' or not any_allowed[r]:
                continue
            bs, pending, holder = rocket_value[r]
            if (r in hits and options.rocket_tornado_lone == 'skip') or (options.rocket_value_idle == 'on' and bool(playing[r])) or (
                    options.rocket_value_threat == 'on' and not getattr(holder, 'rv_threatened', False)):
                continue
            hit = rocket_tornado_choice(options, card_names[r], allowed[r], bs, grid, pending)
            if hit is None:
                continue
            if hit[5] == 'lone':                    # rocket_tornado_lone best: the lone Rocket (rocket_value_choice's hit) is the better play
                if r in lone:
                    hits[r] = lone[r]
                continue
            hits.pop(r, None)
            combos[r] = hit
        if hits:
            ids = sorted(hits)
            logits = cell_logits(ids, [hits[r][0] for r in ids])
            for j, r in enumerate(ids):
                lg = logits[j] if cell_guard is None else cell_guard(r, hits[r][0], logits[j:j + 1])
                out[r] = dict(play=True, slot=hits[r][0], cell=rocket_value_cell(lg, hits[r][1]), why='rocket_value')
                if tr is not None:
                    tr[r].update(rule='rocket_value', value=hits[r][2])
        for r, hit in combos.items():
            after, within = rocket_tornado_timing(hit[3])
            first, second = (hit[0], hit[1]) if hit[5] == 'rocket' else (hit[1], hit[0])    # order 'tornado': the Rocket follows
            d = dict(play=True, slot=first, cell=hit[2], why='rocket_tornado')
            if options.rocket_tornado != 'rocket_only':
                f = (follow_up or _sim_follow_up)(r, first, second, hit[2], after, within, hit[5], hit[4])
                if f is None:                       # the second card left the hand: no combo, the model decides
                    continue
                d['follow_ups'] = [f]
            out[r] = d
            if tr is not None:
                tr[r].update(rule='rocket_tornado', value=hit[4], window=hit[3], order=hit[5])
    # ---- 4. the model's card and cell ----
    model_rows = [r for r in range(n) if out[r] is None]
    slots = [-1] * n
    cells = np.full(n, -1, dtype=np.int64)
    if sample:
        with torch.no_grad():
            card_logits = heads['card'].clone()
            card_logits = card_logits.masked_fill(~torch.from_numpy(allowed).to(card_logits.device), float('-inf'))
            card_probs = torch.softmax(card_logits.double() / T, dim=-1).cpu().numpy()
            for r in model_rows:
                if playing[r] and 'card' not in heads_sampled:
                    slots[r] = int(card_logits[r].argmax().item())  # greedy card, as live_decide
                elif playing[r]:
                    probs = card_probs[r]
                    c = int(s['rngs'][r].choice(len(probs), p=probs))
                    slots[r] = c
                    lp_card[r] = math.log(probs[c])
            play_idx = [r for r in model_rows if playing[r]]
            if play_idx:
                cl = cell_logits(play_idx, [slots[r] for r in play_idx])
                cell_probs = torch.softmax(cl.double() / T, dim=-1).cpu().numpy()
                gob = []
                for j, r in enumerate(play_idx):
                    if 'cell' not in heads_sampled:
                        cells[r] = int(cell_probs[j].argmax())      # greedy cell, as live_decide
                    else:
                        probs = cell_probs[j]
                        cells[r] = x = int(s['rngs'][r].choice(len(probs), p=probs))
                        lp_cell[r] = math.log(probs[x])
                    if options.barrel_lane == 'on' and card_names is not None and is_barrel_answer(card_names[r][slots[r]]):
                        gob.append((j, r))
                for j, r in gob:                    # barrel_lane: the answer goes to the barrel's lane (forced)
                    pts = [(bx * 18.0, by * 32.0) for bx, by in barrel_landings(projectiles[r], barrel_id)] \
                        if projectiles is not None else []
                    pts += list(barrel_goblins[r]) if barrel_goblins is not None else []
                    c = barrel_lane_cell(cl[j], pts, int(cells[r]), grid)
                    if c is not None and c != int(cells[r]):
                        cells[r] = c
                        out[r] = 'forced'
    else:
        for r in model_rows:
            slots[r] = choose_slot(heads['card'][r], allowed[r], options, rngs[r], playing=bool(playing[r]))
        ids = np.array([r for r in model_rows if playing[r]], dtype=np.int64)
        log_air_rows = set()                        # rows log_air re-aimed or blocked (why='log_air')
        blocked = set()
        while len(ids):
            names = [card_names[r][slots[r]] for r in ids] if card_names is not None else [''] * len(ids)
            if (options.spell_aim != 'argmax' or options.xbow_class != 'argmax' or options.log_aim != 'argmax'
                    or options.xbow_dead_lane != 'allow' or options.rocket_dead_target != 'allow') and card_names is None:
                raise ValueError('Rocket aim / X-Bow class / Log aim / dead-lane / dead-target blocks require explicit '
                                 'public card identities')
            logits = cell_logits(ids, [slots[r] for r in ids])
            if cell_guard is not None:
                logits = torch.cat([cell_guard(int(r), slots[r], logits[j:j + 1]) for j, r in enumerate(ids)])
            barrels = None
            if options.uses_barrels:
                if projectiles is None:
                    raise ValueError('log_barrel / log_air require the model projectile tokens of every row')
                barrels = [barrel_landings(projectiles[r], barrel_id) for r in ids]
            moved = []
            ctx = dict(rngs=[rngs[r] for r in ids], grid=grid, barrels=barrels,
                       barrel_goblins=None if barrel_goblins is None else [barrel_goblins[r] for r in ids],
                       enemy_alive=None if enemy_alive is None else [enemy_alive[r] for r in ids],
                       # only the rows that read them (live builds these boards lazily: a Rocket / a Log row)
                       rocket_boards=None if rocket_boards is None else [
                           rocket_boards[r] if str(nm).lower() == 'rocket' else None for r, nm in zip(ids, names)],
                       log_air_boards=None if log_air_boards is None else [
                           log_air_boards[r] if is_log(nm) else None for r, nm in zip(ids, names)])
            cells[ids] = (choose or choose_cells)(logits, names, options, log_air_moved=moved, **ctx).cpu().numpy()
            log_air_rows.update(int(ids[j]) for j in moved)
            if tr is not None:
                for j, r in enumerate(ids):
                    tr[r].update(logits=logits[j:j + 1], name=names[j], moved=j in moved)
            for j, r in enumerate(ids):
                if cells[r] == LOG_AIR_BLOCKED:     # block: WAIT, never another card
                    playing[r], cells[r] = False, -1
                    blocked.add(int(r))
                    if tr is not None:              # live logs the Log's aim without log_air
                        one = {k: (v[j:j + 1] if isinstance(v, list) else v) for k, v in ctx.items()}
                        tr[r]['blocked_cell'] = int(choose_cells(logits[j:j + 1], [names[j]],
                                                                 replace(options, log_air='off'), **one)[0])
            # xbow_dead_lane / rocket_dead_target left an X-Bow / Rocket no cell (-1): it is not chosen; the next card by
            # the model's own ranking is (choose_slot without it), else WAIT.
            ids = ids[(cells[ids] < 0) & playing[ids]]
            if len(ids):
                allowed = allowed.copy()
            for r in ids:
                if tr is not None:
                    tr[r]['dropped'] = 'xbow_dead_lane' if is_xbow(card_names[r][slots[r]]) else 'rocket_dead_target'
                allowed[r, slots[r]] = False
                nxt = choose_slot(heads['card'][r], allowed[r], options, rngs[r], playing=True)
                if nxt < 0:
                    playing[r] = False
                else:
                    slots[r] = nxt
            ids = ids[playing[ids]]
        if tr is not None:                          # live logs a WAIT's aim: argmax, no RNG-drawing or blocking option
            waits = [r for r in model_rows if not playing[r] and slots[r] >= 0 and r not in blocked]
            if waits:
                plain = replace(options, xbow_class='argmax', xbow_dead_lane='allow', rocket_dead_target='allow',
                                log_air='off')
                logits = cell_logits(waits, [slots[r] for r in waits])
                names = [card_names[r][slots[r]] if card_names is not None else '' for r in waits]
                barrels = [barrel_landings(projectiles[r], barrel_id) for r in waits] if plain.uses_barrels else None
                got = choose_cells(logits, names, plain, grid=grid, barrels=barrels,
                                   barrel_goblins=None if barrel_goblins is None else [barrel_goblins[r] for r in waits])
                for j, r in enumerate(waits):
                    tr[r]['wait_cell'] = int(got[j])
    res = [None] * n
    for r in range(n):
        if isinstance(out[r], dict):
            res[r] = out[r]
            continue
        res[r] = dict(play=bool(playing[r]), slot=slots[r], cell=int(cells[r]),
                      why=('no_affordable' if not any_allowed[r] else 'wait' if not playing[r]
                           else 'stall' if stalled[r] and (sample or p[r] <= tau[r]) else
                           'gate' if sample else
                           'tau_threat' if p[r] > tau[r] and p[r] <= base_tau[r] and options.tau_threatened is not None
                           else 'gate' if p[r] > tau[r] else 'hazard'))
        if out[r] == 'forced':
            res[r]['forced'] = True
    if not sample:
        for r in log_air_rows:
            res[r]['why'] = 'log_air'
    if sample:                                      # the rollout record; a forced row keeps its draws' log-probs
        rules = options != DecisionOptions()        # (rl_royale leaves forced rows out of PPO)
        for r in range(n):
            d = res[r]
            d.update(allowed=allowed[r].copy(), stalled=bool(stalled[r]), gate_sampled=bool(gate_sampled[r]),
                     lp_gate=float(lp_gate[r]), lp_card=float(lp_card[r]), lp_cell=float(lp_cell[r]), p_gate=float(p[r]),
                     T=T)
            if rules:
                d['forced'] = bool(d.get('forced', False))
    if trace is not None:
        trace.extend(tr)
    return res


def _sim_follow_up(r, first, second, cell, after, within, order, value):
    from .e1_eval import follow_up_spec
    return follow_up_spec(second, cell, after, within)


def decide_batch(model, enc, heads, p, allowed, stalled, *, tau, device, options, rngs, card_names, **context):
    """The SIM's greedy decide (e1_eval.live_decide_batch with decision options; forks; SIM eval): ``decide`` on the
    model's batched cell logits. card_levels is LIVE-ONLY: the SIM's own cards decide."""
    if options.card_levels is not None:
        options = replace(options, card_levels=None)
    barrel_id = getattr(model, 'gid', {}).get(BARREL_KEY) if options.uses_barrels else None
    return decide(heads, p, allowed, stalled, tau=tau, options=options, rngs=rngs, card_names=card_names,
                  cell_logits=model_cell_logits(model, enc, device), barrel_id=barrel_id, **context)


def match_kwargs(matches):
    """Per-match RNGs, never a batch-wide stream; public deck names for aiming."""
    cfg = matches[0].cfg
    options = options_from_config(cfg)
    if options.card_levels is not None:             # card_levels is LIVE-ONLY (a live bundle in a SIM run is ignored)
        options = replace(options, card_levels=None)
    if not options.active:
        return {}
    from .e1_eval import obs_seed
    rngs = []
    for match in matches:
        if replace(options_from_config(match.cfg), card_levels=None) != options:
            raise ValueError('mixed decision options in one policy batch')
        if not hasattr(match, 'rng_decision_options'):
            seed = obs_seed('decision_options:' + match.tag, match.k)
            match.rng_decision_options = np.random.default_rng(np.random.SeedSequence(
                [seed, int(cfg.get('decision_seed', 0))]))
        rngs.append(match.rng_decision_options)
    out = dict(decision_options=options, rngs=rngs, card_names=[list(m.deck.cards) for m in matches])
    if cfg.get('pipeline_tau_delta') and any(getattr(m, 'pend', None) for m in matches):   # only while a play is pending
        out['tau_delta'] = [float(cfg['pipeline_tau_delta']) if getattr(m, 'pend', None) else 0.0 for m in matches]
    if options.gate_decode != 'threshold':
        out['step_s'] = 0.05 * int(cfg['decide_every'])   # the SIM decides every decide_every ticks
        if any(getattr(m, '_hz_step_ticks', None) is not None for m in matches):   # pipeline_decisions: the real step per row
            out['step_s'] = [0.05 * (cfg['decide_every'] if getattr(m, '_hz_step_ticks', None) is None else m._hz_step_ticks)
                             for m in matches]
        out['elixir'] = [float(m._cur[1].my_elixir) for m in matches]
        out['enemy_units'] = [enemy_unit_count(m._cur[1]) for m in matches]
        if threat_on(options):              # per-match state on the match, the decision's engine BoardState (my frame)
            for m in matches:
                m.threat_state, m.threatened = tower_threat(options, getattr(m, 'threat_state', None), m._cur[1])
            out['threatened'] = [m.threatened for m in matches]
    if options.tau_threatened is not None:  # the decision's engine BoardState (my frame); per-match state on the match
        for m in matches:
            m.tau_threat_state, m.tau_threat = tau_threat_state(getattr(m, 'tau_threat_state', None), m._cur[1])
        out['tau_threat'] = [m.tau_threat for m in matches]
    if (options.tau_phase is not None or options.xbow_class != 'argmax' or options.xbow_dead_lane != 'allow'
            or options.rocket_dead_target != 'allow'):
        boards = [m._cur[1] for m in matches]    # the prepared decision's engine BoardState (my frame)
        out.update(t_sec=[float(b.t_sec) for b in boards], grid=cfg['grid'],
                   enemy_alive=[tuple(bool(t.alive) for t in b.towers[3:6]) for b in boards])
        if options.rocket_dead_target != 'allow':      # glitch-filtered towers (state on the match), bodies, king HP
            rb = []
            for m, b in zip(matches, boards):
                m.princess_dead_state, alive = princess_dead_state(getattr(m, 'princess_dead_state', None), b)
                crown = ((m.state or {}).get('episode') or {}).get('crown_towers', [])
                rb.append((alive, enemy_body_tiles(b), rocket_kills_king(crown, int(m.side))))
            out['rocket_boards'] = rb
    if options.lethal_rocket != 'off':  # the model board's time (as tau_phase); tower HP from the decision tick's raw state
        out.update(t_sec=[float(m._cur[1].t_sec) for m in matches], grid=cfg['grid'],
                   lethal=[(((m.state or {}).get('episode') or {}).get('crown_towers', []), int(m.side),
                            getattr(m, 'pending', None) is not None or bool(getattr(m, 'pend', None))) for m in matches])
        if options.lethal_log == 'on' or options.lethal_quiet > 0:   # public tower HP per decision tick (live's history)
            for row, m in zip(out['lethal'], matches):
                m._lethal_hp_hist = record_hp(getattr(m, '_lethal_hp_hist', None), int(m._cur[0]),
                                              enemy_princess_hps(row[0], row[1]))
        if options.lethal_log == 'on':  # + my accepted plays (landing tick, deck slot, my-frame xy) for the in-flight guard
            out['lethal'] = [row + ([(m.deck.cards[s], x, y, land * 0.05, hp_after(m._lethal_hp_hist, land))
                                     for land, s, x, y in m.done_plays[-8:]],)
                             for row, m in zip(out['lethal'], matches)]
        if options.lethal_quiet > 0:    # owner 10-25 (live_gen_v2.lethal_rocket): no finisher on a princess something else is hitting
            out['lethal'] = [(row + (None,) if len(row) == 3 else row)
                             + (recently_hit(m._lethal_hp_hist, m._lethal_hp_hist[-1][0], round(options.lethal_quiet / 0.05)),)
                             for row, m in zip(out['lethal'], matches)]
    if options.log_air != 'off':        # the enemy board the Log's corridor is judged on (the decision BoardState, my frame)
        out.update(grid=cfg['grid'], log_air_boards=[
            log_air_board(m._cur[1], log_air_ground_child_tiles((getattr(m, 'state', None) or {}).get('entities'), getattr(m, 'side', 0)))
            for m in matches])
    if options.barrel_lane == 'on':     # owner 10-25: the goblins on my half (the decision BoardState, my frame)
        out.update(grid=cfg['grid'], barrel_goblins=[barrel_goblin_tiles(m._cur[1]) for m in matches])
    if options.rocket_value > 0:        # the decision's engine BoardState (hp_frac known, as live's): same board as tau_phase
        out.update(grid=cfg['grid'], rocket_value=[(m._cur[1], getattr(m, 'pending', None) is not None, m) for m in matches])
    if options.uses_barrels:            # the very projectile tokens the model saw (gen_row, fv >= 4), as live's batch
        rows = [getattr(m, '_gen_row', None) for m in matches]
        if any(r is None or 'projectiles' not in r for r in rows):
            raise ValueError('log_barrel requires generalist rows with public projectile tokens (feature_version >= 4)')
        out.update(grid=cfg['grid'], projectiles=[r['projectiles'] for r in rows])
    return out
