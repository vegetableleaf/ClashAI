"""Cue-feature parity: the 22 floats the LIVE builder (pipeline/live_unit_state.py, the production code) gives each live
body vs the 22 floats the SIM gives the paired SIM body (model_gen.cue_vector over sim_unit_state.extract, hit window
100 ms, the training definition), at the same tick, through fights.py's replays (imported, never edited; the S6
collect.py hooks).

    PARITY_SIM_PATH=<royalesim 0.1.35> PARITY_ATTACKS=.. PARITY_BUFFS=.. python pcollect.py LOG.jsonl OUT_DIR

Writes OUT_DIR/<stem>.jsonl.gz: [dt, setup, dist_mt, name, live22, sim22] per paired non-tower body per frame.
"""
import gzip
import json
import os
import sys
from pathlib import Path

CB = Path(os.environ.get('CB', Path(__file__).resolve().parent / 'cb'))
sys.path.insert(0, str(CB))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, os.environ["PARITY_SIM_PATH"])
import royalesim                                            # noqa: E402,F401  (live_unit_state reads its embedded table)
import scratchpad.gauntlet.L74.parity.fights as F          # noqa: E402
from pipeline import sim_unit_state as U                    # noqa: E402
from pipeline.model_gen import cue_vector                   # noqa: E402
from logframes import frames                                # noqa: E402

CTX = dict(on=False)
OUT = []
LIVE = {}


def live_vectors(path):
    from pipeline.live_unit_state import LiveCues
    c, prev = LiveCues(), None
    for f in frames(path):
        us = c.units(f, prev)
        prev = f
        if us is None:
            LIVE[f['game_tick']] = None
            continue
        ents = {e['category']: e for e in f['entities']}
        p2 = {u['generation']: u for u in f['phase2']['units']}
        p3 = {b['generation']: b for b in f['phase3']['bodies']}
        row = {}
        for u in us:
            if u['tower']:
                continue
            g = u['generation']
            e, att = ents[g], (p3.get(g) or {}).get('attack') or {}
            tg = att.get('target_gen')
            te = ents.get(tg)
            dbg = dict(raw=e['behavior_state_raw'], hp=e['hp'], mhp=e['max_hp'], prog=att.get('progress_raw') or 0,
                       tg=tg is not None, tn=(p2.get(tg) or {}).get('name') if te else None,
                       td=round(((e['x'] - te['x']) ** 2 + (e['y'] - te['y']) ** 2) ** .5) if te else None)
            row[g] = ([round(v, 3) for v in cue_vector(u, u['target_is_tower'])], dbg)
        LIVE[f['game_tick']] = row


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
            compare(fight, CTX['rows'], CTX['setup'], CTX['catalog'], CTX['cues'])
        except Exception as e:                  # one fight must not stop the collection
            OUT.append(['err', fight['t0'], repr(e)])
    return r


F.Engine.bodies, F.measure, F.run_fight = bodies, measure, run_fight


def compare(fight, rows, setup, catalog, cues):
    t0 = rows[0][0]
    pairs = F.initial_pairs(rows, setup, catalog)
    setup_ids = {b['id'] for b in setup}
    for tick, live, simb in rows:
        sc, lv = cues.get(tick), LIVE.get(tick)
        if sc is None or lv is None:
            continue
        towers = {u['uid'] for u in sc['units'] if u['kind'] in ('princess_tower', 'king_tower')}
        su = {f"s{u['uid']}": u for u in sc['units'] if u['uid'] not in towers}
        for b in live:
            if b['tower'] or 'gen' not in b or b['gen'] not in lv:
                continue
            u = su.get(pairs.get(b['id']))
            if u is None:
                continue
            dist = ((b['x'] - u['x'] * 1000) ** 2 + (b['y'] - u['y'] * 1000) ** 2) ** .5
            sv = [round(v, 3) for v in cue_vector(u, u['attack']['target'] in towers)]
            tu = next((x for x in sc['units'] if x['uid'] == u['attack']['target']), None)
            sd = dict(st=u['state'], hp=u['hp'], mhp=u['max_hp'], tn=tu['name'] if tu else None,
                      td=round(((u['x'] - tu['x']) ** 2 + (u['y'] - tu['y']) ** 2) ** .5 * 1000) if tu else None)
            OUT.append([tick - t0, b['id'] in setup_ids, round(dist), u['name'], lv[b['gen']][0], sv, lv[b['gen']][1], sd])


def main():
    path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    live_vectors(path)
    tmp = out_dir / ('fights_' + path.stem)
    (tmp / 'matches').mkdir(parents=True, exist_ok=True)
    summ = F.run_match(str(path), 240, str(tmp), 0)
    print(path.stem, 'fights', summ.get('fights'), 'errors', summ.get('errors'), 'rows', len(OUT), flush=True)
    with gzip.open(out_dir / (path.stem + '.jsonl.gz'), 'wt') as h:
        for r in OUT:
            h.write(json.dumps(r, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
