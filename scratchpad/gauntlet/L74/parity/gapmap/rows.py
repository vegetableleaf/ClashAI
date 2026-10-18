"""Per-fight rows of a results dir -> TSV (one line per fight, stamped cohort only by default).
cols: stem t0 card strict aK a0 ceil bmis bn tfail blockers(comma) allflags(comma)
usage: CB=/workspace/cb12 python rows.py RESULTS_DIR > rows.tsv   (ALL=1: every match, not only phase-3b stamped)"""
import json, os, sys
from pathlib import Path
sys.path.insert(0, os.environ.get('CB', '/workspace/cb12'))
from scratchpad.gauntlet.L74.parity import fights as F

ALL = os.environ.get('ALL') == '1'
for p in sorted((Path(sys.argv[1])/'matches').glob('*.json')):
    m = json.loads(p.read_text(encoding='utf-8'))
    if m['summary'].get('skipped') or (not ALL and not m['summary'].get('phase3b_births')):
        continue
    stem = m['summary']['match'][10:]
    for r in m.get('fights', []):
        if 'error' in r:
            continue
        a = r['anchor']
        card = ('own ' if r['own'] else 'opp ') + a['name'] + ('', ' evo', ' hero')[a['form']]
        blk = sorted({k.split(':')[0] for k in r['flags'] if k.startswith(F.CLEAN_BLOCKERS)})
        allf = ','.join(sorted({k.split(':')[0] for k in r['flags']}))
        s = F.card_scores(r)
        strict = int(F.is_clean(r, 'strict'))
        if s is None:
            print('\t'.join(map(str, (stem, r['t0'], card, strict, '', '', '', '', '', '', ','.join(blk)))))
            continue
        c = '' if s['ceil'] is None else f"{s['ceil']:.4f}"
        print('\t'.join(map(str, (stem, r['t0'], card, strict, f"{s['aK']:.4f}", int(s['a0']), c, s['bmis'], s['bn'],
                                  int(s['tfail']), ','.join(blk), allf))))
