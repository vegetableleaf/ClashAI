"""Drift (<1%, from the saved checkpoint) + 8-game smoke of ADAPTFIX/adapt_fixed.pt (hard opponent, pipelining ON, record-plays). Exit 1 = fail."""
import importlib.util, json, os, sys
from pathlib import Path
ROOT = Path('/workspace/wt_tornado'); os.chdir(ROOT); sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('tornado_driver', ROOT / 'scratchpad/gauntlet/L74/tornado/driver.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
import torch
out = Path(sys.argv[1]); fixed = out / 'adapt_fixed.pt'
t = torch.load(fixed, map_location='cpu', weights_only=True)['pending_pretrain']
drift = t['ordinary_top_card_drift']; print('ordinary_top_card_drift', drift, 'epoch', t.get('epoch'))
assert drift < .01, 'drift >= 1%'
dest = out / 'smoke_evo'
cmd = D.eval_command(fixed, dest, D.A.EVO, 30000, 8, D.A.CAL_C, .1, True)
cmd[cmd.index('--seeds') + 1] = '30000:30008'
D.run(cmd, out / 'smoke_search.log')
rows = [json.loads(s) for s in (dest / 'matches.jsonl').read_text().splitlines()]
assert len(rows) == 8 and not any(r.get('skipped') for r in rows) and all(r.get('outcome') in ('win', 'draw', 'loss') for r in rows), 'smoke incomplete'
print('smoke games', len(rows), 'wins', sum(r['outcome'] == 'win' for r in rows), 'draws', sum(r['outcome'] == 'draw' for r in rows),
      'pipelined games', sum('pipeline_decisions' in r for r in rows))
