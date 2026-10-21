"""Bait punish cost, SIM vs live: own-tower damage in recorded live fights anchored on an opponent Goblin Barrel (base / evo),
Skeleton Barrel or Dart Goblin play vs the SIM replay of the same fight (fights.py / replay_metrics.py per-fight output:
fight['towers'][T]['live' / 'sim'], 12 s window from the setup, the anchor = the opponent's play).

Reads existing fight-output dirs only (no SIM run here):
  python bait_parity.py RUN_DIR [RUN_DIR ...]      (RUN_DIR holds matches/*.json)

Per card: fights where the anchor's side lost own-tower hp live OR in the SIM (= the bait reached a tower in either world);
sum(live), sum(sim), ratio sim/live with a match-cluster bootstrap 95% CI; per-fight median live / sim; the same on the
J1-clean subset (no CLEAN_BLOCKERS flag). Own = the replayed match's own side (summary.side); the bait is the opponent's.
The tower damage is the whole fight window's (other units in the push count too); the anchor is the bait play.
"""
from __future__ import annotations

from collections import defaultdict
import glob
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
BAIT = {'GoblinBarrel': 'Goblin Barrel', 'SkeletonBalloon': 'Skeleton Barrel', 'BlowdartGoblin': 'Dart Goblin'}
try:
    from scratchpad.gauntlet.L74.parity.fights import CLEAN_BLOCKERS
except Exception:                                        # noqa: BLE001 -- fights.py needs its heavy imports; the tuple is stable
    CLEAN_BLOCKERS = ('opp_spell_seen', 'opp_ability_unobserved', 'setup_child_skipped', 'setup_form_not_set',
                      'setup_was_deploying', 'spell_in_flight_at_start', 'ability_active_at_start', 'setup_unmapped_body',
                      'setup_spawn_refused', 'event_card_missing', 'spell_spawned_units_timing_unknown', 'card_not_in_sim',
                      'play_refused', 'sim_game_over', 'setup_mid_jump')


def rows(run):
    out = []
    for f in sorted(glob.glob(str(Path(run) / 'matches' / '*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        side = (d.get('summary') or {}).get('side')
        for x in d.get('fights') or []:
            a = x.get('anchor') or {}
            if a.get('name') not in BAIT or a.get('side') == side or side is None:
                continue
            own = [v for k, v in (x.get('towers') or {}).items() if k.startswith(f'T{side}')]
            live, sim = sum(v['live'] for v in own), sum(v['sim'] for v in own)
            if live <= 0 and sim <= 0:
                continue
            out.append(dict(match=Path(f).stem, card=a['name'] + ('_evo' if a.get('form') == 1 else ''), live=live, sim=sim,
                            clean=not any(k in CLEAN_BLOCKERS for k in (x.get('flags') or {})),
                            stamp=(x.get('stamp') or {}).get('path')))
    return out


def ratio_ci(rs, B=2000, seed=0):
    by = defaultdict(list)
    for r in rs:
        by[r['match']].append(r)
    ms = list(by.values())
    rng = random.Random(seed)
    v = []
    for _ in range(B):
        s = [r for m in (rng.choice(ms) for _ in ms) for r in m]
        li = sum(r['live'] for r in s)
        v.append(sum(r['sim'] for r in s) / li if li else float('nan'))
    v.sort()
    return v[int(.025 * B)], v[int(.975 * B) - 1]


def table(rs, label):
    lines = [f'### {label}', '', '| card | fights | matches | live hp (sum) | SIM hp (sum) | SIM / live [95% CI, by match] | median live / SIM | SIM within 10% of live, per fight |',
             '|---|---|---|---|---|---|---|---|']
    groups = defaultdict(list)
    for r in rs:
        groups[r['card']].append(r)
    groups['ALL three'] = rs
    for c, g in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        if not g:
            continue
        li, si = sum(r['live'] for r in g), sum(r['sim'] for r in g)
        lo, hi = ratio_ci(g)
        ml = sorted(r['live'] for r in g)[len(g) // 2]; ms = sorted(r['sim'] for r in g)[len(g) // 2]
        w10 = sum(abs(r['sim'] - r['live']) <= max(100, .1 * r['live']) for r in g) / len(g)
        lines.append(f'| {c} | {len(g)} | {len({r["match"] for r in g})} | {li:,} | {si:,} | {si/li:.3f} [{lo:.3f}, {hi:.3f}] | {ml} / {ms} | {w10:.2f} |')
    return lines


def main(argv):
    for run in argv:
        rs = rows(run)
        stamps = sorted({r['stamp'] for r in rs if r['stamp']})
        print(f'## {run}  (engine: {", ".join(stamps) or "?"})\n')
        print('\n'.join(table(rs, 'all fights') + [''] + table([r for r in rs if r['clean']], 'J1-clean fights')))
        print()


if __name__ == '__main__':
    main(sys.argv[1:])
