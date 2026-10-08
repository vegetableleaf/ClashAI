"""Verifier: real live_gen_v2.GenPilot (live ckpt, fv>=4) over recorded live SB frames; digest of decide() outputs."""
import copy, glob, hashlib, json, os, sys
ROOT = os.path.abspath(sys.argv[1]); FLAG = '--on' in sys.argv
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, 'scratchpad/gauntlet/L73/skeleton_barrel/fix'))
import ctypes; ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
import numpy as np, torch
torch.set_num_threads(2)
from pipeline.live_gen_v2 import GenPilot
from pipeline.tests.test_live_mem import FRAME
LIVE = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader'
CK = r'C:/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt'
kw = {'predict_drops': True} if FLAG else {}
p = GenPilot(CK, device='cpu', gate_tau=0.35, use_counter=True, extrapolate_ticks=26, **kw)
print('fv', p.feature_version, 'drops', getattr(p, 'drops', 'ABSENT'))
def frames_of(path):
    for line in open(path, encoding='utf-8'):
        if '"event": "frame"' not in line[:30]: continue
        e = json.loads(line)
        if e.get('ents') is None: continue
        ents = [dict(side=b[0], x=b[1], y=b[2], card_id=b[3], hp=b[4], max_hp=b[5], kind=b[6], address=b[7]) for b in e['ents']]
        f = copy.deepcopy(FRAME); f['game_tick'], f['entities'] = int(e['tick']), ents
        if int(e['my_side']) != 1:
            f['players'][0], f['players'][1] = dict(f['players'][1], side=0), dict(f['players'][0], side=1)
        yield f
tot = hashlib.sha256(); n = 0
files = [f for f in sorted(glob.glob(os.path.join(LIVE, 'live_play_2026*.jsonl'))) if '26000056' in open(f, encoding='utf-8').read()][:4]
for path in files:
    p.reset_match()
    for i, f in enumerate(frames_of(path)):
        p.observe(f)
        if i % 5: continue
        d = p.decide(f)
        tot.update(repr(sorted((k, v) for k, v in d.items() if k not in ('bs',) and not hasattr(v, 'units'))).encode()); n += 1
    print(os.path.basename(path), n, flush=True)
print('LIVEDIGEST', n, tot.hexdigest())
