"""LOOP-OPS dry-run stand-in for LOOP-INT's fastloop.py (same argv and file contract; trains nothing): every --every s one
"update" -> icebow/data/bench/rl_royale/RUN/RUN_uNNNN.pt (the config's init bytes + the update number, tmp + os.replace)
+ its .sha256 after the rename, and a throughput.jsonl line; OUT/STOP or --max-updates -> a last checkpoint, OUT/FINAL.

    python fake_loop.py --run RUN --config CFG --out OUT [--every 5] [--max-updates 0] [anything else ignored]
"""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True)
    ap.add_argument('--config', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--every', type=float, default=5.0)
    ap.add_argument('--max-updates', type=int, default=0)
    a, _ = ap.parse_known_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    init = next(ln.split(':', 1)[1].strip() for ln in open(a.config) if ln.startswith('init:'))
    body = Path(init).read_bytes()
    ck = Path('icebow/data/bench/rl_royale') / a.run
    ck.mkdir(parents=True, exist_ok=True)
    u, t0 = 0, time.time()
    while True:
        time.sleep(a.every)
        u += 1
        p = ck / f'{a.run}_u{u:04d}.pt'
        data = body + u.to_bytes(4, 'little')
        p.with_suffix('.tmp').write_bytes(data)
        os.replace(p.with_suffix('.tmp'), p)
        Path(str(p) + '.sha256').write_text(hashlib.sha256(data).hexdigest() + '\n')
        with open(out / 'throughput.jsonl', 'a') as f:
            f.write(json.dumps({'update': u, 't': time.time() - t0, 'matches': 512 * u, 'fake': True}) + '\n')
        if (out / 'STOP').exists() or u == a.max_updates:
            (out / 'FINAL').write_text(str(p) + '\n')
            print(f'fake loop stopped at update {u}: FINAL {p}', flush=True)
            return


if __name__ == '__main__':
    main()
