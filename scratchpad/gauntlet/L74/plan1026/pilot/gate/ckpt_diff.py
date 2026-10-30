"""ckpt_diff.py A B -- per-tensor max |A - B| of two checkpoints' model state (keys 'model' / 'state_dict' / top level);
prints keys only in one, the count of differing tensors and the top 10. Read-only."""
import sys
import torch


def sd(p):
    st = torch.load(p, map_location='cpu', weights_only=False)
    for k in ('model', 'state_dict', 'model_state'):
        if isinstance(st, dict) and isinstance(st.get(k), dict):
            return st[k], sorted(st)
    return st, sorted(st)


(a, ka), (b, kb) = sd(sys.argv[1]), sd(sys.argv[2])
print('top-level keys A:', ka); print('top-level keys B:', kb)
print('only A:', sorted(set(a) - set(b))[:20]); print('only B:', sorted(set(b) - set(a))[:20])
d = {k: (a[k].float() - b[k].float()).abs().max().item() for k in set(a) & set(b)
     if torch.is_tensor(a[k]) and a[k].shape == b[k].shape}
diff = sorted(((v, k) for k, v in d.items() if v > 0), reverse=True)
print(f'tensors compared {len(d)}, differing {len(diff)}')
for v, k in diff[:10]:
    print(f'  {v:.3e} {k}')
