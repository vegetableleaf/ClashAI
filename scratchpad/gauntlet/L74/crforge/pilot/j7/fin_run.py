"""J7 whole-match open-loop driver for RoyaleSim (fin15 / fin16), ticket A2b-2: the same plans J7Run.java reads.

    PYTHONPATH=<code tree> python fin_run.py --plans DIR --out DIR --tick lo|hi [--workers N] [--limit N]
Engine: fights.Engine (PARITY_SIM_PATH = a dir holding the wheel, or ROYALE_RUNTIME), its card table by match date
(PARITY_TABLE_1019=1 -> the 10-19 table for post-10-19 matches: fin16; unset -> 10-06: fin15).

Build (from tick 0, nothing on the board): Battle.reset with both full decks (display names), per-card levels, forms from
the slot flags (evo 1, hero 2), tower levels and the tower troop of the API spawn group. Each play is issued at its run
tick (lo or hi) exactly as parity/fights.py play() issues one: the card is put in hand slot 0, the side's mana set full,
an evolution slot's evo charge set from the play's observed form, then step([(side, 0, x*18, y*18)], 0). An ability is
step([(side, HAND_SIZE, 0, 0)], 0). Rows: the towers every tick (a row per change), as J7Run.java.
"""
import argparse, json, time
from collections import Counter
from pathlib import Path

IDS = ('T0L', 'T0R', 'T0K', 'T1L', 'T1R', 'T1K')
TROOP = {'King_KnifeTowers': 'DaggerDuchess', 'King_CannonTowers': 'Cannoneer', 'King_ChefTowers': 'ChefTower'}
_E = {}


def engine(stem):
    from scratchpad.gauntlet.L74.parity import fights as F
    t = F.table_for(stem)
    if t not in _E:
        _E[t] = F.Engine(t)
    return _E[t]


def towers(st, eng):
    r = [0] * 6
    fi = eng.F
    cid, team, x_, hp = fi.index('card_id'), fi.index('team'), fi.index('x'), fi.index('hp')
    for row in st['entities']:
        if row[cid] == -1:
            x = row[x_] // 18
            r[3 * row[team] + (2 if abs(x - 9000) < 1000 else 0 if x < 9000 else 1)] = max(0, row[hp])
    awake = [int(bool(p.get('king_active'))) for p in sorted(st['players'], key=lambda p: p['team'])]
    return r + awake


def run(plan, key):
    from scratchpad.gauntlet.L74.parity.mechanics import load_edited
    eng = engine(plan['match'])
    b, sim = eng.b, eng.sim
    refused = Counter()
    missing = [n for s in (0, 1) for n in plan['display'][s] if n not in eng.ids]
    if missing:
        return dict(crash='card_not_in_sim:' + ','.join(missing))
    decks = [[eng.ids[n] for n in plan['display'][s]] for s in (0, 1)]
    forms = [[{1: 1, 2: 2}.get(f, 0) for f in plan['slots'][s]] for s in (0, 1)]
    levels = plan['levels']
    tl = [plan['towers'][s][2] for s in (0, 1)]
    troops = [TROOP.get(plan['towers'][s][0]) for s in (0, 1)]
    if any(troops):
        b.set_tower_troops(*troops)
    try:
        for attempt in range(3):
            f_ = forms if attempt == 0 else [[x if x == 2 else 0 for x in fs] for fs in forms] if attempt == 1 else [[0] * 8, [0] * 8]
            try:
                b.reset(1, decks, 0, 0, None, None, [], forms=f_, levels=levels, tower_levels=tl)
                break
            except ValueError as e:
                refused[f'reset_forms_dropped_{attempt + 1}:' + str(e)[:80]] += 1
        else:
            return dict(crash='reset refused')
    finally:
        if any(troops):
            b.set_tower_troops(None, None)
    # catalogue id -> engine internal id (fights.run_fight's mapping, H-DECKMAP)
    sv = json.loads(b.save()); pub = json.loads(b.state_json())
    internal = {}
    for t in (0, 1):
        pp, sp = pub['players'][t], sv['players'][t]
        mono = dict(zip(sorted(pp['deck']), sorted(sp['hand'] + sp['queue'])))
        mono.update(dict(zip(pp['hand'] + ([pp['next_card']] if pp.get('next_card') is not None else []), sp['hand'] + sp['queue'][:1])))
        internal[t] = mono
    NO_CARD = getattr(sim, 'NO_CARD', None)

    def play(e):
        before = json.loads(b.save()); after = json.loads(json.dumps(before))
        p = after['players'][e['side']]
        if e['kind'] == 'play':
            ic = internal[e['side']][eng.ids[e['display']]]
            rest = [c for c in p['hand'] + p['queue'] if c not in (ic, NO_CARD)]
            p['hand'] = [ic] + rest[:3]; p['queue'] = rest[3:]
            for ev in p.get('evo', []):
                if ev['card'] == ic:
                    ev['plays'] = ev['cycles'] if e['form'] == 1 else 0
        p['mana'] = after['calib']['max_mana'] * after['mana_unit']; p['refill_ms'] = 0
        if after != before:
            load_edited(b, before, after)
        slot = 0 if e['kind'] == 'play' else sim.HAND_SIZE
        r = b.step([(e['side'], slot, round(e['x'] * 18) if 'x' in e else 0, round(e['y'] * 18) if 'y' in e else 0)], 0)[0]
        return sim.DEPLOY_REASONS[r[1]]

    cmds = sorted(plan['cmds'], key=lambda c: c[key])
    rows, prev, i, stop = [], None, 0, 'end'
    n_play = sum(c['kind'] == 'play' for c in cmds); ok = 0
    while True:
        st = json.loads(b.state_json())
        if st.get('game_over'):
            stop = 'over'; break
        tick = st['tick']
        if tick >= 6000:
            break
        while i < len(cmds) and cmds[i][key] <= tick:
            c = cmds[i]; i += 1
            try:
                why = play(c)
            except Exception as e:
                why = 'play_crash:' + type(e).__name__
            if why == 'OK':
                ok += c['kind'] == 'play'
            else:
                refused[('ability:' if c['kind'] != 'play' else '') + why] += 1
        b.step([], 1)
        st = json.loads(b.state_json())
        r = [st['tick']] + towers(st, eng)
        if prev is None or r[1:] != prev[1:]:
            rows.append(r)
        prev = r
    refused['never_run_after_end'] += len(cmds) - i
    return dict(match=plan['match'], engine=eng.stamp, table=eng.b.card_table() if hasattr(eng.b, 'card_table') else None,
                mode='force', tick=key, stop=stop, end=prev[0] if prev else 0, plays_n=n_play, plays_ok=ok,
                refused=dict(refused), rows=rows)


def one(job):
    path, out, key = job
    o = Path(out) / Path(path).name
    if o.exists():
        return o.name, 'skip'
    try:
        r = run(json.loads(Path(path).read_text()), key)
    except Exception as e:
        r = dict(match=Path(path).stem, crash=type(e).__name__ + ':' + str(e)[:300])
    o.write_text(json.dumps(r, default=str))
    return o.name, r.get('crash') or r.get('stop')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plans', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--tick', choices=['lo', 'hi'], default='lo')
    ap.add_argument('--workers', type=int, default=1); ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    names = [n.strip() for n in open(Path(a.plans) / 'index.txt') if n.strip()]
    if a.limit:
        names = names[:a.limit]
    jobs = [(str(Path(a.plans) / (n + '.json')), a.out, a.tick) for n in names]
    t = time.monotonic()
    if a.workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(a.workers) as ex:
            for k, (n, s) in enumerate(ex.map(one, jobs), 1):
                print(k, n, s, f'{time.monotonic() - t:.0f}s', flush=True)
    else:
        for k, j in enumerate(jobs, 1):
            n, s = one(j)
            print(k, n, s, f'{time.monotonic() - t:.0f}s', flush=True)


if __name__ == '__main__':
    main()
