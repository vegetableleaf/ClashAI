"""Opt-in inference choices. No gate, tower-HP, card-priority or reward rules."""
from __future__ import annotations

from dataclasses import dataclass
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
    gate_decode: str = 'threshold'          # 'hazard' / 'hazard_below_tau': execute the gate's learned play RATE (W4)
    gate_hazard_min_elixir: float = 0.0     # hazard draws only at own elixir >= this (0 = everywhere)
    gate_hazard_quiet: bool = False         # hazard draws only with no enemy unit on the board (public bodies)
    gate_hazard_threatened: float = 0.0     # hazard draws ALSO while a tower of mine lost HP within this many s (0 = off)
    gate_hazard_threat_radius: float = 0.0  # ... or while an enemy unit is within this many tiles of my alive tower
    lethal_rocket: str = 'off'
    lethal_log: str = 'off'                 # 'on': the lethal finisher also uses the Log (rides on lethal_rocket's mode)
    xbow_dead_lane: str = 'allow'           # 'block': no X-Bow cell that reaches only the king / a destroyed princess
    rocket_dead_target: str = 'allow'       # 'block': no Rocket on a fallen tower / the king with nothing alive in it
    tau_threatened: Optional[float] = None  # gate threshold while threatened (tau_threat_state); None = the phase tau
    rocket_value: float = 0.0               # > 0: Rocket a clump of >= this much enemy elixir value on my half (rocket_value_choice)
    rocket_value_mode: str = 'cost'         # 'damage': the share of each body's value the Rocket destroys; 'kill': only bodies it kills
    rocket_value_min_y: float = 16.0        # the blast centre must be at board y >= this (16 = my half; 21+ = near my towers)
    rocket_value_max_left: float = 99.0     # no fire when the bodies in the blast would KEEP more than this much value after the Rocket
    rocket_value_hitbox: str = 'centre'     # 'edge': a body is in the blast when its hitbox touches the radius
    rocket_value_lead: str = 'off'          # 'on' / 'drift' / 'blend': aim at where the bodies will be when the Rocket lands
    rocket_value_idle: str = 'off'          # 'on': only at a decision where the model itself would not play (displaces nothing)
    rocket_value_min_elixir: float = 0.0    # fire only with at least this much elixir (the Rocket leaves the rest)

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
        if self.gate_decode not in ('threshold', 'hazard', 'hazard_below_tau'):
            raise ValueError('gate_decode must be threshold, hazard or hazard_below_tau')
        if not math.isfinite(self.gate_hazard_min_elixir) or not 0 <= self.gate_hazard_min_elixir <= 10:
            raise ValueError('gate_hazard_min_elixir must be in [0, 10]')
        for k in ('gate_hazard_threatened', 'gate_hazard_threat_radius'):
            if not math.isfinite(getattr(self, k)) or getattr(self, k) < 0:
                raise ValueError(f'{k} must be finite and >= 0')
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
                      ('rocket_value_lead', ('off', 'on', 'drift', 'blend')), ('rocket_value_idle', ('off', 'on'))):
            if getattr(self, k) not in ok:
                raise ValueError(f'{k} must be one of {ok}')
        if not math.isfinite(self.rocket_value_min_elixir) or not 0 <= self.rocket_value_min_elixir <= 10:
            raise ValueError('rocket_value_min_elixir must be in [0, 10]')
        if not math.isfinite(self.rocket_value_min_y) or not 16.0 <= self.rocket_value_min_y <= 32.0:
            raise ValueError('rocket_value_min_y must be in [16, 32] tiles (my half)')
        if not math.isfinite(self.rocket_value_max_left) or self.rocket_value_max_left < 0:
            raise ValueError('rocket_value_max_left must be finite and >= 0 (99 = off)')

    @property
    def active(self):
        return (self.card_choice != 'argmax' or self.spell_aim != 'argmax' or self.tau_phase is not None
                or self.xbow_class != 'argmax' or self.log_aim != 'argmax' or self.gate_decode != 'threshold'
                or self.lethal_rocket != 'off' or self.xbow_dead_lane != 'allow' or self.rocket_dead_target != 'allow'
                or self.tau_threatened is not None or self.rocket_value > 0)


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
    parser.add_argument('--rocket-value-max-left', type=float, default=99.0, metavar='L',
                        help='no fire when the bodies in the best blast would still hold more than L elixir of value after the '
                             'Rocket (a Golem keeps 5.7 of its 8): the Rocket then only strips the support and the elixir it '
                             'cost is missing against the tank. 99 = off')
    parser.add_argument('--rocket-value-min-y', type=float, default=16.0, metavar='Y',
                        help='the blast centre must be at board y >= Y tiles (me at the bottom, my half starts at 16, my princess '
                             'towers stand at 25.5): a deep centre is short in the air and on a clump already at my towers')
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


def my_rocket_damage(crown_towers, side):
    """My Rocket's crown-tower damage from my own tower max HP (lethal_rocket_target's level rule), or None."""
    from .body_identity import level_of_factor
    mine = next((t for t in crown_towers if int(t['side']) == side and t.get('max_hp')), None)
    level = mine and level_of_factor(float(mine['max_hp']) / (4824.0 if mine.get('type') == 'king' else 3052.0))
    return None if level is None else rocket_tower_damage(level)


def rocket_kills_king(crown_towers, side):
    """True when the alive enemy king's public HP <= my Rocket's crown-tower damage (the never-the-king exception)."""
    damage = my_rocket_damage(crown_towers, side)
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


def choose_cells(logits, card_names, options, *, rngs=None, enemy_alive=None, grid=None, barrels=None,
                 rocket_boards=None):
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
    return result


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


def lethal_rocket_target(crown_towers, side, card='Rocket', own=None, t_sec=None):
    """The alive ENEMY PRINCESS my Rocket finishes in one hit, lowest HP first -> dict(lane (my frame), hp, damage,
    level), else None. ``crown_towers``: raw ``episode.crown_towers`` rows (side, type, x, y in 1/1000 tile, hp, max_hp;
    live_mem.to_observe / RoyaleSim raw()). My card level = my own tower max HP (from_engine's level factor: level 11
    = 3052 princess / 4824 king -> body_identity.level_of_factor); Rocket assumed at that level. Kings never qualify.
    ``own`` (lethal_log on): my accepted plays -> a princess my own Rocket / Log in flight will finish is skipped."""
    from .body_identity import level_of_factor
    from .obs_contract import _engine_xy
    mine = next((t for t in crown_towers if int(t['side']) == side and t.get('max_hp')), None)
    level = mine and level_of_factor(float(mine['max_hp']) / (4824.0 if mine.get('type') == 'king' else 3052.0))
    if level is None:
        return None
    damage, best = rocket_tower_damage(level, card), None
    covered = in_flight_damage(own, t_sec, level, enemy_princess_hps(crown_towers, side)) if own else {}
    for t in crown_towers:
        if int(t['side']) == side or t.get('type') != 'princess' or t.get('destroyed') or not 0 < t['hp'] <= damage:
            continue
        x, _ = _engine_xy(float(t['x']), float(t['y']), side == 1)
        if covered.get('L' if x < .5 else 'R', 0) >= t['hp']:
            continue                                # my own spell already on its way finishes it
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


def in_flight_damage(own, t_sec, level, hp_now=None):
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
                damage = rocket_tower_damage(level, 'Rocket' if rocket else 'Log')
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


def lethal_log_choice(options, t_sec, names, allowed, crown_towers, side, grid, own=None):
    """lethal_log: -> (slot, cell, target with card='Log') or None, under lethal_rocket's phase / crown rules."""
    slots = [i for i, n in enumerate(names) if n is not None and is_log(n) and allowed[i]]
    if not slots or not _lethal_phase(options, t_sec, crown_towers, side, LOG_HIT_TICKS):
        return None
    target = lethal_rocket_target(crown_towers, side, 'Log', own, t_sec)
    return None if target is None else (slots[0], lethal_log_cell(target['lane'], grid), target)


def lethal_rocket_choice(options, t_sec, names, allowed, crown_towers, side, grid, pending=False, own=None):
    """-> (slot, cell, target) when lethal_rocket fires, else None: overtime (phase_index 2, the tau_phase edge), no
    card pending, an affordable Rocket slot (``allowed``: in hand and cost <= integer elixir), a lethal princess.
    ``ot_behind`` also fires in regulation while ``crowns_behind`` and the Rocket lands before tick 3600 (cutoff above)."""
    if options.lethal_rocket == 'off' or pending:
        return None
    if options.lethal_log != 'on':
        own = None                                  # off: today's rule exactly (no in-flight guard)
    else:                                           # the Log first: cheaper and it hits sooner
        hit = lethal_log_choice(options, t_sec, names, allowed, crown_towers, side, grid, own)
        if hit is not None:
            return hit
    if phase_index([t_sec])[0] != 2:
        if (options.lethal_rocket != 'ot_behind' or round(t_sec / 0.05) + ROCKET_FLIGHT_TICKS > REGULATION_END_TICK
                or not crowns_behind(crown_towers, side)):
            return None
    slots = [i for i, n in enumerate(names) if n is not None and str(n).lower() == 'rocket' and allowed[i]]
    target = (lethal_rocket_target(crown_towers, side, own=own, t_sec=t_sec) if own else
              lethal_rocket_target(crown_towers, side)) if slots else None
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


def best_rocket_clump(bodies, grid, hitbox='centre', lead=None, min_y=MY_HALF_MIN_Y_TILES, with_left=False):
    """-> (value, eligible) for the best Rocket blast CENTRED on my half: its value, and the [2304] bool cells (on my half) whose
    blast covers every body of that best clump. (0.0, None) with no body worth anything. ``hitbox`` 'centre' counts a body whose
    centre is within the Rocket radius, 'edge' one whose hitbox touches it (radius + the body's collision radius). ``lead`` =
    None, or the (decision tick, history, mode) of rocket_track / 'drift': the bodies are moved to where they will be when a Rocket aimed at the
    cell lands (rocket_lands_in at the cell, found by one refinement from the static best cell)."""
    if not len(bodies):
        return (0.0, None, 0.0) if with_left else (0.0, None)
    x, y = cell_centres_tiles(grid)
    reach = rocket_radius_tiles() + (bodies[:, 4] if hitbox == 'edge' else np.zeros(len(bodies)))
    mine = y >= min_y

    def blast(pos):
        inside = np.hypot(x[:, None] - pos[None, :, 0], y[:, None] - pos[None, :, 1]) <= reach[None, :]
        return inside, np.where(mine, inside @ bodies[:, 3], -1.0)

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
    return (float(value[best]), eligible, float(inside[best] @ bodies[:, 5])) if with_left else (float(value[best]), eligible)


def rocket_value_choice(options, names, allowed, bs, grid, pending=False, holder=None, playing=False):
    """-> (slot, eligible cells, value) when rocket_value fires, else None: an affordable Rocket slot (``allowed``), no card
    pending, and the best blast centred on my half (best_rocket_clump) holds >= options.rocket_value. Public bodies only; the
    enemy king is out of reach (a centre on my half is >= 13 tiles from it). With lead on, ``holder`` keeps the decision history
    (rocket_track); called at EVERY decision, even with no Rocket in hand, so the history has no gaps."""
    if options.rocket_value <= 0:
        return None
    slots = [i for i, n in enumerate(names) if n is not None and str(n).lower() == 'rocket' and allowed[i]]
    track = options.rocket_value_lead in ('on', 'blend') and holder is not None
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
    if float(bs.my_elixir) + 1e-9 < options.rocket_value_min_elixir:
        return None
    value, eligible, left = best_rocket_clump(bodies, grid, options.rocket_value_hitbox, lead, options.rocket_value_min_y, True)
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


@torch.no_grad()
def decide_batch(model, enc, heads, p, allowed, stalled, *, tau, device, options, rngs, card_names,
                 t_sec=None, enemy_alive=None, grid=None, projectiles=None, step_s=None, elixir=None,
                 enemy_units=None, lethal=None, threatened=None, rocket_boards=None, tau_threat=None, rocket_value=None):
    """Optional branch of e1_eval's live decision; default branch remains untouched.
    ``t_sec`` (tau_phase) and ``enemy_alive`` [(K, L, R) alive] + ``grid`` (xbow_class) are per-row match context;
    ``projectiles`` (log_aim) = each row's model projectile tokens, decoded with the model's own card vocabulary.
    ``lethal`` (lethal_rocket) = per row (raw crown towers, my side, a card pending) for ``lethal_rocket_choice``.
    ``rocket_value`` = per row (the decision BoardState, a card pending, the match keeping the lead history) for ``rocket_value_choice``."""
    base_tau = tau = gate_taus(options, tau, t_sec, len(allowed))
    tau = threat_taus(options, tau, tau_threat)
    playing = allowed.any(axis=1) & ((np.asarray(p) > tau) | stalled)
    if options.gate_decode != 'threshold':
        if step_s is None:
            raise ValueError('hazard gate decoding requires the decision step (seconds)')
        if options.gate_decode == 'hazard':
            playing = allowed.any(axis=1) & stalled
        for r in np.flatnonzero(allowed.any(axis=1) & ~playing):   # a draw only where a play is possible
            playing[r] = hazard_draw(options, p[r], step_s, rngs[r],
                                     elixir=None if elixir is None else elixir[r],
                                     enemy_units=None if enemy_units is None else enemy_units[r],
                                     threatened=None if threatened is None else threatened[r])
    slots = [choose_slot(heads['card'][r], allowed[r], options, rngs[r], playing=bool(playing[r]))
             for r in range(len(allowed))]
    cells = np.full(len(slots), -1, dtype=np.int64)
    ids = np.flatnonzero(playing)
    while len(ids):
        index = torch.as_tensor(ids, device=device)
        sub_enc = {k: v[index] for k, v in enc.items()}
        slot_tensor = torch.tensor([slots[r] for r in ids], device=device)
        logits = model.cell_logits(sub_enc, slot_tensor)
        names = [card_names[r][slots[r]] for r in ids] if card_names is not None else [''] * len(ids)
        if (options.spell_aim != 'argmax' or options.xbow_class != 'argmax' or options.log_aim != 'argmax'
                or options.xbow_dead_lane != 'allow' or options.rocket_dead_target != 'allow') and card_names is None:
            raise ValueError('Rocket aim / X-Bow class / Log aim / dead-lane / dead-target blocks require explicit '
                             'public card identities')
        barrels = None
        if options.log_aim != 'argmax':
            if projectiles is None:
                raise ValueError('log_barrel requires the model projectile tokens of every row')
            barrel_id = getattr(model, 'gid', {}).get(BARREL_KEY)
            barrels = [barrel_landings(projectiles[r], barrel_id) for r in ids]
        cells[ids] = choose_cells(logits, names, options, rngs=[rngs[r] for r in ids], grid=grid, barrels=barrels,
                                  enemy_alive=None if enemy_alive is None else [enemy_alive[r] for r in ids],
                                  rocket_boards=None if rocket_boards is None else [rocket_boards[r] for r in ids]
                                  ).cpu().numpy()
        # xbow_dead_lane / rocket_dead_target left an X-Bow / Rocket no cell (-1): it is not chosen; the next card by the
        # model's own ranking is (choose_slot without it), else WAIT. Never reached with unmasked SIM logits (neither
        # block ever covers the board).
        ids = ids[cells[ids] < 0]
        if len(ids):
            allowed = allowed.copy()
        for r in ids:
            allowed[r, slots[r]] = False
            nxt = choose_slot(heads['card'][r], allowed[r], options, rngs[r], playing=True)
            if nxt < 0:
                playing[r] = False
            else:
                slots[r] = nxt
        ids = ids[playing[ids]]
    tau, base_tau = np.broadcast_to(tau, len(slots)), np.broadcast_to(base_tau, len(slots))
    out = [dict(play=bool(playing[r]), slot=slots[r], cell=int(cells[r]),
                why=('no_affordable' if slots[r] < 0 else 'wait' if not playing[r]
                     else 'stall' if stalled[r] and p[r] <= tau[r] else
                     'tau_threat' if p[r] > tau[r] and p[r] <= base_tau[r] and options.tau_threatened is not None
                     else 'gate' if p[r] > tau[r] else 'hazard'))
           for r in range(len(slots))]
    if options.rocket_value > 0:    # before lethal_rocket, which overrides it
        if rocket_value is None or grid is None or card_names is None:
            raise ValueError('rocket_value requires per-row boards, the grid and card names')
        hits = {}
        for r in range(len(out)):
            hit = rocket_value_choice(options, card_names[r], allowed[r], rocket_value[r][0], grid, pending=rocket_value[r][1],
                                      holder=rocket_value[r][2], playing=bool(playing[r]))
            if hit is not None:
                hits[r] = hit
        if hits:
            ids = list(hits)
            logits = model.cell_logits({k: v[torch.as_tensor(ids, device=device)] for k, v in enc.items()},
                                       torch.tensor([hits[r][0] for r in ids], device=device))
            for j, r in enumerate(ids):
                out[r] = dict(play=True, slot=hits[r][0], cell=rocket_value_cell(logits[j], hits[r][1]), why='rocket_value')
    if options.lethal_rocket != 'off':
        if lethal is None or t_sec is None or grid is None or card_names is None:
            raise ValueError('lethal_rocket requires per-row crown towers, decision times, the grid and card names')
        for r in range(len(out)):
            towers, side, pending, *own = lethal[r]
            hit = lethal_rocket_choice(options, t_sec[r], card_names[r], allowed[r], towers, side, grid, pending=pending,
                                       own=own[0] if own else None)
            if hit is not None:
                out[r] = dict(play=True, slot=hit[0], cell=hit[1],
                              why='lethal_log' if hit[2].get('card') == 'Log' else 'lethal_rocket')
    return out


def match_kwargs(matches):
    """Per-match RNGs, never a batch-wide stream; public deck names for aiming."""
    cfg = matches[0].cfg
    options = options_from_config(cfg)
    if not options.active:
        return {}
    from .e1_eval import obs_seed
    rngs = []
    for match in matches:
        if options_from_config(match.cfg) != options:
            raise ValueError('mixed decision options in one policy batch')
        if not hasattr(match, 'rng_decision_options'):
            seed = obs_seed('decision_options:' + match.tag, match.k)
            match.rng_decision_options = np.random.default_rng(np.random.SeedSequence(
                [seed, int(cfg.get('decision_seed', 0))]))
        rngs.append(match.rng_decision_options)
    out = dict(decision_options=options, rngs=rngs, card_names=[list(m.deck.cards) for m in matches])
    if options.gate_decode != 'threshold':
        out['step_s'] = 0.05 * int(cfg['decide_every'])   # the SIM decides every decide_every ticks
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
                            getattr(m, 'pending', None) is not None) for m in matches])
        if options.lethal_log == 'on':  # + my accepted plays (landing tick, deck slot, my-frame xy) for the in-flight guard
            for row, m in zip(out['lethal'], matches):   # public tower HP per decision tick -> the HP each spell landed on
                m._lethal_hp_hist = record_hp(getattr(m, '_lethal_hp_hist', None), int(m._cur[0]),
                                              enemy_princess_hps(row[0], row[1]))
            out['lethal'] = [row + ([(m.deck.cards[s], x, y, land * 0.05, hp_after(m._lethal_hp_hist, land))
                                     for land, s, x, y in m.done_plays[-8:]],)
                             for row, m in zip(out['lethal'], matches)]
    if options.rocket_value > 0:        # the decision's engine BoardState (hp_frac known, as live's): same board as tau_phase
        out.update(grid=cfg['grid'], rocket_value=[(m._cur[1], getattr(m, 'pending', None) is not None, m) for m in matches])
    if options.log_aim != 'argmax':     # the very projectile tokens the model saw (gen_row, fv >= 4), as live's batch
        rows = [getattr(m, '_gen_row', None) for m in matches]
        if any(r is None or 'projectiles' not in r for r in rows):
            raise ValueError('log_barrel requires generalist rows with public projectile tokens (feature_version >= 4)')
        out.update(grid=cfg['grid'], projectiles=[r['projectiles'] for r in rows])
    return out
