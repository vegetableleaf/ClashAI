"""Default-off identity on RECORDED live frames: digest of GenPilot.row()'s model input (tok / mask / sc / unit rows) and
of the extrapolated reader frame, for every 5th frame of every live frame log with a Skeleton Barrel.

    identity_live.py <repo_root> [--predict-drops]      # run once per tree (HEAD copy vs the worktree), compare the digests

The pilot is the stub of test_live_gen_afford (no checkpoint): row() is the whole look-ahead -> tokens path.
"""
import copy, glob, hashlib, json, os, sys
from collections import deque

ROOT = os.path.abspath(sys.argv[1])
FLAG = '--predict-drops' in sys.argv
sys.path.insert(0, ROOT)
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
import numpy as np, torch                                              # noqa: E402
torch.set_num_threads(4)
from pipeline.dataset_gen import card_key                              # noqa: E402
from pipeline.live_gen import GenPilot                                 # noqa: E402
from pipeline.live_mem import deck_of                                  # noqa: E402
from pipeline.tests.test_live_mem import FRAME                         # noqa: E402

try:
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except Exception:
    pass
LIVE = r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader'


def frames_of(path):
    out = []
    for line in open(path, encoding='utf-8'):
        if '"event": "frame"' not in line[:30]:
            continue
        e = json.loads(line)
        if e.get('ents') is None:
            continue
        ents = [dict(side=b[0], x=b[1], y=b[2], card_id=b[3], hp=b[4], max_hp=b[5], kind=b[6], address=b[7]) for b in e['ents']]
        f = copy.deepcopy(FRAME)
        me = 1                                                       # FRAME's visible hand is side 1; mirror the roles if needed
        f['game_tick'], f['entities'] = int(e['tick']), ents
        if int(e['my_side']) != me:
            f['players'][0], f['players'][1] = dict(f['players'][1], side=0), dict(f['players'][0], side=1)
        out.append((int(e['my_side']), f))
    return out


def pilot():
    p = object.__new__(GenPilot)
    _, names = deck_of(FRAME, 1)
    p.gid = {card_key(n): i + 1 for i, n in enumerate(names)}
    p.grid, p.dev, p.gate_tau = 'lattice', torch.device('cpu'), 0.5
    p.past, p.history, p.opp, p.opp_est = [], {}, None, None
    p.ext_h, p.frames = 26, deque(maxlen=30)
    if FLAG:
        from pipeline.extrapolate import DropTracker
        p.drops = DropTracker()
    return p


tot, n, n_unit_diff = hashlib.sha256(), 0, 0
for f in sorted(glob.glob(os.path.join(LIVE, 'live_play_2026*.jsonl'))):
    s = open(f, encoding='utf-8').read()
    if not (('26000056' in s or '13000056' in s) and '"event": "frame"' in s):
        continue
    p = pilot()
    h = hashlib.sha256()
    for i, (side, fr) in enumerate(frames_of(f)):
        p.observe(fr)
        if i % 5:
            continue
        b, info = p.row(fr)
        for k in ('tok', 'mask', 'sc'):
            h.update(np.ascontiguousarray(b[k].numpy()).tobytes())
        h.update(repr([(u.cls, u.side, round(u.x, 6), round(u.y, 6), u.deploying) for u in info['bs'].units]).encode())
        n += 1
    tot.update(h.digest())
    print(os.path.basename(f), h.hexdigest()[:16], flush=True)
print('FRAMES', n, 'TOTAL', tot.hexdigest())
