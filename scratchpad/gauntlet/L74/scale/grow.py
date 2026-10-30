"""GROW-10M (PLAN Pillar 4a step 3): function-preserving expansion of a GenModel policy checkpoint (CLXIII, B0 = CLXIII +
memory v2) into a wider and deeper GenModel whose outputs equal the original's, so RL starts from it with no re-base.

    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/scale/grow.py IN.pt OUT.pt --d 256 --layers 8
        [--place interleave|end] [--noise 0.01] [--seed 0]
    ... grow.py IN.pt --count               (exact param count table, no checkpoint written)

The output is a PLAIN GenModel checkpoint (args d / layers changed, 4 heads, ffn 4 d, every add-on rebuilt by content), so
model_gen.load_model, eval_gen.load_model, rl_royale (learner + actors) and live_gen load it with no code change.

Widening d -> D = k d (k integer): every d-space vector is carried as k exact copies.
  * residual stream / LN outputs / patch, unit, global tokens / cell_emb / query q: BLOCK copies [x, x, ..., x];
  * attention q / k / v: copies INSIDE each of the 4 heads (head h = k copies of the old head h's 32 dims), q scaled by
    1 / sqrt(k) so q'.k' / sqrt(32 k) = q.k / sqrt(32);
  * LayerNorm over D of [x, ..., x] has the mean and the (population) variance of x: LN is exact with gamma / beta copied,
    no LN change and no new LN statistics (why D must be a multiple of d);
  * a linear that READS a copied space gets W / k per copy + antisymmetric noise (copies' noise sums to 0 for each
    weight), so W'x' = Wx at init but the copies get different gradients (RL runs the model in eval(), no dropout to
    break the symmetry); a linear that WRITES one gets its rows copied;
  * dot products divided by sqrt(D) (cell head kp / kc, CellRefine.residual) get their key side scaled by 1 / sqrt(k).
Deepening: the old layers keep their order; each new TransformerEncoderLayer is a fresh init with out_proj and linear2
(weights AND biases) zero, i.e. x + 0 + 0 = x exactly; ``interleave`` puts them between the old layers, ``end`` after.
Every float tensor of the state dict must match one rule below (an unknown module raises, never passes silently).
Top level: args d / layers / n_params, ``grow`` provenance; rl["ability_head"] widened the same way (rl["ability"]["d_g"]
= D); rl optimizer / ability_optimizer / kl_ref (shape-bound 128-wide state) are dropped (a fresh run never reads them).
"""
from __future__ import annotations

import argparse
import hashlib
import math
import re
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
HEADS = 4                      # GenModel's constructor default; no loader passes another value

# key regex -> (kind, out spec, in spec, out scale). Specs are lists of (space, size) with size in units of the OLD d:
# 'B' = block-copied d-space (size in multiples of d via 'd' / 'ffn'), 'H' = head-copied, '-' = unchanged (an int size).
# kinds: lin (weight [out, in] + its bias), col (param [n, d]: dim 1), row (dim 0: LN vectors, depthwise conv).
D_ = 'd'
RULES = [
    (r'^(patch_pos|cell_emb|cls_emb\.weight|type_emb\.weight)$', 'col', [('B', D_)], None, 1),
    (r'^(cell_bias|cell_patch|patch_xy|unit_in\.form\.weight|past_slot\.weight|card_id\.weight|form_id\.weight|'
     r'card_b\.weight|wait_b\.weight)$', 'copy', None, None, 1),
    (r'^(projectile_in|effect_in|ability_in)\.', 'copy', None, None, 1),
    (r'^(unit_in\.base|unit_in\.project|patch_in|global_in\.0|projectile_target_in\.0|cue_in|tgt_in|tower_refine\.unit\.0)\.',
     'lin', [('B', D_)], '-', 1),
    (r'^(global_in\.2|query\.2|projectile_target_in\.2|tgt_out|tgt_back|tower_refine\.unit\.2)\.', 'lin', [('B', D_)],
     [('B', D_)], 1),
    (r'^projectile_target_spread\.weight$', 'row', [('B', D_)], None, 1),
    (r'^encoder\.layers\.\d+\.self_attn\.in_proj_', 'lin', [('H', D_), ('H', D_), ('H', D_)], [('B', D_)], 'q'),
    (r'^encoder\.layers\.\d+\.self_attn\.out_proj\.', 'lin', [('B', D_)], [('H', D_)], 1),
    (r'^encoder\.layers\.\d+\.linear1\.', 'lin', [('B', 'ffn')], [('B', D_)], 1),
    (r'^encoder\.layers\.\d+\.linear2\.', 'lin', [('B', D_)], [('B', 'ffn')], 1),
    (r'^(encoder\.layers\.\d+\.norm[12]|norm)\.(weight|bias)$', 'row', [('B', D_)], None, 1),
    (r'^(gate_head|value_head|card_q|wait_q|timing_head|ability_head|cell_refine\.inp|tower_refine\.cell\.inp)\.', 'lin',
     '-', [('B', D_)], 1),
    (r'^query\.0\.', 'lin', [('B', D_)], [('B', D_), ('-', 'd_c')], 1),
    (r'^cell_key\.', 'lin', [('B', D_)], [('B', D_)], 'isk'),
    (r'^(cell_refine|tower_refine\.cell)\.out\.', 'lin', [('B', D_)], '-', 'isk'),
    (r'^(cell_refine|tower_refine\.cell)\.(convs\.|cfg$|coords$)', 'copy', None, None, 1),
    (r'^tower_refine\.(xy|cfg)$', 'copy', None, None, 1),
    (r'^tower_refine\.card\.0\.', 'lin', '-', [('B', D_), ('-', 37)], 1),
    (r'^tower_refine\.card\.2\.', 'copy', None, None, 1),
    (r'^(mem|deck_enc|ctx_\w+)\.', 'copy', None, None, 1),
    (r'^mem_aux\.(own|opp)\.0\.', 'lin', '-', [('-', 'z'), ('B', D_), ('-', 'rest')], 1),
    (r'^mem_aux\.glob\.0\.', 'lin', '-', [('-', 'z'), ('B', D_)], 1),
    (r'^mem_aux\.(own|opp|glob)\.2\.', 'copy', None, None, 1),
    (r'^mem_aux\.cfg$', 'copy', None, None, 1),
]


def seg_map(spec, sizes: dict, n_old: int, k: int):
    """spec -> (src [N] old index of each new index, cp [N] copy index (-1 = not copied)). '-' alone = unchanged."""
    if spec == '-':
        return torch.arange(n_old), torch.full((n_old,), -1)
    src, cp, o = [], [], 0
    for space, size in spec:
        n = n_old - o if size == 'rest' else sizes[size] if isinstance(size, str) else size
        if space == '-':
            src.append(torch.arange(o, o + n)); cp.append(torch.full((n,), -1))
        elif space == 'B':
            src.append(torch.arange(o, o + n).repeat(k)); cp.append(torch.arange(k).repeat_interleave(n))
        else:                                                    # 'H': head h -> [copy 0 of h, copy 1 of h, ...]
            hd = n // HEADS
            i = torch.arange(hd)
            for h in range(HEADS):
                src.append((o + h * hd + i).repeat(k)); cp.append(torch.arange(k).repeat_interleave(hd))
        o += n
    assert o == n_old, (spec, o, n_old)
    return torch.cat(src), torch.cat(cp)


def expand_linear(w, b, out_spec, in_spec, scale, sizes, k, noise, gen):
    so, _ = seg_map(out_spec, sizes, w.shape[0], k)
    si, ci = seg_map(in_spec, sizes, w.shape[1], k)
    s = torch.ones(len(so), dtype=w.dtype)
    if scale == 'isk':
        s[:] = 1 / math.sqrt(k)
    elif scale == 'q':                                           # in_proj: the q third of the rows
        s[:len(so) // 3] = 1 / math.sqrt(k)
    exp = ci >= 0
    w2 = w[so][:, si] * s[:, None]
    w2[:, exp] /= k
    if noise > 0 and exp.any():
        r = torch.randn(len(so), w.shape[1], k, generator=gen, dtype=torch.float64)
        r = (r - r.mean(-1, keepdim=True)) * (noise * float(w.std()))
        w2[:, exp] += r[:, si[exp], ci[exp]].to(w.dtype) * s[:, None]
    return w2, (None if b is None else b[so] * s)


def rule_of(key):
    hits = [r for r in RULES if re.search(r[0], key)]
    if len(hits) != 1:
        raise ValueError(f'grow: {key} matches {len(hits)} rules (need exactly 1)')
    return hits[0]


def expand_sd(sd, d, k, sizes, noise, gen, prefix=''):
    """Old state dict -> the widened one (same keys). sizes: the named segment widths."""
    out, done = {}, set()
    for key, v in sd.items():
        if key in done:
            continue
        _, kind, ospec, ispec, scale = rule_of(prefix + key)
        if kind == 'copy' or not v.is_floating_point():
            out[key] = v.clone()
        elif kind == 'col':
            out[key] = v[:, seg_map(ospec, sizes, v.shape[1], k)[0]].clone()
        elif kind == 'row':
            out[key] = v[seg_map(ospec, sizes, v.shape[0], k)[0]].clone()
        else:                                                    # lin: the weight and its bias together
            base = key.rsplit('weight', 1)[0] if 'weight' in key.rsplit('.', 1)[-1] else key.rsplit('bias', 1)[0]
            wk, bk = base + 'weight', base + 'bias'
            w2, b2 = expand_linear(sd[wk], sd.get(bk), ospec, ispec, scale, sizes, k, noise, gen)
            out[wk] = w2
            done.add(wk)
            if bk in sd:
                out[bk] = b2
                done.add(bk)
    return out


def layer_positions(l0, l1, place):
    if place == 'end':
        return list(range(l0))
    return [round(i * l1 / l0) for i in range(l0)]               # old layer i -> new index (interleave)


def grow(st: dict, d1: int, l1: int, place: str = 'interleave', noise: float = 0.01, seed: int = 0, src: str = '') -> dict:
    from pipeline.model_gen import GenModel
    a = st['args']
    d0, l0 = int(a['d']), int(a['layers'])
    if d1 % d0 or l1 < l0:
        raise ValueError(f'grow: d {d1} must be a multiple of {d0} (exact LayerNorm) and layers {l1} >= {l0}')
    if st.get('architecture') or st.get('opp'):
        raise ValueError('grow: only plain GenModel checkpoints (no architecture / opp options) are supported')
    k = d1 // d0
    sd = st['model']
    sizes = {'d': d0, 'ffn': 4 * d0, 'd_c': int(st['d_c'])}
    if 'mem_aux.cfg' in sd:
        sizes['z'] = int(sd['mem_aux.cfg'][0])
    gen = torch.Generator().manual_seed(seed)
    wide = expand_sd(sd, d0, k, sizes, noise, gen)
    if 'mem_aux.cfg' in wide:
        wide['mem_aux.cfg'][1] = d1
    pos = layer_positions(l0, l1, place)
    torch.manual_seed(seed)
    fresh = GenModel(d=d1, layers=l1, d_c=int(st['d_c']), n_cards=len(st['card_vocab']),
                     feature_version=int(a.get('feature_version', 1))).state_dict()
    new_sd = {}
    for key, v in wide.items():
        m = re.match(r'encoder\.layers\.(\d+)\.(.*)', key)
        new_sd[f'encoder.layers.{pos[int(m[1])]}.{m[2]}' if m else key] = v
    for j in sorted(set(range(l1)) - set(pos)):
        for key, v in fresh.items():
            if key.startswith(f'encoder.layers.{j}.'):
                zero = re.search(r'\.(self_attn\.out_proj|linear2)\.(weight|bias)$', key)
                new_sd[key] = torch.zeros_like(v) if zero else v.clone()
    model = GenModel(d=d1, layers=l1, d_c=int(st['d_c']), n_cards=len(st['card_vocab']),
                     feature_version=int(a.get('feature_version', 1)))
    model.load_state_dict(new_sd)                                # strict; builds every add-on from the keys' content
    out = {kk: vv for kk, vv in st.items() if kk != 'model'}
    out['model'] = model.state_dict()
    out['args'] = {**a, 'd': d1, 'layers': l1}
    out['n_params'] = sum(p.numel() for p in model.parameters())
    rl = dict(st.get('rl') or {})
    for kk in ('optimizer', 'ability_optimizer', 'kl_ref', 'branch_optimizer'):
        rl.pop(kk, None)
    if any(kk in rl for kk in ('posture_head', 'ctx_head')):
        raise ValueError('grow: rl posture_head / ctx_head widening is not implemented')
    if 'ability_head' in rl:
        nf = int(rl['ability'].get('n_feat'))
        rl['ability_head'] = expand_sd(rl['ability_head'], d0, k, {'d': d0, 'nf': nf}, noise, gen, prefix='rlab.')
        rl['ability'] = {**rl['ability'], 'd_g': d1}
    if st.get('rl') is not None:
        out['rl'] = rl
    out['grow'] = {'base': src, 'base_sha256': st.get('_sha256'), 'd0': d0, 'layers0': l0, 'd': d1, 'layers': l1, 'k': k,
                   'place': place, 'old_layer_positions': pos, 'noise': noise, 'seed': seed,
                   'n_params0': n_params(st),
                   'builder': 'scratchpad/gauntlet/L74/scale/grow.py'}
    out.pop('_sha256', None)
    return out


RULES.append((r'^rlab\.net\.0\.', 'lin', '-', [('-', 'nf'), ('B', D_)], 1))   # rl ability head: cat[feat, g]
RULES.append((r'^rlab\.net\.2\.', 'copy', None, None, 1))


def n_params(st):
    """Parameters of a checkpoint's GenModel (add-ons built by content, as every loader does)."""
    from pipeline.model_gen import GenModel
    a = st['args']
    m = GenModel(d=int(a['d']), layers=int(a['layers']), d_c=int(st['d_c']), n_cards=len(st['card_vocab']),
                 feature_version=int(a.get('feature_version', 1)))
    m.load_state_dict(st['model'])
    return sum(p.numel() for p in m.parameters())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def count(inp):
    """Exact param counts of the grown INP (no checkpoint written)."""
    st = torch.load(inp, map_location='cpu', weights_only=False)
    print(f'| d | layers | params | ({inp}: {n_params(st):,}) |\n|---|---|---|')
    for d in (256, 384):
        for L in (4, 6, 8, 10, 12):
            print(f'| {d} | {L} | {grow(st, d, L, noise=0.0)["n_params"] / 1e6:.2f} M |', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('inp', nargs='?')
    ap.add_argument('out', nargs='?')
    ap.add_argument('--d', type=int, default=256)
    ap.add_argument('--layers', type=int, default=8)
    ap.add_argument('--place', choices=('interleave', 'end'), default='interleave')
    ap.add_argument('--noise', type=float, default=0.01)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--count', action='store_true')
    a = ap.parse_args()
    if a.count:
        return count(a.inp)
    st = torch.load(a.inp, map_location='cpu', weights_only=False)
    st['_sha256'] = sha(a.inp)
    try:
        src = str(Path(a.inp).resolve().relative_to(ROOT)).replace('\\', '/')
    except ValueError:
        src = str(a.inp)
    g = grow(st, a.d, a.layers, a.place, a.noise, a.seed, src)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp')
    torch.save(g, tmp)
    tmp.replace(out)
    print(f'grown {src} ({g["grow"]["n_params0"]:,} params, d {g["grow"]["d0"]} x {g["grow"]["layers0"]}) -> {out} '
          f'({g["n_params"]:,} params, d {a.d} x {a.layers}, {a.place}, noise {a.noise}) sha256 {sha(out)}')


if __name__ == '__main__':
    main()
