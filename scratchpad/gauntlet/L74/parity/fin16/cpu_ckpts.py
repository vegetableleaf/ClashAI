"""cpu_ckpts.py CONFIG.yaml: re-save, IN PLACE, every .pt path a config names (relative to the cwd) with its tensors mapped to
the CPU, so `rl_royale --smoke` runs with CUDA hidden (A1 10-27: pod 32657's GPU belongs to another worker). Run ONLY inside a
throw-away copy of a code tree (cp -a, not a hard-link copy): it rewrites the files."""
import re
import sys
from pathlib import Path

import torch

paths = sorted(set(re.findall(r'[\w./-]+\.pt\b', Path(sys.argv[1]).read_text())))
for p in map(Path, paths):
    if not p.is_file():
        print('absent', p)
        continue
    if p.stat().st_nlink > 1:
        raise SystemExit(f'{p} is hard-linked: refusing to rewrite it')
    obj = torch.load(p, map_location='cpu', weights_only=False)
    torch.save(obj, p)
    print('cpu', p)
