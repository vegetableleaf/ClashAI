"""Opt-in inference choices. No gate, tower-HP, card-priority or reward rules."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math

import numpy as np
import torch
import torch.nn.functional as F


@dataclass(frozen=True)
class DecisionOptions:
    card_choice: str = 'argmax'
    card_ratio: float = 0.7
    card_T: float = 1.0
    spell_aim: str = 'argmax'

    def __post_init__(self):
        if self.card_choice not in ('argmax', 'filtered'):
            raise ValueError('card_choice must be argmax or filtered')
        if not math.isfinite(self.card_ratio) or not 0 < self.card_ratio <= 1:
            raise ValueError('card_ratio must be in (0, 1]')
        if not math.isfinite(self.card_T) or self.card_T <= 0:
            raise ValueError('card_T must be positive and finite')
        if self.spell_aim not in ('argmax', 'rocket_area'):
            raise ValueError('spell_aim must be argmax or rocket_area')

    @property
    def active(self):
        return self.card_choice != 'argmax' or self.spell_aim != 'argmax'


def options_from_config(cfg=None):
    cfg = cfg or {}
    return DecisionOptions(**{k: cfg[k] for k in DecisionOptions.__dataclass_fields__ if k in cfg})


def add_arguments(parser):
    parser.add_argument('--card-choice', choices=('argmax', 'filtered'), default='argmax')
    parser.add_argument('--card-ratio', type=float, default=0.7)
    parser.add_argument('--card-T', type=float, default=1.0)
    parser.add_argument('--spell-aim', choices=('argmax', 'rocket_area'), default='argmax',
                        help='rocket_area: maximise learned cell probability inside the catalog Rocket radius')
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


def choose_cells(logits, card_names, options):
    """Aim only after card selection. Other cards retain exact argmax behaviour."""
    result = logits.argmax(dim=-1)
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
def decide_batch(model, enc, heads, p, allowed, stalled, *, tau, device, options, rngs, card_names):
    """"""
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
        if options.spell_aim != 'argmax' and card_names is None:
            raise ValueError('Rocket aim requires explicit public card identities')
        cells[ids] = choose_cells(logits, names, options).cpu().numpy()
    return [dict(play=bool(playing[r]), slot=slots[r], cell=int(cells[r]),
                 why=('no_affordable' if slots[r] < 0 else 'wait' if not playing[r]
                      else 'stall' if p[r] <= tau else 'gate')) for r in range(len(slots))]


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
    return dict(decision_options=options, rngs=rngs, card_names=[list(m.deck.cards) for m in matches])
