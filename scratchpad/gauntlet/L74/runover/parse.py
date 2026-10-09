"""L74 runover, pass 1: live logs since 10-05 -> compact per-match records (cache.pkl). Read-only on the logs.

Run from the MAIN checkout (catalog + RoyaleSim data live there):
  cd C:/Users/benpe/ClashBot && icebow/.venv/Scripts/python.exe <worktree>/scratchpad/gauntlet/L74/runover/parse.py
Single process, below-normal priority. Public information only (own state, visible bodies, own decision record).
Per state: tick, own elixir, hand (name, cost, form), decision (play, p, tau, name, no_affordable), my/enemy tower HP by
slot, enemy bodies (own-frame x, y, raw name, form, max_hp, hp, resolved vocab class, identity reason, parent-body flag),
and the classes the model actually received (model_bodies, enemy side).
"""
import os, sys, glob, json, pickle, time, collections
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
sys.path.insert(0, '.')
from pipeline.obs_contract import _catalog_names, catalog_card_form
from pipeline import vocab, body_identity as BI

HERE = os.path.dirname(os.path.abspath(__file__))
LOGDIR = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
OUT = os.path.join(HERE, 'cache.pkl')
NAMES = _catalog_names()


def own(side, x, y):
    return ((18000 - x) / 1000.0, (32000 - y) / 1000.0) if side == 1 else (x / 1000.0, y / 1000.0)


def tslot(X, Y, kind):
    k = 'K' if (abs(X - 9) < 0.6 and (Y < 4 or Y > 28)) else ('L' if X < 9 else 'R')
    return ('m' if Y < 16 else 'e') + k


# own-body HP of a card at every level (parent body test for cards outside body_identity.FAMILIES)
_cat, _ = BI._catalog()
_REC = {c['name']: c for c in _cat['cards']}
_REC.update({e['name']: e for e in _cat['evolutions']})


def parent_hps(name, form):
    rec = _REC.get(name + '_EV1') if form == 1 else None
    rec = rec or _REC.get(name)
    if rec is None or rec.get('hitpoints') is None: return None
    try:
        return {h * m // 100 for _, m in BI._levels(rec) for h in BI._hitpoints(name, rec)}
    except Exception:
        return None


_PH = {}


def is_parent_body(name, form, mhp, ident):
    """True = the card's own body; False = a different body named by the card (spawn / sub-unit); None = unknown."""
    if ident.reason in ('parent',): return True
    if ident.reason in ('child', 'child_no_class', 'explicit_child', 'unnamed'): return False
    k = (name, form)
    if k not in _PH: _PH[k] = parent_hps(name, form)
    hs = _PH[k]
    if hs is None or mhp is None or mhp <= 0: return None
    return any(abs(mhp - h) <= 2 for h in hs)


_RES = {}


def resolve_cached(board, fac):
    key = (board, tuple(sorted(fac.items())))
    r = _RES.get(key)
    if r is None:
        r = BI.resolve_board(list(board), fac)
        if len(_RES) < 400000: _RES[key] = r
    return r


def parse(f):
    rec = dict(file=os.path.basename(f), start=None, end=None, S=[], plays=[], conf=[])
    for l in open(f, encoding='utf8', errors='replace'):
        if not l.startswith('{"event": "'): continue
        ev = l[11:l.index('"', 11)]
        if ev in ('button', 'menu_guard_off', 'recording', 'waiting_clock', 'tap_timing', 'frame'): continue
        try: d = json.loads(l)
        except ValueError: continue
        if ev == 'start':
            do = d.get('decision_options') or {}
            rec['start'] = dict(ckpt=os.path.basename(str(d.get('ckpt') or '').replace('\\', '/')), dry=bool(d.get('dry_run')),
                                fv=d.get('feature_version'), opts=do, fast=d.get('fast_input'), afford=d.get('afford_ticks'),
                                extrap=d.get('extrapolate'), sha8=(d.get('ckpt_sha256') or '')[:8])
        elif ev == 'end' or ev == 'stop':
            rec['end'] = rec['end'] or dict(ev=ev, **{k: d.get(k) for k in ('seconds', 'why', 'played')})
        elif ev == 'play':
            xy = d.get('xy'); xy = json.loads(xy) if isinstance(xy, str) else xy
            rec['plays'].append((d.get('tick'), d.get('name'), tuple(xy) if xy else None, d.get('elixir'), d.get('p_play'), bool(d.get('forced'))))
        elif ev == 'confirmed':
            rec['conf'].append((d.get('tick'), d.get('name')))
        elif ev == 'decision':
            p = d.get('public') or {}; dc = d.get('decision') or {}
            if 'observer_side' not in p or 'raw_bodies' not in p: continue
            s = p['observer_side']
            mt, et, fac, enemy = {}, {}, {}, []
            for b in p['raw_bodies']:
                cid = int(b.get('card_id', -1)); X, Y = own(s, b['x'], b['y']); mine = b['side'] == s
                if cid == -1 and b.get('kind') in (12, 13):
                    sl = tslot(X, Y, b['kind']); (mt if mine else et)[sl] = b['hp']
                    if b.get('max_hp', 0) > 0:
                        fac.setdefault(b['side'], b['max_hp'] / (4824.0 if sl[1] == 'K' else 3052.0))
                    continue
                if mine or b['hp'] is None or (b['hp'] <= 0 and b['max_hp'] > 0): continue
                unnamed = cid < 0
                name = NAMES.get(cid, str(cid)) if not unnamed else '-1'
                form = catalog_card_form(cid)[1] if not unnamed else 0
                enemy.append((b['side'], name, float(b['max_hp']), form, unnamed, X, Y, b['hp'], b.get('kind')))
            ids = resolve_cached(tuple(e[:5] for e in enemy), fac) if enemy else []
            eb = []
            for e, ident in zip(enemy, ids):
                side, name, mhp, form, unnamed, X, Y, hp, kind = e
                if ident.cls is None and unnamed: continue
                cls = vocab.UNIT_VOCAB[ident.cls] if ident.cls is not None else None
                eb.append((round(X, 2), round(Y, 2), name, form, mhp, hp, cls, ident.reason, is_parent_body(name, form, mhp, ident), kind))
            mb = tuple(vocab.UNIT_VOCAB[m['cls']] for m in p.get('model_bodies', []) if m.get('side') == 1)
            hand = tuple((h.get('name'), h.get('cost'), h.get('form')) for h in p.get('own_hand', []))
            dec = (bool(dc.get('play')), dc.get('p_play'), dc.get('gate_tau'), dc.get('name'), bool(dc.get('no_affordable')), bool(dc.get('hazard_play')), dc.get('form'))
            rec['S'].append((d['tick'], p.get('own_elixir_raw'), hand, dec, mt, et, tuple(eb), mb))
    return rec


def main():
    files = sorted(f for f in glob.glob(LOGDIR + 'live_play_2026*.jsonl') if os.path.basename(f)[10:25] >= '20261005_000000')
    cache = {}
    if os.path.exists(OUT):
        cache = pickle.load(open(OUT, 'rb'))
    now = time.time(); t0 = time.time(); n = 0
    for f in files:
        b = os.path.basename(f)
        if b in cache or now - os.path.getmtime(f) < 300: continue
        try: cache[b] = parse(f)
        except Exception as e: cache[b] = dict(file=b, error=f'{type(e).__name__}: {e}')
        n += 1
        if n % 25 == 0:
            print(f'[{n}] {b} {time.time() - t0:.0f}s', flush=True)
            pickle.dump(cache, open(OUT, 'wb'))
    pickle.dump(cache, open(OUT, 'wb'))
    print(f'parsed {n} new, cache {len(cache)} logs, {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
