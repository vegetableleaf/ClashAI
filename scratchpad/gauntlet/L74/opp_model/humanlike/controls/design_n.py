"""Human controls at the DESIGN size: n_live = 856 (calibration CLXIII), n_model = 1,920 (4 seed blocks)."""
import sys, random, math
from collections import Counter
sys.path.insert(0, 'scratchpad/gauntlet/L74/opp_model/humanlike')
import card as CD
th, sha = CD.SC.load_thresholds()
H, _ = CD.hf_records('scratchpad/gauntlet/L74/opp_model/humanlike/data/hf_ref_bec5811a.json.gz')
HR = CD.rows(H)
feats = [k for k in CD.STATS if k not in ('opp_el', 'pocket_share')]
tags = sorted({r['tag'] for r in H})
by = {}
for x, r in zip(HR, H):
    by.setdefault(r['tag'], []).append(x)
cnt = Counter()
for seed in range(40):          # one side per match, disjoint matches: 856 "live" vs 1,920 "model", B-live rule (TOST 0.20, RMS 0.10)
    rng = random.Random(seed)
    tt = rng.sample(tags, 856 + 1920)
    a = [by[t][rng.randrange(2)] for t in tt[:856]]
    b = [by[t][rng.randrange(2)] for t in tt[856:]]
    r = CD.level_b(a, b, th, feats=feats)
    cnt['rms'] += r['pass_rms']; cnt['tost'] += r['pass_tost']; cnt['b3'] += r['pass_b3']; cnt['all'] += r['passed']
print('B-live rule on HF humans at the design size 856 vs 1,920 (23 stats), 40 draws:', dict(cnt), flush=True)
# siege: bootstrap SE of each fact on the 856 live matches; margin = (1.645 + 1.96) * SE_diff with SE_model = SE_live * sqrt(856 / 1920)
L = CD.live_records('calibration')
ms = CD.siege_facts(L)
rng = random.Random(0)
bs = {k: [] for k in CD.FACT_KEYS}
for _ in range(1000):
    f = CD._facts([ms[rng.randrange(len(ms))] for _ in ms])
    for k in CD.FACT_KEYS:
        bs[k].append(f[k])
for k in CD.FACT_KEYS:
    v = [x for x in bs[k] if x == x]
    mu = sum(v) / len(v)
    se = math.sqrt(sum((x - mu) ** 2 for x in v) / (len(v) - 1))
    sed = se * math.sqrt(1 + 856 / 1920)
    print(f'siege {k}: live {CD._facts(ms)[k]:.3f} bootstrap SE {se:.4f}; SE_diff at design {sed:.4f}; margin for 95% human pass {(1.645 + 1.96) * sed:.3f}')
by_a = {}
for m in ms:
    by_a.setdefault(m[0], []).append(m)
for a, mm in sorted(by_a.items()):
    v = []
    for _ in range(500):
        f = CD._facts([mm[rng.randrange(len(mm))] for _ in mm])['lock_rate']
        if f == f:
            v.append(f)
    mu = sum(v) / len(v)
    se = math.sqrt(sum((x - mu) ** 2 for x in v) / (len(v) - 1))
    print(f'  arch {a}: matches {len(mm)} xbows {sum(len(x[1]) for x in mm)} lock {CD._facts(mm)["lock_rate"]:.3f} SE {se:.3f} margin95 {(1.645 + 1.96) * se * math.sqrt(1 + 856 / 1920):.3f}')
