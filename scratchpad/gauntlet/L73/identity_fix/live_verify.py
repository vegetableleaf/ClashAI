"""Live verification (b): fv4 vs fv5 classes on the logged reader frames (L68 live_play_2026100[456]_*.jsonl), through
the real live adapter (live_mem.to_observe -> obs_contract.from_engine). Truth is an independent HP-threshold rule
per family (parents are far heavier than their children at every level 9-16; catalog multipliers), not body_identity.
'5fwd' = the same frame with card_id -1 TROOP rows forwarded (what a one-line live_mem change would deliver; info only).
Usage: python live_verify.py"""
import sys, json, glob, collections
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
from pipeline import vocab
from pipeline.obs_contract import from_engine, load_deck, catalog_card_form
from pipeline.live_mem import to_observe
from pipeline.body_identity import resolve_board

# family engine name -> (parent if max_hp >= T, parent class, allowed child classes)
FAM = {'Witch': (500, 'witch', {'skeletons'}), 'DarkWitch': (500, 'night_witch', {'bats'}),
       'FirespiritHut': (450, 'furnace', {'fire_spirit'}), 'Tombstone': (400, 'tombstone', {'skeletons'}),
       'GoblinHut': (600, 'goblin_hut', {'spear_goblins'}), 'BarbarianHut': (1300, 'barbarian_hut', {'barbarians'}),
       'GoblinDrill': (1000, 'goblin_drill', {'goblins'}), 'GoblinGiant': (1000, 'goblin_giant', {'spear_goblins', 'goblins'}),
       'SkeletonBalloon': (300, 'skeleton_barrel', {'skeletons'}), 'SkeletonKing': (100, 'skeleton_king', {'skeletons'}),
       'Phoenix': (900, 'phoenix', {'phoenix'}), 'WitchMother': (0, 'mother_witch', set()),
       'Graveyard': (10 ** 9, 'graveyard', {'skeletons'})}
DECK = None


def reader_frame(d):
    ents = [dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6], address=e[7]) for e in d['ents']]
    ms = d['my_side']
    return dict(game_tick=d['tick'], entities=ents,
                players=[dict(side=ms, elixir_raw=0, hand_deck_indices=[-1] * 4, next_deck_index=-1)])


def one(path):
    global DECK
    DECK = DECK or load_deck('icebow')
    res = collections.Counter(); hows = collections.Counter(); unm = {4: set(), 5: set()}
    hist = {4: {}, 5: {}, '5fwd': {}}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('{"event": "frame"'):
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            ms = d['my_side']; rf = reader_frame(d)
            obs = to_observe(rf, ms, list(DECK.cards))
            want = collections.defaultdict(list)
            for e in obs['entities']:
                name = str(e['name'])
                if name in FAM and (e['hp'] > 0 or e['max_hp'] <= 0):
                    T, pc, kids = FAM[name]
                    role = 'unreadable' if e['max_hp'] <= 0 else 'parent' if e['max_hp'] >= T else 'child'
                    want[(int(e['side']), int(e['x']), int(e['y']))].append((name, role))
            # cursed hogs / goblins: card_id -1 troop rows the reader logs but to_observe drops
            extra = [dict(side=e['side'], x=e['x'], y=e['y'], name='-1', card_id=-1, hp=e['hp'], max_hp=e['max_hp'],
                          kind=e['kind'], entity_id=e['address']) for e in rf['entities']
                     if e['card_id'] < 0 and e['kind'] in (14, 15) and e['hp'] > 0]
            fwd = dict(obs, entities=obs['entities'] + extra)
            res[('unnamed_troop_rows',)] += len(extra)
            for fv, o in ((4, obs), (5, obs), ('5fwd', fwd)):
                bs = from_engine(o, ms, DECK, unmapped=unm[4 if fv == 4 else 5], feature_version=4 if fv == 4 else 5,
                                 history=hist[fv])
                if fv == '5fwd':
                    n_named = sum(1 for _ in from_engine(obs, ms, DECK, unmapped=set(), feature_version=5).units)
                    for u in bs.units[n_named:]:
                        res[(fv, 'unnamed_mapped', vocab.UNIT_VOCAB[u.cls])] += 1
                    continue
                pool = {k: list(v) for k, v in want.items()}
                for u in bs.units:
                    # invert _engine_xy (mirror for side 1)
                    X, Y = u.x * 18000.0, (1.0 - u.y) * 32000.0
                    if ms == 1:
                        X, Y = 18000.0 - X, 32000.0 - Y
                    side = ms if u.side == 0 else 1 - ms
                    k = next((kk for kk in ((side, round(X) + dx, round(Y) + dy) for dx in (0, -1, 1) for dy in (0, -1, 1))
                              if pool.get(kk)), None)
                    if k is None:
                        continue
                    name, role = pool[k].pop()
                    T, pc, kids = FAM[name]
                    cls = vocab.UNIT_VOCAB[u.cls]
                    res[(fv, name, role, 'seen')] += 1
                    res[(fv, name, role, 'ok')] += (cls == pc) if role in ('parent', 'unreadable') else (cls in kids)
                    res[(fv, name, role, 'as_parent_class')] += cls == pc
                    res[(fv, name, role, 'form0')] += u.form == 0
                    res[(fv, name, role, 'hp_unknown')] += u.hp_frac is None
                for v in pool.values():
                    for name, role in v:
                        res[(fv, name, role, 'dropped')] += 1
            # tie-break usage (stats only): the same bodies through resolve_board
            lf = {}
            for t in obs['episode']['crown_towers']:
                if t['max_hp']:
                    lf.setdefault(int(t['side']), float(t['max_hp']) / (4824.0 if t['type'] == 'king' else 3052.0))
            bodies = [(e['side'], e['name'], e['max_hp'], catalog_card_form(int(e['card_id']))[1], False)
                      for e in obs['entities'] if e['hp'] > 0 or e['max_hp'] <= 0]
            for (s, name, mhp, f, _), ident in zip(bodies, resolve_board(bodies, lf)):
                if name in FAM:
                    hows[(name, ident.reason, ident.how)] += 1
    return ([list(k) + [v] for k, v in res.items()], [list(k) + [v] for k, v in hows.items()],
            {k: sorted(v) for k, v in unm.items()})


if __name__ == '__main__':
    pattern = sys.argv[1] if len(sys.argv) > 1 else 'live_play_2026100[456]_*.jsonl'
    tag = sys.argv[2] if len(sys.argv) > 2 else ''
    logs = sorted(glob.glob('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/' + pattern))
    tot = collections.Counter(); hows = collections.Counter(); unm = {4: set(), 5: set()}
    with ProcessPoolExecutor(6) as ex:
        for r, h, u in ex.map(one, logs):
            for *k, v in r: tot[tuple(k)] += v
            for *k, v in h: hows[tuple(k)] += v
            for k, v in u.items(): unm[int(k)] |= set(v)
    json.dump(dict(logs=len(logs), rows=[list(k) + [v] for k, v in sorted(tot.items(), key=str)],
                   how=[list(k) + [v] for k, v in sorted(hows.items())], unmapped={k: sorted(v) for k, v in unm.items()}),
              open(f'live_verify{tag}.json', 'w'), indent=0)
    print('unnamed troop rows logged (dropped by to_observe):', tot[('unnamed_troop_rows',)])
    print('fv5 with forwarded -1 rows, mapped:', {k[2]: v for k, v in tot.items() if len(k) == 3 and k[0] == '5fwd'})
    print(f'{"name":15s} {"role":10s} | fv4 seen     ok as_par  drop | fv5 seen     ok as_par  form0 hp_unk  drop')
    for name, role in sorted({(k[1], k[2]) for k in tot if len(k) == 4 and k[0] in (4, 5)}):
        r = lambda fv, m: tot[(fv, name, role, m)]
        print(f'{name:15s} {role:10s} | {r(4,"seen"):8d} {r(4,"ok"):6d} {r(4,"as_parent_class"):6d} {r(4,"dropped"):5d} |'
              f' {r(5,"seen"):8d} {r(5,"ok"):6d} {r(5,"as_parent_class"):6d} {r(5,"form0"):6d} {r(5,"hp_unknown"):6d} {r(5,"dropped"):5d}')
    print('parent-class tokens per readable parent body-frame (fv4 -> fv5):')
    for name in sorted(FAM):
        par = tot[(4, name, 'parent', 'seen')]
        if par:
            a = sum(tot[(4, name, r, 'as_parent_class')] for r in ('parent', 'child'))
            b = sum(tot[(5, name, r, 'as_parent_class')] for r in ('parent', 'child'))
            print(f'  {name:15s} {a / par:5.2f} -> {b / par:5.2f}  (readable parent body-frames {par})')
    print('resolve reason/how (body-frames):')
    for k, v in sorted(hows.items()):
        print('  ', k, v)
    print('unmapped', {k: sorted(v) for k, v in unm.items()})
