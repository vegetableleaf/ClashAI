"""measure1026 step 1 (read-only): one pass over the Ranked live logs of CLX / CLXIII / CLXIV -> live_cache.pkl.

    icebow/.venv/Scripts/python.exe -B -X utf8 scratchpad/gauntlet/L74/memory/measure1026/live_pass.py

Per match: model, ts, side, own princess max HP (main account = 4858), end record, last tick, decision samples (tick, towers,
alive), the memory events (live_dump.read -> match_memory.build(...).events), and -- only when the OPPONENT played a Mortar or an
X-Bow -- a raw frame track: every Mortar / X-Bow body of both sides per frame (catalog display name of the reader card id),
every projectile whose source address is such a body (target xy, projectile address), and the 6 tower HPs per frame.
Ranked = every main-account match since 20261020_132855 (clx_ranked/anatomy.py rule). Idle priority (shared laptop)."""
import ctypes
import json
import pickle
import sys
import time
from pathlib import Path

try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:
    pass

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path[:0] = [str(HERE.parent), str(REPO)]
import live_dump as LD  # noqa: E402
from pipeline import match_memory as M  # noqa: E402
from pipeline.dataset_gen import card_key  # noqa: E402
from pipeline.obs_contract import catalog_card_form  # noqa: E402

LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
RANKED_START = '20261020_132855'
KEYS = (('CLXIV_MEMORY', 'CLXIV'), ('CLXIII_NOLEAK', 'CLXIII'), ('CLX_PARITY', 'CLX'), ('stepd_ctrl_nos2_u0130_grafted', 'CLX'))
SIEGE = {'Mortar', 'X-Bow', 'Xbow'}
OUT = HERE / 'live_cache.pkl'


def model_of(f):
    with open(f, 'rb') as fh:
        for _, raw in zip(range(400), fh):
            if b'"event": "start"' in raw[:60]:
                ck = json.loads(raw).get('ckpt', '')
                return next((g for k, g in KEYS if k in ck), None), Path(ck.replace('\\', '/')).name
    return None, None


def frame_track(f):
    bodies, proj, towers, names, src_ok, pmax = [], [], [], {}, set(), {}
    for raw in open(f, 'rb'):
        if b'"frame"' not in raw[:40]:
            continue
        j = json.loads(raw)
        t = j['tick']
        tw = []
        for e in j['ents']:
            s_, x, y, cid, hp, mx, kind, addr = e
            if cid == -1 and any(abs(x - tx) < 600 and abs(y - ty) < 600 for tx, ty in LD.TOWER_SLOTS):
                tw.append((s_, x, y, hp, mx))
                continue
            if cid not in names:
                names[cid] = catalog_card_form(cid)[0]
            if names[cid] in SIEGE:
                bodies.append((t, s_, addr, x, y, hp, mx, names[cid]))
                src_ok.add(addr)
        towers.append((t, tw))
        for p in j.get('proj') or []:
            if len(p) > 8 and p[8] in src_ok:
                proj.append((t, p[0], p[6], p[8], p[1], p[2], p[4], p[5], p[3]))
    return dict(bodies=bodies, proj=proj, towers=towers)


def main():
    cache = {}
    if OUT.exists():
        cache = pickle.load(open(OUT, 'rb'))
    t0, n_new = time.time(), 0
    for f in sorted(LOGS.glob('live_play_2026102*.jsonl')):
        ts = f.stem.replace('live_play_', '')
        if ts < RANKED_START or f.name in cache:
            continue
        if b'"event": "end"' not in open(f, 'rb').read()[-4000:]:
            continue                                            # unfinished (a match in progress) or a crashed log
        g, ck = model_of(f)
        if g is None:
            continue
        try:
            m = LD.read(f)
        except Exception as exc:
            print('skip', f.name, repr(exc)[:120], flush=True)
            continue
        if not m['samples'] or not m['end']:
            continue
        side = m['side']
        ev = M.build(side, m['samples'], m['plays']).events(m['last'] + 1)
        first = None
        with open(f, 'rb') as fh:
            for raw in fh:
                if b'"frame"' in raw[:40]:
                    first = json.loads(raw)
                    break
        pm = max([e[5] for e in first['ents'] if e[3] == -1 and e[0] == side and e[5] < 6000] or [0]) if first else 0
        opp_cards = {card_key(str(p['card'])) for p in m['plays'] if p.get('side') != side}
        rec = dict(model=g, ckpt=ck, ts=ts, side=side, pmax=pm, end=m['end'], last=m['last'],
                   samples=[(s['tick'], s['towers'], s['alive']) for s in m['samples']], events=ev, opp_cards=sorted(opp_cards))
        if opp_cards & {'mortar', 'x-bow'}:
            rec['track'] = frame_track(f)
        cache[f.name] = rec
        n_new += 1
        if n_new % 25 == 0:
            print(n_new, f.name, round(time.time() - t0), 's', flush=True)
            pickle.dump(cache, open(OUT, 'wb'))
    pickle.dump(cache, open(OUT, 'wb'))
    print('done', n_new, 'new,', len(cache), 'total', round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
