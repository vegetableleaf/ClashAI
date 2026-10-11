"""Pod smoke checks on a toy dataset (review aid; not part of the production chain).

  smoke_checks.py init  BASE DATA OUTDIR   -> convert; converted outputs == base outputs bit-for-bit on real rows
  smoke_checks.py train BASE TRAINED DATA  -> only history.* moved; ablated checkpoint zeroes only the history input
  smoke_checks.py sim   MEMORY_CKPT OUTDIR  -> one real SIM game: the memory model receives non-empty public histories at decision time
"""
import sys
import time
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from pipeline.model_gen import load_model          # noqa: E402
from pipeline.eval_gen import GenRows              # noqa: E402
from pipeline.dataset_spool import load_mapped     # noqa: E402


def rows(data, n=64):
    arrs, meta = load_mapped(data, Path(data).parent / f'smoke_cache_{time.time_ns()}')
    idx = np.arange(min(n, len(arrs['split'])))
    b = GenRows(arrs, idx, 'cpu').batch(idx)
    h = b['history_events']
    print('rows', len(idx), 'history tensor', tuple(h.shape), 'rows with any event', int((h.abs().sum((1, 2)) > 0).sum()),
          'mean events/row', float((h.abs().sum(-1) > 0).sum(1).float().mean()))
    return b, meta


def out(model, b):
    with torch.no_grad():
        return model(b, card=b['card'], form=b['form'])


def init(base, data, outdir):
    from pipeline.add_memory import convert
    Path(outdir).mkdir(parents=True, exist_ok=True)
    dst = Path(outdir) / 'memory_zero_init.pt'
    convert(base, dst, cap=256)
    b, meta = rows(data)
    assert meta['history_cap'] == 256 and meta['history_events']
    m0, _ = load_model(base, torch.device('cpu'))
    m1, _ = load_model(dst, torch.device('cpu'))
    m0.eval(), m1.eval()
    o0, o1 = out(m0, {k: v for k, v in b.items() if k != 'history_events'}), out(m1, b)
    for k in o0:
        assert torch.equal(o0[k], o1[k]), f'converted output differs from base: {k}'
    print('INIT_EQUAL_OK keys', sorted(o0), 'history params', sum(p.numel() for n, p in m1.named_parameters() if n.startswith('history.')))


def train(base, trained, data):
    sys.path.insert(0, str(ROOT / 'scratchpad/gauntlet/L74/memory'))
    import driver as D
    b, _ = rows(data)
    sb = torch.load(base, map_location='cpu', weights_only=True)['model']
    st = torch.load(trained, map_location='cpu', weights_only=True)['model']
    others = [k for k in st if not k.startswith('history.')]
    assert set(others) == set(sb) and all(torch.equal(sb[k], st[k]) for k in others), 'non-history tensor changed'
    print('NON_HISTORY_UNCHANGED_OK tensors', len(others))
    abl = Path(trained).with_name('ablated.pt')
    D.ablate(trained, abl)
    m, _ = load_model(trained, torch.device('cpu'))
    z, _ = load_model(abl, torch.device('cpu'))
    m.eval(), z.eval()
    assert z.history.zero_history and not m.history.zero_history
    zero_b = dict(b, history_events=torch.zeros_like(b['history_events']))
    on, off, ref = out(m, b), out(z, b), out(m, zero_b)
    assert all(torch.equal(off[k], ref[k]) for k in on), 'ablation is not equivalent to zeroed history input'
    diff = max(float((on[k] - off[k]).abs().max()) for k in on if torch.is_floating_point(on[k]))
    print('ABLATION_ZEROES_HISTORY_OK max |memory - ablated| =', diff, '(0 means the trained gate has not opened yet)')


def sim(ckpt, outdir):
    from pipeline import model_gen, search_s0
    sys.path.insert(0, str(ROOT / 'scratchpad/gauntlet/L74/memory'))
    import driver as D
    seen = []
    real = model_gen.GenModel.encode_gen

    def spy(self, b):
        if hasattr(self, 'history'):
            h = b['history_events']
            seen.append((int(h.shape[0]), int((h.abs().sum((1, 2)) > 0).sum()), int((h.abs().sum(-1) > 0).sum(1).max())))
        return real(self, b)

    model_gen.GenModel.encode_gen = spy
    cmd = D.A.eval_command(ckpt, outdir, D.A.EVO, 30000, 1, 1)
    search_s0.main([str(x) for x in cmd[3:]])
    assert seen, 'memory model never ran in the SIM path'
    print('SIM_HISTORY_OK decisions', len(seen), 'with non-empty history', sum(1 for s in seen if s[1]), 'max events in one history', max(s[2] for s in seen))


if __name__ == '__main__':
    {'init': init, 'train': train, 'sim': sim}[sys.argv[1]](*sys.argv[2:])
