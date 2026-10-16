"""Bait eval summary: win rate, paired deltas (95% CI), per-archetype split, learner ability use.
    python bait_summary.py OUT.txt NAME=DIR[,DIR] NAME=DIR[,DIR] ...      (DIR = a bait_eval.py --out; rows DIR/D3/matches.jsonl)
The first NAME is the trained model; each later one is a baseline it is paired against (and the 2nd vs the 3rd)."""
import json
import sys
from collections import defaultdict
from pathlib import Path

L74 = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(L74/'heroiw'), str(L74/'weekend')]
from validate import paired_drift  # noqa: E402
import archetypes as A  # noqa: E402

ABILITY_COST = {'Valkyrie': 3}   # Hero Valkyrie ability mana_cost 3 (RoyaleSim cards.json hero_forms ValkyrieHero_Ability)


def load(spec):
    return [json.loads(s) for d in spec.split(',') for s in (Path(d)/'D3'/'matches.jsonl').read_text().splitlines() if s.strip()]


def mine(r, key):
    return (r.get(key) or {}).get(str(r['learner_side'])) or {}


def describe(name, rs):
    n = len(rs)
    w = sum(r['outcome'] == 'win' for r in rs)
    presses = defaultdict(int)
    deploys = defaultdict(int)
    for r in rs:
        for c, k in mine(r, 'ability_presses').items():
            presses[c] += k
        for c, k in mine(r, 'ability_deployments').items():
            deploys[c] += k
    elixir = sum(ABILITY_COST.get(c, 0) * k for c, k in presses.items())
    fb = sum(any(int(f[0]) == r['learner_side'] for f in r.get('form_fallbacks') or []) for r in rs)
    out = [f"{name}: win {100 * w / n:.2f}% ({w}/{n}); plays/game {sum(r['plays_accepted'] for r in rs) / n:.1f}; "
           f"learner form fallbacks in {fb} games",
           f"  ability presses/match {dict((c, round(k / n, 3)) for c, k in presses.items())}; hero deploys/match "
           f"{dict((c, round(k / n, 3)) for c, k in deploys.items())}; presses/deploy "
           f"{dict((c, round(presses[c] / k, 3)) for c, k in deploys.items() if k)}; ability elixir/match {elixir / n:.2f}"]
    by = defaultdict(lambda: [0, 0])
    for r in rs:
        x = by[A.classify(r['opp_deck'])]
        x[0] += 1
        x[1] += r['outcome'] == 'win'
    out.append('  by archetype: ' + ', '.join(f'{a} {w_}/{c} ({100 * w_ / c:.0f}%)' for a, (c, w_) in
                                             sorted(by.items(), key=lambda t: -t[1][0])))
    return out, by


def main():
    dst, specs = sys.argv[1], [a.split('=', 1) for a in sys.argv[2:]]
    rows = {name: load(d) for name, d in specs}
    names = [n for n, _ in specs]
    lines = ['Bait eval: learner = friend deck (Hero Valkyrie, Evo Skeleton Army, Evo Goblin Barrel, Princess, Dart Goblin, '
             'Wall Breakers, Ice Spirit, Cannon); greedy tau .35 + own_effects (bait live stack); E4 T .1, CAL evo + lad; '
             'hero abilities v2 both sides. Draws count as non-wins.']
    arch = {}
    for n in names:
        txt, arch[n] = describe(n, rows[n])
        lines += txt
    pairs = [(b, names[0]) for b in names[1:]] + ([(names[2], names[1])] if len(names) > 2 else [])
    for old, new in pairs:
        d = paired_drift(rows[old], rows[new], expected=len(rows[new]))
        lines.append(f"{new} - {old}: {d['delta_pp']:+.2f} pp [{d['ci95_pp'][0]:+.2f}, {d['ci95_pp'][1]:+.2f}] ({d['pairs']} pairs)")
    lines.append('per-archetype win % (n): ' + '; '.join(
        f"{a} n {arch[names[0]][a][0]}: " + ' / '.join(f"{n} {100 * arch[n][a][1] / arch[n][a][0]:.0f}" for n in names)
        for a in sorted(arch[names[0]], key=lambda a: -arch[names[0]][a][0])))
    Path(dst).write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
