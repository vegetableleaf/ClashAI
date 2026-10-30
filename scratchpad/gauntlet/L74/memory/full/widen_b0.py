"""MEM-FULL step 3 measurement: B0's frozen S3-aux encoder widened by model_gen.mem_full(256, snap=True) vs as it is, on
the same match memories (synthetic rich matches, test_match_memory.rich_match + extra plays). Read-only, CPU, small.

    icebow/.venv/Scripts/python.exe -I -X utf8 scratchpad/gauntlet/L74/memory/full/widen_b0.py [B0.pt]

Reports, on the representation the aux heads read (mem.rep, 128 floats; the coupling mem.out is zero in B0, so the policy
is identical by construction): (1) histories <= 128 events: max |rep(wide, e_max 256 + snap inputs) - rep(as is)| -- should
be float noise only (new ev_in columns are zero; padding is masked); (2) histories > 128: how far the longer window moves
rep (the new information, not an error), as the mean / max L2 relative to |rep|.
The laptop's s1c JSONs are CRLF copies, so load_model's memory_v2 meta check refuses B0 here: the state dict is loaded
straight into GenModel (same architecture keys), which is fine for a representation measurement."""
import copy
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path[:0] = [str(REPO), str(REPO / 'pipeline' / 'tests')]
from pipeline import match_memory as M  # noqa: E402
from pipeline import model_gen as MG  # noqa: E402
from pipeline.dataset_gen import checkpoint_gid  # noqa: E402
from test_match_memory import DECK, rich_match  # noqa: E402


def load(path):
    st = torch.load(path, map_location='cpu', weights_only=False)
    a = st['args']
    net = MG.GenModel(d=int(a['d']), layers=int(a['layers']), d_c=int(st['d_c']), n_cards=len(st['card_vocab']),
                      feature_version=int(a.get('feature_version', 1)), **(st.get('opp') or {}))
    net.load_state_dict(st['model'])
    return net.eval(), checkpoint_gid(st['card_vocab'])


def rep(net, f):
    t = {k: torch.from_numpy(np.asarray(v)[None]) for k, v in f.items()}
    with torch.no_grad():
        return net.mem.rep(t['mem_ev'], t['mem_mask'].bool(), net.emb(t['mem_card'], t['mem_form']), t['mem_summary'],
                           net.card_id(t['mem_answer'].long()))[0]


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / 'icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt'
    torch.set_num_threads(2)
    net, gid = load(path)
    wide = copy.deepcopy(net)
    wide.mem_full(256, True)
    deck = [gid.get(M.card_key(c), 0) for c in DECK]
    short, long_rel, n_long = 0.0, [], 0
    rng = np.random.default_rng(0)
    for seed in range(4):
        side, sm, plays = rich_match(900 + seed)
        for _ in range(150):
            plays.append(dict(tick=int(rng.integers(0, 4200)), side=int(rng.integers(2)), card='Knight',
                              x=float(rng.integers(0, 18000)), y=float(rng.integers(0, 32000))))
        a, b = M.build(side, sm, plays), M.build(side, sm, plays, e_max=256, snap=True)
        for t in [s['tick'] for s in sm][::6] + [10 ** 6]:
            fa, fb = a.features(t, gid, deck, 'v2'), b.features(t, gid, deck, 'v2')
            ra, rb = rep(net, fa), rep(wide, fb)
            if int(fb['mem_mask'].sum()) <= 128:
                short = max(short, float((ra - rb).abs().max()))
            else:
                n_long += 1
                long_rel.append(float((ra - rb).norm() / ra.norm().clamp(min=1e-9)))
    print(f'B0 {path.name}: ev_in {net.mem.ev_in.in_features} -> {wide.mem.ev_in.in_features}, '
          f'coupling |mem.out.weight| sum {float(net.mem.out.weight.abs().sum()):.3g}')
    print(f'histories <= 128 events: max |rep diff| = {short:.3g}')
    if long_rel:
        print(f'histories > 128 events ({n_long} rows): rep moves by L2 rel mean {np.mean(long_rel):.3f}, '
              f'max {np.max(long_rel):.3f}')


if __name__ == '__main__':
    main()
