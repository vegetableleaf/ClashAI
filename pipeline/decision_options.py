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
        if self.lethal_log not in ('off', 'on'):
            raise ValueError('lethal_log must be off or on')

    @property
    def active(self):
        return (self.card_choice != 'argmax' or self.spell_aim != 'argmax' or self.tau_phase is not None
                or self.xbow_class != 'argmax' or self.log_aim != 'argmax' or self.gate_decode != 'threshold'
                or self.lethal_rocket != 'off' or self.xbow_dead_lane != 'allow')


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


def choose_cells(logits, card_names, options, *, rngs=None, enemy_alive=None, grid=None, barrels=None):
    """Aim only after card selection. Other cards retain exact argmax behaviour.
    ``barrels`` (log_aim): per row, the enemy Goblin Barrel landing points from ``barrel_landings``.
    xbow_dead_lane 'block': X-Bow rows lose ``xbow_dead_lane_cells`` before any X-Bow aim; a row with no finite cell
    left returns -1 (the caller then drops that X-Bow and takes the next card)."""
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
    if options.spell_aim == 'argmax':
        return result
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
    return result


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


def lethal_rocket_target(crown_towers, side, card='Rocket'):
    """The alive ENEMY PRINCESS my Rocket finishes in one hit, lowest HP first -> dict(lane (my frame), hp, damage,
    level), else None. ``crown_towers``: raw ``episode.crown_towers`` rows (side, type, x, y in 1/1000 tile, hp, max_hp;
    live_mem.to_observe / RoyaleSim raw()). My card level = my own tower max HP (from_engine's level factor: level 11
    = 3052 princess / 4824 king -> body_identity.level_of_factor); Rocket assumed at that level. Kings never qualify."""
    from .body_identity import level_of_factor
    from .obs_contract import _engine_xy
    mine = next((t for t in crown_towers if int(t['side']) == side and t.get('max_hp')), None)
    level = mine and level_of_factor(float(mine['max_hp']) / (4824.0 if mine.get('type') == 'king' else 3052.0))
    if level is None:
        return None
    damage, best = rocket_tower_damage(level, card), None
    for t in crown_towers:
        if int(t['side']) == side or t.get('type') != 'princess' or t.get('destroyed') or not 0 < t['hp'] <= damage:
            continue
        x, _ = _engine_xy(float(t['x']), float(t['y']), side == 1)
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
# box reaches y 6.8, inside the princess's 1-tile collision circle at 6.5 (0.7-tile margin; x margin 2.95). MEASURED live:
# casts at (3.5 | 14.5, 17.5) are the bot's commonest tower Logs and hit (553 / 563 HP drops of 35/51). Hit time after
# landing: 3 tiles airborne at 0.36 tile/tick (9 ticks, spells.SPELL_AS_DEPLOY_LAUNCH_MODEL) + the landing tick + 47
# roll steps of 0.2 tile until the front edge meets the tower = 57 ticks; MEASURED live hand rotation -> HP drop median
# 62 (snapshots every ~10 ticks: an upper bound).
LOG_CAST_Y_TILES = 17.5
LOG_HIT_TICKS = 57


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


def lethal_log_choice(options, t_sec, names, allowed, crown_towers, side, grid):
    """lethal_log: -> (slot, cell, target with card='Log') or None, under lethal_rocket's phase / crown rules."""
    slots = [i for i, n in enumerate(names) if n is not None and is_log(n) and allowed[i]]
    if not slots or not _lethal_phase(options, t_sec, crown_towers, side, LOG_HIT_TICKS):
        return None
    target = lethal_rocket_target(crown_towers, side, 'Log')
    return None if target is None else (slots[0], lethal_log_cell(target['lane'], grid), target)


def lethal_rocket_choice(options, t_sec, names, allowed, crown_towers, side, grid, pending=False):
    """-> (slot, cell, target) when lethal_rocket fires, else None: overtime (phase_index 2, the tau_phase edge), no
    card pending, an affordable Rocket slot (``allowed``: in hand and cost <= integer elixir), a lethal princess.
    ``ot_behind`` also fires in regulation while ``crowns_behind`` and the Rocket lands before tick 3600 (cutoff above)."""
    if options.lethal_rocket == 'off' or pending:
        return None
    if options.lethal_log == 'on':                  # the Log first: cheaper and it hits sooner
        hit = lethal_log_choice(options, t_sec, names, allowed, crown_towers, side, grid)
        if hit is not None:
            return hit
    if phase_index([t_sec])[0] != 2:
        if (options.lethal_rocket != 'ot_behind' or round(t_sec / 0.05) + ROCKET_FLIGHT_TICKS > REGULATION_END_TICK
                or not crowns_behind(crown_towers, side)):
            return None
    slots = [i for i, n in enumerate(names) if n is not None and str(n).lower() == 'rocket' and allowed[i]]
    target = lethal_rocket_target(crown_towers, side) if slots else None
    if target is None:
        return None
    return slots[0], lethal_rocket_cell(target['lane'], grid), target


@torch.no_grad()
def decide_batch(model, enc, heads, p, allowed, stalled, *, tau, device, options, rngs, card_names,
                 t_sec=None, enemy_alive=None, grid=None, projectiles=None, step_s=None, elixir=None,
                 enemy_units=None, lethal=None, threatened=None):
    """Optional branch of e1_eval's live decision; default branch remains untouched.
    ``t_sec`` (tau_phase) and ``enemy_alive`` [(K, L, R) alive] + ``grid`` (xbow_class) are per-row match context;
    ``projectiles`` (log_aim) = each row's model projectile tokens, decoded with the model's own card vocabulary.
    ``lethal`` (lethal_rocket) = per row (raw crown towers, my side, a card pending) for ``lethal_rocket_choice``."""
    tau = gate_taus(options, tau, t_sec, len(allowed))
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
                or options.xbow_dead_lane != 'allow') and card_names is None:
            raise ValueError('Rocket aim / X-Bow class / Log aim / X-Bow dead lane require explicit public card identities')
        barrels = None
        if options.log_aim != 'argmax':
            if projectiles is None:
                raise ValueError('log_barrel requires the model projectile tokens of every row')
            barrel_id = getattr(model, 'gid', {}).get(BARREL_KEY)
            barrels = [barrel_landings(projectiles[r], barrel_id) for r in ids]
        cells[ids] = choose_cells(logits, names, options, rngs=[rngs[r] for r in ids], grid=grid, barrels=barrels,
                                  enemy_alive=None if enemy_alive is None else [enemy_alive[r] for r in ids]
                                  ).cpu().numpy()
        # xbow_dead_lane left an X-Bow no cell (-1): it is not chosen; the next card by the model's own ranking is
        # (choose_slot without it), else WAIT. Never reached with unmasked SIM logits (the block never covers the board).
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
    tau = np.broadcast_to(tau, len(slots))
    out = [dict(play=bool(playing[r]), slot=slots[r], cell=int(cells[r]),
                why=('no_affordable' if slots[r] < 0 else 'wait' if not playing[r]
                     else 'stall' if stalled[r] and p[r] <= tau[r] else 'gate' if p[r] > tau[r] else 'hazard'))
           for r in range(len(slots))]
    if options.lethal_rocket != 'off':
        if lethal is None or t_sec is None or grid is None or card_names is None:
            raise ValueError('lethal_rocket requires per-row crown towers, decision times, the grid and card names')
        for r in range(len(out)):
            towers, side, pending = lethal[r]
            hit = lethal_rocket_choice(options, t_sec[r], card_names[r], allowed[r], towers, side, grid, pending=pending)
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
    if options.tau_phase is not None or options.xbow_class != 'argmax' or options.xbow_dead_lane != 'allow':
        boards = [m._cur[1] for m in matches]    # the prepared decision's engine BoardState (my frame)
        out.update(t_sec=[float(b.t_sec) for b in boards], grid=cfg['grid'],
                   enemy_alive=[tuple(bool(t.alive) for t in b.towers[3:6]) for b in boards])
    if options.lethal_rocket != 'off':  # the model board's time (as tau_phase); tower HP from the decision tick's raw state
        out.update(t_sec=[float(m._cur[1].t_sec) for m in matches], grid=cfg['grid'],
                   lethal=[(((m.state or {}).get('episode') or {}).get('crown_towers', []), int(m.side),
                            getattr(m, 'pending', None) is not None) for m in matches])
    if options.log_aim != 'argmax':     # the very projectile tokens the model saw (gen_row, fv >= 4), as live's batch
        rows = [getattr(m, '_gen_row', None) for m in matches]
        if any(r is None or 'projectiles' not in r for r in rows):
            raise ValueError('log_barrel requires generalist rows with public projectile tokens (feature_version >= 4)')
        out.update(grid=cfg['grid'], projectiles=[r['projectiles'] for r in rows])
    return out
