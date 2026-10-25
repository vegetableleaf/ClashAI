"""Memory checkpoint -> the same with ``mem.out.bias`` shifted so an EMPTY memory adds exactly 0 to the global vector
(the S3 adapter's constant offset removed; the memory-dependent part unchanged). Usage: make_delta.py IN.pt OUT.pt
Check printed: max |memory-model - base| on an empty memory (must be ~0) for gate / card / value on a dummy-free basis
(the encoder output itself)."""
import sys

import numpy as np
import torch

sys.path.insert(0, '.')
from pipeline import match_memory as MM  # noqa: E402
from pipeline.model_gen import load_model  # noqa: E402


def empty_out(model):
    """The encoder's output for an empty memory (a constant: only the BOS token is valid, the summary is all zeros)."""
    e = {k: torch.from_numpy(v) for k, v in MM.empty_rows(1, model.mem.version).items()}
    with torch.no_grad():
        return model.mem(e['mem_ev'], e['mem_mask'].bool(), model.emb(e['mem_card'], e['mem_form']), e['mem_summary'],
                         model.card_id(e['mem_answer'].long()))[0]


def main():
    src, dst = sys.argv[1:3]
    st = torch.load(src, map_location='cpu', weights_only=False)
    model = load_model(src, torch.device('cpu'))[0].eval()
    c = empty_out(model)
    print(f'empty-memory offset |c|: max {float(c.abs().max()):.4f} L2 {float(c.norm()):.4f} (global vector dim {len(c)})')
    st['model']['mem.out.bias'] = st['model']['mem.out.bias'] - c
    st['s3_delta'] = {'src': src, 'offset_l2': float(c.norm()), 'note': 'mem.out.bias -= encoder(empty memory)'}
    torch.save(st, dst)
    left = empty_out(load_model(dst, torch.device('cpu'))[0].eval())
    print(f'after: empty-memory output max |.| {float(left.abs().max()):.2e}')
    assert float(left.abs().max()) < 1e-5


if __name__ == '__main__':
    main()
