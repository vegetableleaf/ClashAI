"""Frozen-base projectile-target branch: add GenModel's fv6 zero-init spatial branch on top of a trained fv5 checkpoint.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/barrel_branch/train_branch.py \
        --base icebow/data/pipeline/gen_v32_s0/gen_s0.pt --data icebow/data/pipeline/gen_dataset_v32_fv5.npz \
        --out-dir scratchpad/gauntlet/L73/barrel_branch/v32 --device cuda

Recipe = Codex's L72 development_iteration_7 (Barrel Logs correct 40 -> 56 of 63, wrong lane 22 -> 6): fv6 model,
every base weight loaded and frozen, base kept in eval(), ONLY projectile_target_in / projectile_target_spread trained
with train_gen.losses (same expert loss, row sampling = per-epoch permutation of train rows, mirror p=0.5), AdamW
lr 1e-3 wd 0.01, clip 1, fp32. Differences from Codex: no exact-bitwise gates (tolerance 1e-5, measured and recorded),
and the train rows are a seeded pool of updates*batch rows (loaded streaming, so the 14 GB npz never sits in RAM).
Checks (a)-(d) run inside; exit code 1 and result.json pass_all=false if any fails.
"""
import argparse
import ctypes
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline.eval_gen import val_rows                                   # noqa: E402
from pipeline.model_gen import GenModel, load_model                      # noqa: E402
from pipeline.projectile_observation import require_complete_training    # noqa: E402
from pipeline.train_expert_context import initialize                     # noqa: E402  (fv5 -> fv6 migration, strict key check)
from pipeline.train_gen import GenRows, losses                           # noqa: E402
from pipeline.train_rocket_curriculum import load_subset                 # noqa: E402

TOL = 1e-5
HEADS = ('gate', 'card', 'wait', 'value', 'cell')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


@torch.no_grad()
def compare(model, ref, rows, pos, bs=256):
    """Max |model - ref| per head over rows ``pos`` (-inf pads must coincide); also rows holding a valid projectile target."""
    diff, mean_cell, flips, targets = {k: 0.0 for k in HEADS}, 0.0, 0, 0
    for lo in range(0, len(pos), bs):
        b = rows.batch(pos[lo:lo + bs])
        o, r = model(b, card=b['card'], form=b['form']), ref(b, card=b['card'], form=b['form'])
        for k in HEADS:
            fin = torch.isfinite(o[k]) & torch.isfinite(r[k])
            assert not (~fin & (o[k] != r[k])).any(), f'{k}: non-finite entries differ'
            diff[k] = max(diff[k], float((o[k] - r[k])[fin].abs().max()))
        mean_cell += float((o['cell'] - r['cell']).abs().mean()) * len(b['gate'])
        flips += int((o['cell'].argmax(-1) != r['cell'].argmax(-1)).sum())
        obj = b['projectiles']
        targets += int(((obj[..., 0] > 0) & (obj[..., 4:6] >= 0).all(-1) & (obj[..., 4:6] <= 1).all(-1)).any(-1).sum())
    n = len(pos)
    return dict(max_abs_diff=diff, rows=n, rows_with_valid_target=targets,
                cell_mean_abs_diff=mean_cell / n, cell_argmax_changed_rows=flips)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', type=Path, required=True, help='fv5 GenModel checkpoint (train_gen format)')
    ap.add_argument('--data', type=Path, required=True, help='fv5 dataset_gen npz')
    ap.add_argument('--out-dir', type=Path, required=True)
    ap.add_argument('--updates', type=int, default=1000)
    ap.add_argument('--batch', type=int, default=128)
    ap.add_argument('--lr', type=float, default=1e-3)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--device', default='cpu')
    ap.add_argument('--val-rows', type=int, default=2000, help='fixed seed-0 sample of val rows for checks (a) and (c)')
    ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # below normal
    except AttributeError:
        pass
    a.out_dir.mkdir(parents=True, exist_ok=True)
    dev = torch.device(a.device)

    # --- data: stream only the rows we use (train pool of updates*batch, val sample), never the whole npz
    with np.load(a.data, allow_pickle=False) as z:
        meta, split = json.loads(str(z['meta'])), z['split']
    require_complete_training(meta, allow_causal_tti_unknowns=True)
    rng = np.random.default_rng(a.seed)
    train = np.flatnonzero(split == 0)
    tr_ids = np.sort(rng.choice(train, min(a.updates * a.batch, len(train)), replace=False))
    va_ids = val_rows({'split': split}, a.val_rows)
    ids = np.sort(np.r_[tr_ids, va_ids])
    t0 = time.time()
    sub, _ = load_subset(a.data, ids)
    rows = GenRows(sub, np.arange(len(ids)), dev)
    tr_pos, va_pos = np.searchsorted(ids, tr_ids), np.searchsorted(ids, va_ids)
    print(json.dumps(dict(loaded_rows=len(ids), train_pool=len(tr_pos), val=len(va_pos), seconds=round(time.time() - t0))), flush=True)
    assert len(tr_pos) >= a.batch

    # --- models: fv6 = base + zero-init branch; ref = the untouched fv5 base
    state = torch.load(a.base, map_location='cpu', weights_only=False)
    assert int(state['args']['feature_version']) == 5, 'base must be an fv5 checkpoint'
    model = initialize(state, 6, meta).to(dev)       # checks vocab / grid / data version; strict except the 5 branch keys
    ref = GenModel(d=int(state['args']['d']), layers=int(state['args']['layers']), d_c=int(state['d_c']),
                   n_cards=len(state['card_vocab']), feature_version=5)
    ref.load_state_dict(state['model'])
    ref = ref.to(dev).eval()
    for n, p in model.named_parameters():
        p.requires_grad_(n.startswith('projectile_target_'))
    params = [p for p in model.parameters() if p.requires_grad]
    assert len(params) == 5, len(params)
    model.eval()
    branch0 = {n: p.detach().clone() for n, p in model.named_parameters() if p.requires_grad}
    grid = str(state['args']['grid'])
    checks = {}

    # (a) zero-init branch == base on a sample batch
    checks['a_zero_init_equals_base'] = ca = compare(model, ref, rows, va_pos[:256])
    ca['ok'] = max(ca['max_abs_diff'].values()) <= TOL
    print(json.dumps(dict(check_a=ca)), flush=True)

    # --- train: only the branch; same loss / row sampling / mirror draw as train_gen
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.01)
    perm, pos, log, t0 = rng.permutation(tr_pos), 0, [], time.time()
    with (a.out_dir / 'train.jsonl').open('w') as f:
        for u in range(1, a.updates + 1):
            if pos + a.batch > len(perm):
                perm, pos = rng.permutation(tr_pos), 0
            b = rows.batch(perm[pos:pos + a.batch])
            pos += a.batch
            loss, parts = losses(model, b, mirror=bool(rng.random() < 0.5), grid=grid)
            assert torch.isfinite(loss), f'nonfinite loss at update {u}'
            opt.zero_grad(set_to_none=True)
            loss.backward()
            for n, p in model.named_parameters():
                if p.requires_grad:
                    assert p.grad is None or torch.isfinite(p.grad).all(), f'nonfinite grad {n}'
                else:
                    assert p.grad is None, f'frozen {n} got a gradient'
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            rec = dict(update=u, loss=float(loss.detach()), parts=parts, seconds=round(time.time() - t0, 1))
            f.write(json.dumps(rec) + '\n')
            if u % max(1, a.updates // 10) == 0 or u == a.updates:
                print(json.dumps(rec), flush=True)

    # --- save in train_gen's checkpoint layout (+ one provenance key), fv6
    ck = {k: v for k, v in state.items() if k not in ('model', 'args', 'optimizer')}
    ck.update(model={k: v.detach().cpu() for k, v in model.state_dict().items()},
              args=dict(state['args'], feature_version=6), n_params=sum(p.numel() for p in model.parameters()),
              projectile_branch=dict(base=str(a.base), base_sha256=sha(a.base), data=str(a.data), updates=a.updates,
                                     batch=a.batch, lr=a.lr, seed=a.seed, note="'val'/'epoch' keys are the base's, not re-measured"))
    out = a.out_dir / f'gen_branch_s{a.seed}.pt'
    torch.save(ck, out)

    # (b) base tensors byte-identical, read back from the saved file
    saved = torch.load(out, map_location='cpu', weights_only=False)['model']
    base_keys = set(state['model'])
    added = set(saved) - base_keys
    bad = [k for k in base_keys if k not in saved or saved[k].dtype != state['model'][k].dtype
           or not torch.equal(saved[k], state['model'][k])]
    checks['b_base_byte_identical'] = dict(base_tensors=len(base_keys), mismatched=bad, added_keys=sorted(added),
                                           ok=not bad and all(k.startswith('projectile_target_') for k in added) and len(added) == 5)

    # (c) gate / card unchanged on validation rows (branch only feeds spatial patches), within 1e-5
    reloaded, _ = load_model(out, dev)
    checks['c_gate_card_unchanged'] = cc = compare(reloaded.eval(), ref, rows, va_pos)
    cc['ok'] = max(cc['max_abs_diff'][k] for k in ('gate', 'card')) <= TOL and cc['rows_with_valid_target'] > 0

    # (d) branch weights changed and finite
    now = {n: p.detach() for n, p in model.named_parameters() if p.requires_grad}
    checks['d_branch_changed_finite'] = dict(
        max_abs_change={n: float((now[n] - branch0[n]).abs().max()) for n in now},
        finite=all(bool(torch.isfinite(v).all()) for v in now.values()),
        ok=all(bool((now[n] != branch0[n]).any()) for n in now) and all(bool(torch.isfinite(v).all()) for v in now.values()))

    result = dict(checks=checks, checkpoint=str(out), checkpoint_sha256=sha(out), updates=a.updates, batch=a.batch, lr=a.lr,
                  seed=a.seed, device=a.device, train_pool_rows=len(tr_pos), val_rows=len(va_pos),
                  final_loss=rec['loss'], pass_all=all(c['ok'] for c in checks.values()))
    (a.out_dir / 'result.json').write_text(json.dumps(result, indent=1))
    print(json.dumps(dict(RESULT=result['pass_all'], **{k: v['ok'] for k, v in checks.items()})), flush=True)
    return 0 if result['pass_all'] else 1


if __name__ == '__main__':
    sys.exit(main())
