"""ENG-FIX2 (SME_SPELL_KING premise): every projectile spell shot of the ext logs, first two sightings -> per-tick speed v
and k = |P1 - K| / v from the nearest king centre K; prints match, serial, card, side, first, prev frame, src, k, the
off-line residual of P1 from the line K -> aim, and the would-be run tick first - round(k).
    python -I spellk_census.py LIST... (LIST: .jsonl with "match" or .tsv first column) > OUT.tsv"""
import json, math, os, sys
from bisect import bisect_left
from pathlib import Path
ROOT = Path(__file__).resolve().parents[7]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import fights  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
cat = load_catalog()[0]
KINGS = ((9000, 3000), (9000, 29000))
print('match\tserial\tcard\tside\tfirst\tprev\tsecond\tsrc\tk\toffline\trule_run\tdefault_tick')
for f in sys.argv[1:]:
    ms = [json.loads(l)['match'] for l in open(f)] if f.endswith('.jsonl') else \
        [l.split('\t')[0] for l in open(f) if l.strip() and not l.startswith('#')]
    for mm in ms:
        m = fights.read_match(str(LIVE / (mm + '.jsonl')))[0]
        if not m or not m.get('ext'):
            continue
        ticks = [t for t, _ in m['frames']]
        sight = {}
        for t in sorted(m['proj']):
            for p in m['proj'][t]:
                if (cat.get(p[3]) or {}).get('type') == 'spell':
                    sight.setdefault(p[6], []).append((t, p))
        for ser, ss in sight.items():
            if len(ss) < 2:
                continue
            (t1, p), (t2, q) = ss[0], ss[1]
            v = math.hypot(q[1] - p[1], q[2] - p[2]) / (t2 - t1)
            if v <= 0:
                continue
            K = min(KINGS, key=lambda K: math.hypot(p[1] - K[0], p[2] - K[1]))
            k = math.hypot(p[1] - K[0], p[2] - K[1]) / v
            ax, ay = p[4] - K[0], p[5] - K[1]
            L = math.hypot(ax, ay) or 1
            off = abs(ax * (p[2] - K[1]) - ay * (p[1] - K[0])) / L
            prev = ticks[max(0, bisect_left(ticks, t1) - 1)]
            prev = prev if prev < t1 else t1 - 2
            print('\t'.join(map(str, (mm[10:], ser, cat[p[3]]['display_name'], p[0], t1, prev, t2, p[7], round(k, 3),
                                      round(off), t1 - round(k), (prev + 1 + t1) // 2 - 1))))
