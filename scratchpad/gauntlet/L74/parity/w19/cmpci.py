"""Arm vs base on J1 strict fights (diag_night/r5c/cmp.py's keys) with CIs: each run's overall raw aK [match-bootstrap 95% CI],
the PAIRED difference on the fights strict in both runs [match-bootstrap 95% CI], fights up / down, per-card before -> after
(cards that move or are named), and the cards that lose.
  python cmpci.py BASE_DIR ARM_DIR [card ...]       (each DIR holds matches/*.json; STAMPED=0 for the full cohort)"""
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

ST = os.environ.get('STAMPED', '1') == '1'
FORM = ('', ' evo', ' hero')


def load(d):
    out = {}
    for p in sorted((Path(d) / 'matches').glob('*.json')):
        m = json.loads(p.read_text(encoding='utf-8'))
        if m['summary'].get('skipped') or (ST and not m['summary'].get('phase3b_births')):
            continue
        for r in m.get('fights', []):
            if 'error' in r or not F.is_clean(r, 'strict'):
                continue
            s = F.card_scores(r)
            if s is None:
                continue
            a = r['anchor']
            out[(m['summary']['match'][10:], r['t0'], a['tick'], ('own ' if r['own'] else 'opp ') + a['name'] + FORM[a['form']])] = s['aK']
    return out


def boot(keys, f, B=2000, seed=0):
    by = defaultdict(list)
    for k in keys:
        by[k[0]].append(k)
    ms, rng, v = sorted(by), random.Random(seed), []
    for _ in range(B):
        ks = [k for m in rng.choices(ms, k=len(ms)) for k in by[m]]
        v.append(f(ks))
    v.sort()
    return v[int(.025 * B)], v[int(.975 * B) - 1]


def main():
    A, Bm = load(sys.argv[1]), load(sys.argv[2])
    named = set(sys.argv[3:])
    mA = sum(A.values()) / len(A); mB = sum(Bm.values()) / len(Bm)
    ciA = boot(list(A), lambda ks: sum(A[k] for k in ks) / len(ks))
    ciB = boot(list(Bm), lambda ks: sum(Bm[k] for k in ks) / len(ks))
    both = [k for k in A if k in Bm]
    d = sum(Bm[k] - A[k] for k in both) / len(both)
    ciD = boot(both, lambda ks: sum(Bm[k] - A[k] for k in ks) / len(ks))
    up = sum(Bm[k] > A[k] + 1e-9 for k in both); down = sum(Bm[k] < A[k] - 1e-9 for k in both)
    print(f'BASE  {len(A)} fights {len({k[0] for k in A})} matches: {mA:.4f} [{ciA[0]:.4f}, {ciA[1]:.4f}]')
    print(f'ARM   {len(Bm)} fights {len({k[0] for k in Bm})} matches: {mB:.4f} [{ciB[0]:.4f}, {ciB[1]:.4f}]')
    print(f'PAIRED on {len(both)} common fights: {d:+.5f} [{ciD[0]:+.5f}, {ciD[1]:+.5f}]; up {up} / down {down}; '
          f'only base {len(A) - len(both)}, only arm {len(Bm) - len(both)}')
    cards = defaultdict(lambda: [[], []])
    for k, v in A.items():
        cards[k[3]][0].append(v)
    for k, v in Bm.items():
        cards[k[3]][1].append(v)
    print('card | n base -> arm | raw base -> arm')
    for c, (a, b) in sorted(cards.items(), key=lambda kv: -len(kv[1][0])):
        ma = sum(a) / len(a) if a else float('nan'); mb = sum(b) / len(b) if b else float('nan')
        if c in named or abs(ma - mb) > 1e-9 or len(a) != len(b):
            print(f'{c} | {len(a)} -> {len(b)} | {ma:.4f} -> {mb:.4f}')
    print('moved fights (base aK -> arm aK):')
    for k in sorted(both, key=lambda k: (k[3], k[0], k[1])):
        if abs(Bm[k] - A[k]) > 1e-9:
            print(f'  {k[0]}@{k[1]} {k[3]}: {A[k]:.3f} -> {Bm[k]:.3f}')


if __name__ == '__main__':
    main()
