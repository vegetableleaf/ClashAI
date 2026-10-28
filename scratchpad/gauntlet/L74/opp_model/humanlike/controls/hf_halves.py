import sys, time
from collections import Counter
sys.path.insert(0, 'scratchpad/gauntlet/L74/opp_model/humanlike')
import card as CD
th, sha = CD.SC.load_thresholds()
t = time.time()
H, meta = CD.hf_records('scratchpad/gauntlet/L74/opp_model/humanlike/data/hf_ref_bec5811a.json.gz')
H = [r for r in H if r['split'] in (1, 2)]
print('HF test-split sides', len(H), 'arch', Counter(r['arch'] for r in H).most_common(), round(time.time() - t), 's', flush=True)
HR = CD.rows(H)
print('rows', round(time.time() - t), 's', flush=True)
feats = [k for k in CD.STATS26 if k not in ('opp_el', 'pocket_share')]
tags = sorted({r['tag'] for r in H})
for n in (3700,):
    cnt = Counter()
    for seed in range(20):
        ta, tb = CD.halves(tags, seed)
        ta, tb = set(ta[:n]), set(tb[:n])
        xa = [x for x, r in zip(HR, H) if r['tag'] in ta]
        xb = [x for x, r in zip(HR, H) if r['tag'] in tb]
        r = CD.level_b(xa, xb, th, feats=feats, margin=th['B']['b_hf_per_stat_abs_d_max'])
        cnt['rms'] += r['pass_rms']; cnt['tost'] += r['pass_tost']; cnt['b3'] += r['pass_b3']; cnt['all'] += r['passed']
        if seed == 0:
            print(CD.print_b(f'  example n={n}', r))
    print(f'B-HF human halves, {n} matches/half (both sides), 20 splits:', dict(cnt), flush=True)
# per archetype at 2000 matches (both sides) per arch where available
by = Counter(r['arch'] for r in H)
print('per-arch side counts', by)
