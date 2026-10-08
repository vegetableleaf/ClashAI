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

    @property
    def active(self):
        return (self.card_choice != 'argmax' or self.spell_aim != 'argmax' or self.tau_phase is not None
                or self.xbow_class != 'argmax' or self.log_aim != 'argmax')


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
    ``barrels`` (log_aim): per row, the enemy Goblin Barrel landing points from ``barrel_landings``."""
    result = logits.argmax(dim=-1)
    if options.xbow_class == 'class_sample':
        if len(card_names) != len(logits):
            raise ValueError('one card identity required per cell-logit row')
        for i, name in enumerate(card_names):
            if not is_xbow(name):
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


@torch.no_grad()
def decide_batch(model, enc, heads, p, allowed, stalled, *, tau, device, options, rngs, card_names,
                 t_sec=None, enemy_alive=None, grid=None, projectiles=None):
    """Optional branch of e1_eval's live decision; default branch remains untouched.
    ``t_sec`` (tau_phase) and ``enemy_alive`` [(K, L, R) alive] + ``grid`` (xbow_class) are per-row match context;
    ``projectiles`` (log_aim) = each row's model projectile tokens, decoded with the model's own card vocabulary."""
    tau = gate_taus(options, tau, t_sec, len(allowed))
    playing = allowed.any(axis=1) & ((np.asarray(p) > tau) | stalled)
    slots = [choose_slot(heads['card'][r], allowed[r], options, rngs[r], playing=bool(playing[r]))
             for r in range(len(allowed))]
    cells = np.full(len(slots), -1, dtype=np.int64)
    ids = np.flatnonzero(playing)
    if len(ids):
        index = torch.as_tensor(ids, device=device)
        sub_enc = {k: v[index] for k, v in enc.items()}
        slot_tensor = torch.tensor([slots[r] for r in ids], device=device)
        logits = model.cell_logits(sub_enc, slot_tensor)
        names = [card_names[r][slots[r]] for r in ids] if card_names is not None else [''] * len(ids)
        if (options.spell_aim != 'argmax' or options.xbow_class != 'argmax' or options.log_aim != 'argmax')                 and card_names is None:
            raise ValueError('Rocket aim / X-Bow class / Log aim require explicit public card identities')
        barrels = None
        if options.log_aim != 'argmax':
            if projectiles is None:
                raise ValueError('log_barrel requires the model projectile tokens of every row')
            barrel_id = getattr(model, 'gid', {}).get(BARREL_KEY)
            barrels = [barrel_landings(projectiles[r], barrel_id) for r in ids]
        cells[ids] = choose_cells(logits, names, options, rngs=[rngs[r] for r in ids], grid=grid, barrels=barrels,
                                  enemy_alive=None if enemy_alive is None else [enemy_alive[r] for r in ids]
                                  ).cpu().numpy()
    tau = np.broadcast_to(tau, len(slots))
    return [dict(play=bool(playing[r]), slot=slots[r], cell=int(cells[r]),
                 why=('no_affordable' if slots[r] < 0 else 'wait' if not playing[r]
                      else 'stall' if p[r] <= tau[r] else 'gate')) for r in range(len(slots))]


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
    if options.tau_phase is not None or options.xbow_class != 'argmax':
        boards = [m._cur[1] for m in matches]    # the prepared decision's engine BoardState (my frame)
        out.update(t_sec=[float(b.t_sec) for b in boards], grid=cfg['grid'],
                   enemy_alive=[tuple(bool(t.alive) for t in b.towers[3:6]) for b in boards])
    if options.log_aim != 'argmax':     # the very projectile tokens the model saw (gen_row, fv >= 4), as live's batch
        rows = [getattr(m, '_gen_row', None) for m in matches]
        if any(r is None or 'projectiles' not in r for r in rows):
            raise ValueError('log_barrel requires generalist rows with public projectile tokens (feature_version >= 4)')
        out.update(grid=cfg['grid'], projectiles=[r['projectiles'] for r in rows])
    return out
