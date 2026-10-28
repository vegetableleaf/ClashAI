"""LOOP-OPS 1: B0 = CLXIII NOLEAK (the live checkpoint, grafted heads incl.) + the S3-aux memory v2 encoder, coupling zero.

    python scratchpad/gauntlet/L74/plan1026/pilot/ops/build_b0.py [OUT]

B0's state dict = CLXIII's 141 tensors unchanged + the encoder file's mem.* / mem_aux.* tensors (50). The encoder file
(mem_best_ze.pt, 3d75a25d) was trained on the RAW succ48_o_s91 u75 (3eda9d23); CLXIII NOLEAK = that raw net + heads grafted
from rlarm_gae_u0250_grafted (cell_refine / tower_refine / projectile_target_*). Refuses unless: both input shas match, the
encoder file's non-memory tensors equal CLXIII's on every shared non-head tensor (same trunk), and the coupling mem.out is
exactly zero. Top level = CLXIII's (args, rl incl. the ability head, grafted_heads_from, ...) + the encoder's memory keys
(memory v2, memory_aux v1, memory_v2 artifact shas, s3 provenance) + b0 provenance.
"""
import hashlib
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[6]
CLXIII = ROOT / 'icebow/data/models/ICEBOW/ICEBOW_Mark_CLXIII_NOLEAK.pt'
ENC = Path('C:/Users/benpe/pod_backup_weekend/night1025/mem_best_ze.pt')
SHA = {CLXIII: '8d328a43bf09fb7e389d41f01524fbb50955e15b64fdb72e28488a123eabad42',
       ENC: '3d75a25d8ebedd4ed34bd63981fe676e448dedcb325fc7b3e5ff36e484175ac4'}
OUT = ROOT / 'icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt'
HEADS = ('cell_refine.', 'tower_refine.', 'projectile_target_')
MEM = ('mem.', 'mem_aux.')


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(out=OUT):
    for p, s in SHA.items():
        assert sha(p) == s, f'{p}: sha {sha(p)} != {s}'
    a = torch.load(CLXIII, map_location='cpu', weights_only=False)
    e = torch.load(ENC, map_location='cpu', weights_only=False)
    sa, se = a['model'], e['model']
    assert not any(k.startswith(MEM) for k in sa), 'CLXIII already has a memory encoder'
    trunk = [k for k in sa if not k.startswith(HEADS)]
    bad = [k for k in trunk if k not in se or not torch.equal(sa[k], se[k])]
    assert not bad, f'encoder file trunk differs from CLXIII on {bad}'
    extra = [k for k in se if k not in sa and not k.startswith(MEM)]
    assert not extra, f'encoder file has non-memory tensors CLXIII lacks: {extra}'
    mem = {k: v for k, v in se.items() if k.startswith(MEM)}
    assert mem['mem.out.weight'].abs().max() == 0 and mem['mem.out.bias'].abs().max() == 0, 'coupling mem.out is not zero'
    assert 'mem.zero_empty' in mem, 'encoder lacks zero_empty'
    b0 = {**a, 'model': {**sa, **mem}}
    for k in ('memory', 'memory_aux', 'memory_v2', 's3'):
        b0[k] = e[k]
    b0['b0'] = {'base': str(CLXIII.relative_to(ROOT)).replace('\\', '/'), 'base_sha256': SHA[CLXIII],
                'encoder': str(ENC).replace('\\', '/'), 'encoder_sha256': SHA[ENC], 'coupling': 'zero (mem.out = 0)',
                'tensors': {'clxiii': len(sa), 'memory': len(mem)}, 'builder': 'scratchpad/gauntlet/L74/plan1026/pilot/ops/build_b0.py'}
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp')
    torch.save(b0, tmp)
    tmp.replace(out)
    chk = torch.load(out, map_location='cpu', weights_only=False)['model']
    assert all(torch.equal(chk[k], sa[k]) for k in sa) and all(torch.equal(chk[k], mem[k]) for k in mem)
    print(f'B0 {out} sha256 {sha(out)}: {len(sa)} CLXIII tensors (trunk {len(trunk)} == encoder file) + {len(mem)} memory '
          f'tensors; mem.out max |w| 0.0')


if __name__ == '__main__':
    main(*sys.argv[1:])
