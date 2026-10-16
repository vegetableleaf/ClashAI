"""S6 collector: replay a live log's fights with fights.py (unchanged) and, each frame, compare the SIM's
sim_unit_state.extract with the live reader's cue fields for the same bodies (joined through fights' pairing).

    PARITY_SIM_PATH=<unpacked royalesim 0.1.35> python collect.py LIVE_STEM [--max-fights N] [--out DIR]

Writes DIR/<stem>.jsonl.gz: one JSON line per paired body per frame ('b'), per frame projectile/area lists ('p', 'a').
fights.py is imported, never edited: Engine.bodies, run_fight and measure are wrapped in this process only.
"""
import gzip
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import scratchpad.gauntlet.L74.parity.fights as F          # noqa: E402
if os.environ.get('S6_EXTRACTOR'):                          # baseline run: the extractor as committed (HEAD), loaded from a file
    import importlib.util
    _sp = importlib.util.spec_from_file_location('sim_unit_state_before', os.environ['S6_EXTRACTOR'])
    U = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(U)
else:
    from pipeline import sim_unit_state as U                # noqa: E402
import live_cues as LC                                      # noqa: E402

CTX = dict(on=False)
OUT = []


def tower_id(team, x_tiles):
    mt = x_tiles * 1000
    return f"T{team}" + ('K' if abs(mt - 9000) < 1000 else 'L' if mt < 9000 else 'R')


_orig_bodies, _orig_measure, _orig_run_fight = F.Engine.bodies, F.measure, F.run_fight


def bodies(self, by_name):
    st, out = _orig_bodies(self, by_name)
    if CTX['on']:
        CTX['cues'][st['tick']] = U.extract(self.b, CTX['memo'], hit_window_ms=100)
    return st, out


def measure(rows, setup, flags, catalog, stamp):
    if CTX['on'] and CTX.get('rows') is None:
        CTX['rows'], CTX['setup'], CTX['catalog'] = rows, setup, catalog
    return _orig_measure(rows, setup, flags, catalog, stamp)


def run_fight(eng, m, events, fight, catalog, by_name, levels, tower_levels, top, ceiling=0):
    CTX.update(on=True, cues={}, memo={}, rows=None)
    try:
        r = _orig_run_fight(eng, m, events, fight, catalog, by_name, levels, tower_levels, top, ceiling)
    finally:
        CTX['on'] = False
    if CTX['rows']:
        try:
            OUT.extend(compare(m, fight, CTX['rows'], CTX['setup'], catalog, CTX['cues']))
        except Exception as e:                   # one fight must not stop the collection
            import traceback
            OUT.append(dict(k='err', fight=fight['t0'], err=repr(e), tb=traceback.format_exc()[-600:]))
    return r


F.Engine.bodies, F.measure, F.run_fight = bodies, measure, run_fight


def compare(m, fight, rows, setup, catalog, cues):
    t0 = rows[0][0]
    pairs = F.initial_pairs(rows, setup, catalog)
    inv = {s: l for l, s in pairs.items() if s}
    setup_ids = {b['id'] for b in setup}
    T = LC.CUES                                         # live cue index of this log (set by main)
    out, prev = [], {}
    for tick, live, simb in rows:
        sc = cues.get(tick)
        if sc is None:
            continue
        su = {}
        for u in sc['units']:
            sid = tower_id(u['team'], u['x']) if u['kind'] in ('princess_tower', 'king_tower') else f"s{u['uid']}"
            su[sid] = u
        uid2id = {u['uid']: sid for sid, u in su.items()}
        gen2id = {b['gen']: b['id'] for b in live if 'gen' in b}
        cue = T.get(tick)
        LB = {b['id']: b for b in live}
        lv = {}
        for b in live:
            if 'gen' not in b:
                continue
            sid = pairs.get(b['id']) or (b['id'] if b['tower'] else None)
            lv[b['id']] = LC.live_cue(b, prev.get(b['id']), tick, cue, gen2id, catalog, su.get(sid))
            tb = LB.get(lv[b['id']]['tg'])
            lv[b['id']]['td'] = round(((b['x'] - tb['x']) ** 2 + (b['y'] - tb['y']) ** 2) ** .5) if tb else None
        for b in live:
            sid = pairs.get(b['id']) or (b['id'] if b['tower'] else None)
            if sid not in su or b['id'] not in lv:
                continue
            u = su[sid]
            sm = LC.sim_cue(u, uid2id, inv)
            tu = su.get(uid2id.get(u['attack']['target']))
            sm['td'] = round(((u['x'] - tu['x']) ** 2 + (u['y'] - tu['y']) ** 2) ** .5 * 1000) if tu else None
            dist = ((b['x'] - u['x'] * 1000) ** 2 + (b['y'] - u['y'] * 1000) ** 2) ** .5
            out.append(dict(k='b', f=fight['t0'], dt=tick - t0, id=b['id'], name=u['name'], side=b['side'],
                            tw=b['tower'], setup=b['id'] in setup_ids, dist=round(dist), lv=lv[b['id']], sm=sm))
        # projectiles / areas, in the live id space
        lp = [dict(src=p[7], tgt=p[8], x=p[1], y=p[2], side=p[0], card=p[3], cn=(catalog.get(p[3]) or {}).get('display_name'),
                   ct=(catalog.get(p[3]) or {}).get('type')) for p in (m['proj'].get(tick) or [])]
        sp = [dict(src=uid2id.get(p['source']), tgt=uid2id.get(p['target']), x=p['x'] * 1000, y=p['y'] * 1000,
                   aim=(p['aim_x'] * 1000, p['aim_y'] * 1000), side=p['team'], type=p['type'], fx=p['effect'])
              for p in sc['projectiles']]
        sp = [dict(q, src=inv.get(q['src'], q['src']) if q['src'] else None,
                   tgt=inv.get(q['tgt'], q['tgt']) if q['tgt'] else None) for q in sp]
        out.append(dict(k='p', f=fight['t0'], dt=tick - t0, live=lp, sim=sp))
        la = [dict(name=(catalog.get(a[3]) or {}).get('display_name', a[3]), rem=a[4], x=a[1], y=a[2], side=a[0])
              for a in (m['fx'].get(tick) or [])]
        sa = [dict(name=a['name'], rem=a['remaining_ms'], frac=a['frac'], x=a['x'] * 1000, y=a['y'] * 1000,
                   side=a['team'], motion=a['motion']) for a in sc['areas']]
        out.append(dict(k='a', f=fight['t0'], dt=tick - t0, live=la, sim=sa))
        prev = {b['id']: (tick, b) for b in live}
    return out


def main():
    stem = sys.argv[1]
    if '--max-fights' in sys.argv:
        os.environ['PARITY_MAX_FIGHTS'] = sys.argv[sys.argv.index('--max-fights') + 1]
    out_dir = Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else HERE / 'out'
    out_dir.mkdir(parents=True, exist_ok=True)
    print('cues', LC.load(stem))
    tmp = out_dir / ('fights_' + stem)
    (tmp / 'matches').mkdir(parents=True, exist_ok=True)
    path = ROOT / 'scratchpad/gauntlet/L68/live_reader' / (stem + '.jsonl')
    summ = F.run_match(str(path), 240, str(tmp), 0)
    print(summ.get('match'), 'fights', summ.get('fights'), 'errors', summ.get('errors'), 'skipped', summ.get('skipped'),
          'rows', len(OUT))
    with gzip.open(out_dir / (stem + '.jsonl.gz'), 'wt') as h:
        for r in OUT:
            h.write(json.dumps(r, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
