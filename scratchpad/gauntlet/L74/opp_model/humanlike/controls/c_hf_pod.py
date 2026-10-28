import sys, time
sys.path.insert(0, "/workspace/score/cb/scratchpad/gauntlet/L74/opp_model/humanlike")
import card as CD, disc
H, meta = CD.hf_records('/workspace/score/cb/scratchpad/gauntlet/L74/opp_model/humanlike/data/hf_ref_bec5811a.json.gz')
tags = sorted({x['tag'] for x in H})
ta, tb = CD.halves(tags, 0)
ta, tb = set(ta[:5000]), set(tb[:5000])
xa = [x for x in H if x['tag'] in ta and x['side'] == 0]
xb = [x for x in H if x['tag'] in tb and x['side'] == 0]
for name, b in (('HF human halves', xb), ('planted: half B plays 1 s later', [dict(x, plays=[[p[0] + 20] + p[1:] for p in x['plays']]) for x in xb]),
                ('planted: half B positions +0.5 tile deeper', [dict(x, plays=[p[:4] + [p[4] + 0.5] + p[5:] for p in x['plays']]) for x in xb])):
    t = time.time()
    r = disc.train_eval(xa, b, 0)
    print(f'{name} ({len(xa)}/{len(b)}): AUC {r["auc"]:.3f} 90% CI [{r["ci"][0]:.3f}, {r["ci"][1]:.3f}] ({time.time() - t:.0f} s)', flush=True)
