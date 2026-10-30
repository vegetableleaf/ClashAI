"""meta_diff.py A B -- the non-tensor checkpoint metadata of A vs B: top-level keys in one only, and every differing
(nested) value of the shared dict keys (args, rl, gen, memory, memory_v2, ...). Read-only."""
import sys
import torch


def flat(x, p=''):
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            out.update(flat(v, f'{p}.{k}' if p else str(k)))
        return out
    return {p: x if not torch.is_tensor(x) else ('tensor', tuple(x.shape))}


A, B = (torch.load(p, map_location='cpu', weights_only=False) for p in sys.argv[1:3])
print('only A:', sorted(set(A) - set(B))); print('only B:', sorted(set(B) - set(A)))
for k in sorted(set(A) & set(B)):
    if k == 'model':
        continue
    fa, fb = flat(A[k], k), flat(B[k], k)
    for q in sorted(set(fa) | set(fb)):
        va, vb = fa.get(q, '<absent>'), fb.get(q, '<absent>')
        if repr(va) != repr(vb):
            print(f'{q}: A={repr(va)[:150]} | B={repr(vb)[:150]}')
for k in sorted(set(A) - set(B)):
    print(f'A only {k}: {repr(A[k])[:300]}')
