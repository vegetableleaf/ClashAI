"""Plan A gate G-mem-0 (S1b): a memory model at init = CLXIII exactly.

    icebow/.venv/Scripts/python.exe -B -X utf8 scratchpad/gauntlet/L74/memory/gmem0.py [--rows 2500] > gmem0.out

Rows: the first N rows of icebow/data/pipeline/gen_dataset_v32_fv5.npz (the pro set CLXIII's imitation parent trained on),
read as a STREAMED PREFIX of each npz member (no member is loaded whole: projectiles alone are 7.2 GB). Models: CLXIII
(icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt, the grafted live file) loaded plain, and the same file loaded with
model_gen.load_model(..., memory="v1") (the fv6 checkpoint has no memory weights -> a fresh zero-output encoder), fed RANDOM
memory inputs (random floats / masks incl. empty memories / card ids / forms / summaries / answer cards). CPU (the laptop GPU
belongs to the live bot). Compared per row: the gate log-prob of both outcomes, the hand-card log-softmax, the cell
log-softmax for the row's card (2,304 cells; wait rows: the first hand card), the value-head softmax: max |diff|.
Then two liveness checks: a perturbed output layer changes the outputs; one backward gives the output layer a gradient."""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as Fn

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline import match_memory as MM  # noqa: E402
from pipeline.eval_gen import GenRows  # noqa: E402
from pipeline.model_gen import load_model  # noqa: E402

NPZ = REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5.npz'
CKPT = REPO / 'icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt'
PER_TOKEN = ('tok', 'unit_form')


def npz_prefix(path, n):
    """The first n rows of every member (per-token members: the first off[n] tokens; off: n + 1), streamed."""
    z = zipfile.ZipFile(path)
    names = [i.filename[:-4] for i in z.infolist()]

    def read(name, rows):
        with z.open(name + '.npy') as f:
            ver = np.lib.format.read_magic(f)
            shape, fortran, dtype = (np.lib.format.read_array_header_1_0(f) if ver == (1, 0)
                                     else np.lib.format.read_array_header_2_0(f))
            if fortran or not shape:
                return np.load(z.open(name + '.npy'))
            rows = shape[0] if rows is None else min(rows, shape[0])
            per = int(np.prod(shape[1:], dtype=np.int64))
            return np.frombuffer(f.read(rows * per * dtype.itemsize), dtype).reshape((rows,) + tuple(shape[1:])).copy()
    off = read('off', n + 1)
    out = {'off': off}
    for k in names:
        if k in ('off', 'meta', 'tags'):
            continue
        out[k] = read(k, int(off[-1]) if k in PER_TOKEN else n)
    return out


def outputs(model, b):
    out = model(b, card=b['_cell_card'], form=b['_cell_form'])
    g = out['gate'].double()
    card = out['card'].double()
    return dict(gate=torch.stack([Fn.logsigmoid(g), Fn.logsigmoid(-g)], -1),
                card=torch.where(torch.isfinite(card), torch.log_softmax(card, -1), torch.zeros_like(card)),
                cell=torch.log_softmax(out['cell'].double(), -1), value=torch.softmax(out['value'].double(), -1))


def random_memory(n, n_cards, rng):
    m = MM.empty_rows(n)
    m['mem_ev'][:] = rng.random(m['mem_ev'].shape, dtype=np.float32)
    k = rng.integers(0, MM.E_MAX + 1, n)
    k[::7] = 0                                                  # every 7th row: an EMPTY memory
    m['mem_mask'][:] = np.arange(MM.E_MAX)[None] < k[:, None]
    m['mem_card'][:] = rng.integers(0, n_cards, m['mem_card'].shape)
    m['mem_form'][:] = rng.integers(0, 4, m['mem_form'].shape)
    m['mem_summary'][:] = rng.random(m['mem_summary'].shape, dtype=np.float32)
    m['mem_answer'][:] = rng.integers(0, n_cards, n)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rows', type=int, default=2500)
    ap.add_argument('--bs', type=int, default=250)
    a = ap.parse_args()
    torch.set_num_threads(4)
    dev = torch.device('cpu')
    arrs = npz_prefix(NPZ, a.rows)
    n = len(arrs['y_gate'])
    base, st = load_model(CKPT, dev)
    mem, _ = load_model(CKPT, dev, memory='v1')
    base.eval(), mem.eval()
    rows = GenRows(arrs, np.arange(n), dev)
    rng = np.random.default_rng(0)
    worst = {k: 0.0 for k in ('gate', 'card', 'cell', 'value')}
    n_play = 0
    with torch.no_grad():
        for s in range(0, n, a.bs):
            ids = np.arange(s, min(s + a.bs, n))
            b = rows.batch(ids)
            play = b['gate'] > .5
            n_play += int(play.sum())
            b['_cell_card'] = torch.where(play, b['card'], b['hand_card'][:, 0])
            b['_cell_form'] = torch.where(play, b['form'], b['hand_form'][:, 0])
            ref = outputs(base, b)
            bm = dict(b, **{k: torch.from_numpy(v) for k, v in random_memory(len(ids), len(st['card_vocab']), rng).items()})
            got = outputs(mem, bm)
            for k in worst:
                worst[k] = max(worst[k], float((got[k] - ref[k]).abs().max()))
    print(f'G-mem-0: {n} real rows ({n_play} play rows) from {NPZ.name} prefix; CLXIII vs CLXIII + memory v1 (random memory '
          f'inputs, every 7th row empty)')
    print('  max |diff|:', ' '.join(f'{k} {v:.3g}' for k, v in worst.items()), '->',
          'PASS (< 1e-6)' if max(worst.values()) < 1e-6 else 'FAIL')
    n_mem = sum(p.numel() for p in mem.mem.parameters())
    print(f'  memory encoder parameters: {n_mem:,} (base model {sum(p.numel() for p in base.parameters()):,})')
    # liveness: a nonzero output layer moves the outputs; the output layer gets a gradient at init
    b = rows.batch(np.arange(min(64, n)))
    b['_cell_card'], b['_cell_form'] = b['hand_card'][:, 0], b['hand_form'][:, 0]
    bm = dict(b, **{k: torch.from_numpy(v) for k, v in random_memory(len(b['gate']), len(st['card_vocab']), rng).items()})
    out = mem(bm, card=bm['_cell_card'], form=bm['_cell_form'])
    (out['gate'].sum() + out['value'].sum()).backward()
    gnorm = float(mem.mem.out.weight.grad.norm())
    with torch.no_grad():
        mem.mem.out.weight.normal_(0, 0.01)
        moved = float((mem(bm)['gate'] - base(b)['gate']).abs().max())
    print(f'  liveness: output-layer grad norm at init {gnorm:.3g} (> 0 = it can learn); perturbed output layer moves the '
          f'gate logit by up to {moved:.3g}')


if __name__ == '__main__':
    main()
