"""(A) Is opp_cycle populated with the bait card live?  (B) Does the policy's P(Log) react to it?

Rebuilds the deployed live inputs from --log-frames live logs (cues/live/logframes.full_frames + pipeline.live_gen_v2.GenPilot
with the deployed LIVE_OPTIONS, as cues/live/ident.py does), on CLX matches whose opponent played a Goblin Barrel / Skeleton
Barrel / Dart Goblin. CPU, one thread, idle priority.

(A) at the first rebuilt decision after the bait card's first public play: its opp_cycle row (slot, plays_since, age_s).
(B) on decision states with the Log in hand + affordable and an enemy ground body on our half: the model's
P(Log) = sigmoid(gate) x softmax(card logits over the affordable slots)[Log], and P(Log on a low-value target) = P(Log) x
1[the Log's argmax cell rolls over < 1 elixir of enemy bodies with hp <= 429 on the decision frame], under:
  asis      the recorded inputs
  -bait     every CORE bait card removed from opp_cycle (and opp_past)
  +GB / +DG Goblin Barrel / Dart Goblin inserted as the newest opp_cycle row (plays_since 0, age 3 s), cycle only
  +GBp      as +GB, and also the newest opp_past row (at our left princess, dt 3 s)
  +GBold / +DGold  inserted as seen 25 s ago with 4 opponent plays since (the "hold it for the barrel" case)
Paired differences vs asis, bootstrap 95% CI over states (states within a match are correlated: CI also by match).

  python cycle_probe.py [--matches 12] [--every 4]
"""
from __future__ import annotations

import argparse
import copy
import ctypes
import json
from pathlib import Path
import random
import sys

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:                                        # noqa: BLE001
    pass
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path[:0] = [str(REPO), str(HERE), str(REPO / 'scratchpad/gauntlet/L74/cues/live')]
import torch                                             # noqa: E402
torch.set_num_threads(1)
import log_use as L                                      # noqa: E402
from logframes import full_frames                        # noqa: E402
from pipeline import live_gen_v2                         # noqa: E402
from pipeline.e1_eval import allowed_slots               # noqa: E402
from pipeline.model_v3 import cell_xy                    # noqa: E402

CLX = REPO / 'icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt'
PROBE = ('goblin_barrel', 'skeleton_barrel', 'dart_goblin')


def _deployed_options():
    """the live LIVE_OPTIONS file's decision options (pipeline/tests/test_live_options.parse without pytest)."""
    import argparse
    from pipeline.decision_options import add_arguments, config_from_args, options_from_config
    from pipeline.live_options import add_live_options_arguments, parse_with_live_options
    ap = argparse.ArgumentParser()
    add_arguments(ap)
    ap.add_argument('--tau', type=float, default=.35)
    ap.add_argument('--tau-alternate', type=float, nargs=2, default=None)
    add_live_options_arguments(ap, REPO / 'scratchpad/gauntlet/L70/live/LIVE_OPTIONS')
    a, _ = parse_with_live_options(ap, [])
    return options_from_config(config_from_args(a))


def pick(n):
    """newest CLX main-account logs (4858 towers, ext frames) whose opponent publicly played a PROBE card."""
    out = []
    for p in sorted(L.LOGS.glob('live_play_2026*.jsonl'), reverse=True):
        if p.stem < 'live_play_20261019_140000':
            break
        with open(p, 'rb') as f:
            head = f.readline()
        if b'rlarm_stepd_ctrl_nos2' not in head:
            continue
        m = L.parse(p)
        if m is None or m['side'] is None:
            continue
        first = {}
        for q in m['opp']:
            if q['card'] in PROBE:
                first.setdefault(q['card'], q['tick'])
        if first:
            out.append((p, first))
        if len(out) >= n:
            break
    return out


def enemy_ground_on_our_half(f, side):
    for e in f['entities']:
        if e['side'] == side or e['card_id'] == -1 or e['hp'] <= 0:
            continue
        k, _ = L.key_of(e['card_id'])
        tr = L.TRAITS.get(k)
        if tr and not tr['air'] and tr['kind'] == 'troop' and ((e['y'] < 16000) == (side == 0)):
            return True
    return False


def low_value_cell(f, side, xy):
    lx, ly = L.raw_xy(side, xy)
    fwd = 1 if side == 0 else -1
    v = 0.0
    for e in f['entities']:
        if e['side'] == side or e['card_id'] == -1 or not 0 < e['hp'] <= L.LOG_DMG:
            continue
        k, _ = L.key_of(e['card_id'])
        tr = L.TRAITS.get(k)
        if not tr or tr['air']:
            continue
        ahead = (e['y'] - ly) * fwd
        if abs(e['x'] - lx) <= L.HALF + L.PAD and -1100 <= ahead <= L.REACH + L.PAD:
            v += (tr['elixir'] or 1) / L.BODY_COUNT.get(k, 1)
    return v < L.LOW


def variants(b, gid):
    cyc, past = b['opp_cycle'], b['opp_past']
    bait_ids = {gid[k] for k in L.CORE if k in gid}
    pad_c = torch.tensor([0, 3, -1, -1], dtype=cyc.dtype)
    pad_p = torch.tensor([0, 3, -1, -1, -1], dtype=past.dtype)

    def strip(t, pad):
        rows = [r for r in t[0] if int(r[0]) not in bait_ids]
        rows += [pad] * (t.shape[1] - len(rows))
        return torch.stack(rows).unsqueeze(0)

    def insert_c(card, since=0, age=3.0):
        rows = [r for r in cyc[0] if int(r[0]) != gid[card] and int(r[0]) != 0]
        rows = [torch.tensor([gid[card], 0, since, age], dtype=cyc.dtype)] + rows
        rows = (rows + [pad_c] * 8)[:cyc.shape[1]]
        return torch.stack(rows).unsqueeze(0)

    def insert_p(card):
        rows = [torch.tensor([gid[card], 0, 0.194, 0.797, 3.0], dtype=past.dtype)] + list(past[0])
        return torch.stack(rows[:past.shape[1]]).unsqueeze(0)
    out = {'asis': b, '-bait': dict(b, opp_cycle=strip(cyc, pad_c), opp_past=strip(past, pad_p))}
    out['+GB'] = dict(b, opp_cycle=insert_c('goblin_barrel'))
    out['+DG'] = dict(b, opp_cycle=insert_c('dart_goblin'))
    out['+GBp'] = dict(b, opp_cycle=insert_c('goblin_barrel'), opp_past=insert_p('goblin_barrel'))
    # seen long ago (age 25 s, 4 plays since: by the public count the card is likely back in their hand) = the hold case
    out['+GBold'] = dict(b, opp_cycle=insert_c('goblin_barrel', 4, 25.0))
    out['+DGold'] = dict(b, opp_cycle=insert_c('dart_goblin', 4, 25.0))
    return out


@torch.no_grad()
def score(pilot, b, info, f, side):
    allowed = allowed_slots([h[0] > 0 for h in info['hand']], info['costs'], info.get('el_afford', info['el_int']))
    names = [info['names'][d] if d >= 0 else None for d in info['hand_deck_indices']]
    if 'Log' not in names or not allowed[names.index('Log')]:
        return None
    slot = names.index('Log')
    out = pilot.model(b)
    gate = float(torch.sigmoid(out['gate'][0]))
    logits = out['card'][0].masked_fill(~torch.as_tensor(allowed), float('-inf'))
    pc = float(torch.softmax(logits, -1)[slot])
    card, form = info['hand'][slot]
    cell = pilot.model(b, card=torch.tensor([card]), form=torch.tensor([form]))['cell'][0]
    xy = cell_xy(int(cell.argmax()), pilot.grid)
    low = low_value_cell(f, side, xy)
    return dict(p=gate * pc, gate=gate, card=pc, low=gate * pc * low, argmax_log=int(logits.argmax()) == slot)


def boot_ci(groups, B=2000, seed=0):
    """groups: per-match lists of paired diffs -> (mean, state CI, match-cluster CI)."""
    flat = [x for g in groups for x in g]
    rng = random.Random(seed)
    m = sum(flat) / len(flat)
    s = sorted(sum(rng.choice(flat) for _ in flat) / len(flat) for _ in range(B))
    c = []
    for _ in range(B):
        gs = [rng.choice(groups) for _ in groups]
        xs = [x for g in gs for x in g]
        c.append(sum(xs) / len(xs))
    c.sort()
    return m, (s[int(.025 * B)], s[int(.975 * B) - 1]), (c[int(.025 * B)], c[int(.975 * B) - 1])


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--matches', type=int, default=12)
    ap.add_argument('--every', type=int, default=4)
    a = ap.parse_args(argv)
    kw = dict(device='cpu', gate_tau=.35, extrapolate_ticks=24, own_effects=True, hero_ability_spec='supplement',
              decision_options=_deployed_options(), decision_seed=0)
    pilot = live_gen_v2.GenPilot(str(CLX), **kw)
    pilot.legal_guard, pilot.identity_ext, pilot.afford_ticks = True, True, 23
    if getattr(pilot.model, 'cue_in', None) is not None:
        from pipeline.live_unit_state import LiveCues
        pilot.cues = LiveCues()
    gid = {**pilot.gid, **{k.replace('-', '_'): v for k, v in pilot.gid.items()}}
    name_of = {v: k for k, v in pilot.gid.items()}
    print('feature_version', pilot.feature_version, 'cue layer', getattr(pilot.model, 'cue_in', None) is not None, flush=True)
    diffs = {k: {'p': [], 'low': []} for k in ('-bait', '+GB', '+DG', '+GBp', '+GBold', '+DGold')}
    base = {'p': [], 'low': [], 'n': 0}
    for path, first in pick(a.matches):
        pilot.reset_match()
        side = None; checked = set(); md = {k: {'p': [], 'low': []} for k in diffs}
        for i, f in enumerate(full_frames(str(path))):
            pilot.observe(copy.deepcopy(f))
            side = f['my_side']
            if f['game_tick'] < 150 or i % a.every:
                continue
            b, info = pilot.row(copy.deepcopy(f))
            t = f['game_tick']
            for card, t0 in first.items():           # (A)
                if card not in checked and t > t0:
                    checked.add(card)
                    cyc = b['opp_cycle'][0].tolist()
                    row = next(((j, r) for j, r in enumerate(cyc) if int(r[0]) == gid.get(card)), None)
                    print(f'  (A) {path.stem} {card}: first play tick {t0}, decision {t}: ' +
                          (f'opp_cycle slot {row[0]}, plays_since {row[1][2]:.0f}, age {row[1][3]:.1f} s' if row else 'ABSENT')
                          + ' | cycle ' + ', '.join(f'{name_of.get(int(r[0]), "-")}' for r in cyc if r[0] > 0), flush=True)
            if not enemy_ground_on_our_half(f, side):
                continue
            vs = variants(b, gid)
            s0 = score(pilot, vs['asis'], info, f, side)
            if s0 is None:
                continue
            base['p'].append(s0['p']); base['low'].append(s0['low']); base['n'] += 1
            for k in diffs:
                s1 = score(pilot, vs[k], info, f, side)
                md[k]['p'].append(s1['p'] - s0['p']); md[k]['low'].append(s1['low'] - s0['low'])
        for k in diffs:
            for q in ('p', 'low'):
                if md[k][q]:
                    diffs[k][q].append(md[k][q])
        print(f'{path.stem}: states so far {base["n"]}', flush=True)
    print(f'\n(B) {base["n"]} states (Log in hand + affordable, enemy ground troop on our half), '
          f'{len(diffs["+GB"]["p"])} matches; mean P(Log) as-is {L.mean(base["p"]):.4f}, P(low-value Log) {L.mean(base["low"]):.4f}')
    for k, d in diffs.items():
        for q in ('p', 'low'):
            m, sci, cci = boot_ci(d[q])
            print(f'  {k:6s} d{"P(Log)" if q == "p" else "P(low Log)"}: {m:+.4f}  state CI [{sci[0]:+.4f}, {sci[1]:+.4f}]  '
                  f'match CI [{cci[0]:+.4f}, {cci[1]:+.4f}]  relative {m / max(1e-9, L.mean(base[q])):+.1%}')


if __name__ == '__main__':
    main(sys.argv[1:])
