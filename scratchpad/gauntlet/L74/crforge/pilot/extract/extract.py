"""crforge Stage 1 extractor (ticket A2b-1): our live log + the official battle log -> crforge battle inputs.

    python -I extract.py match    --live LIVE.jsonl                    # one match -> JSON on stdout
    python -I extract.py validate --live LIVE.jsonl --rec REC.jsonl    # extracted plays vs a replay recording's plays
    python -I extract.py batch    --out OUT.jsonl [--since 20261019_0600]

Per match (the ScenarioPlan fields crforge ReplayBattle.build reads, plus what the J7 driver needs):
  decks       both sides, crforge row names in deck-slot order (API order = slot order: CRFORGE_S0 2c, 8/8 both sides)
  levels      per card, counted 1..16 across rarities = API level + 16 - maxLevel (exact, from the battle log)
  slot_flags  bit 0 evolution slot, bit 1 hero slot = API evolutionLevel 1 / 2
  towers      spawn group (API support card) + king / princess level, cross-checked against the live tick-0 max hp
              (crforge tower table: towers.tsv, LagProbe towers)
  words       low word of each account id (gen_jobs.word, the community tag decoding: b)
  deal        ours exact (gen_jobs.own_order, decision own_hand deck_index); the opponent's is not public live: null
  plays       both sides, from parity/fights.deployments (reused unedited): card, deck index, form, x / y in game units
              (= live millitiles, side 0 low y), tile, run_ticks [lo, hi] = the crforge run-tick candidates. crforge makes
              a play's first object 1 tick after its run tick (LagProbe: 13 / 13 cards, lag 1), which is the parity
              convention deployments already dates by (tick = creation - 1), so the frame gap's two ticks are the two
              candidates; a phase-3b capture dates a body's play exactly (lo = hi).
  rng_free    no deck holds Arrows / Princess / Hunter / SkeletonKing (crforge/live_attr.py rule, G0)
Never read: the opponent's hand or elixir (live logs carry an elixir estimate; it is not opened here).
"""
import argparse, collections, datetime as dt, itertools, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scratchpad/gauntlet/L74/seeds'))
from gen_jobs import id_names, own_order, word, BATTLELOG, LIVE  # noqa: E402
from scratchpad.gauntlet.L74.parity import fights  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402

TABLES = Path(r'C:\Users\benpe\crforge_eval\cache\tables\16.402.22')
DRAWERS = {'Arrows', 'Princess', 'Hunter', 'SkeletonKing'}      # G0: the only Ladder cards that draw after the deal
OWN_PRINCESS = 4858                                             # main account, level-16 towers
GROUPS = {'Tower Princess': 'King_PrincessTowers', 'Cannoneer': 'King_CannonTowers',
          'Dagger Duchess': 'King_KnifeTowers', 'Royal Chef': 'King_ChefTowers'}


def tower_table():
    """(group, level) -> (king hp, princess hp) from towers.tsv (crforge, LagProbe towers)."""
    out = {}
    for line in open(HERE / 'towers.tsv'):
        g, lv, *xs = line.split()
        hp = {int(x.split(':')[0]): int(x.split(':')[1]) for x in xs}
        out[g, int(lv)] = (hp[9000], hp[3500])
    return out


def table_shims(tables):
    """The three facts deployments takes from the RoyaleSim Engine, read from the crforge tables instead (no SIM on the
    laptop): area-effect life (ms) by spell, collision radius by unit, and own_unit (below, per match)."""
    rows = {}
    for f in ('spells_other', 'spells_characters', 'spells_buildings', 'characters', 'buildings', 'area_effect_objects'):
        rows[f] = json.load(open(Path(tables) / f'{f}.json'))['rows']
    def life(name):
        ae = (rows['spells_other'].get(name) or {}).get('columns', {}).get('AreaEffectObject')
        return (rows['area_effect_objects'].get(ae) or {}).get('columns', {}).get('LifeDuration') if ae else None
    def stats(name):
        r = rows['characters'].get(name) or rows['buildings'].get(name) or {}
        return {'collision_radius_milli': r.get('columns', {}).get('CollisionRadius')}
    return life, stats


def battles():
    """Ranked battle-log entries, de-duplicated, newest last."""
    seen, out = set(), []
    for line in open(BATTLELOG):
        b = json.loads(line)['battle']
        k = (b['battleTime'], b['opponent'][0]['tag'])
        if b['type'] == 'pathOfLegend' and k not in seen:
            seen.add(k); out.append(b)
    return sorted(out, key=lambda b: b['battleTime'])


def log_start(p):
    m = re.match(r'live_play_(\d{8}_\d{6})', p.name)
    return dt.datetime.strptime(m.group(1), '%Y%m%d_%H%M%S') + dt.timedelta(hours=4) if m else None  # EDT -> UTC


def battle_for(path, bl):
    """The battle-log entry this live log played: battle end 60..600 s after the log's start (gen_jobs rule), nearest."""
    t0 = log_start(Path(path))
    c = [((dt.datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S') - t0).total_seconds(), b) for b in bl]
    c = [(s, b) for s, b in c if 60 <= s <= 600]
    return min(c, key=lambda x: x[0]) if c else (None, None)


def side_info(p, names, cat, tt, live_k, live_p):
    cards = p['cards']
    deck = [names.get(c['id'], '?' + c['name']) for c in cards]
    sup = (p.get('supportCards') or [{}])[0]
    group = GROUPS.get(sup.get('name'))
    lv = sup.get('level', 0) + 16 - sup.get('maxLevel', 16) if sup else None
    king = next((L for (g, L), (k, _) in tt.items() if g == group and k == live_k), None)
    flags = []
    if group is None:
        flags.append(f'tower_troop_unknown:{sup.get("name")}')
    elif tt.get((group, lv), (None, None))[1] != live_p:
        flags.append(f'princess_hp_mismatch:api_L{lv}_live{live_p}')
    if king is None:
        flags.append(f'king_hp_unmatched:{live_k}')
    return dict(deck=deck, api_ids=[c['id'] for c in cards],
                display=[(cat.get(c['id']) or {}).get('display_name') for c in cards],
                levels=[c['level'] + 16 - c['maxLevel'] for c in cards],
                slot_flags=[{1: 1, 2: 2}.get(c.get('evolutionLevel') or 0, 0) for c in cards],
                towers=dict(group=group, king_level=king, level=lv, king_hp=live_k, princess_hp=live_p),
                word=word(p['tag']), flags=flags)


def cycle_fail(deal, seq):
    """Index of the first play of `seq` (deck indices, in play order) not in hand under the 4-card cycle dealt `deal`,
    or None if every play is legal. A played card goes to the back of the queue; the queue's front enters the hand."""
    hand, queue = list(deal[:4]), list(deal[4:])
    for i, k in enumerate(seq):
        if k not in hand:
            return i
        hand.remove(k); hand.append(queue.pop(0)); queue.append(k)
    return None


def deals_fitting(seq):
    """(how many of the 8! deals make every play legal, one of them: first-play order when it fits). Public plays only."""
    first = list(dict.fromkeys(seq)); first += [k for k in range(8) if k not in first]
    n = sum(cycle_fail(d, seq) is None for d in itertools.permutations(range(8)))
    ex = first if cycle_fail(first, seq) is None else next((list(d) for d in itertools.permutations(range(8))
                                                             if cycle_fail(d, seq) is None), None)
    return n, ex


def match(path, bl=None, names=None, cat=None, shims=None, tt=None):
    """-> (record, None) or (None, skip reason)."""
    path = Path(path)
    bl = bl if bl is not None else battles()
    gap, b = battle_for(path, bl)
    if b is None:
        return None, 'no_battle_log_entry'
    m, why = fights.read_match(path)
    if m is None:
        return None, why
    my = m['side']
    t0 = m['frames'][0][1]
    hp = {(bd['side'], bd['id'][-1] == 'K'): bd['max_hp'] for bd in t0 if bd['tower']}
    if hp.get((my, False)) != OWN_PRINCESS:
        return None, f'not_main_account:{hp.get((my, False))}'
    end = next((json.loads(r) for r in open(path, 'rb') if b'"end"' in r[:20]), {})
    crowns = ((end.get('towers') or {}).get('crowns_me'), (end.get('towers') or {}).get('crowns_opp'))
    api = (b['team'][0]['crowns'], b['opponent'][0]['crowns'])
    names = names or id_names(TABLES)
    cat = cat or load_catalog()[0]
    tt = tt or tower_table()
    life, stats = shims or table_shims(TABLES)
    sides = {my: side_info(b['team'][0], names, cat, tt, hp.get((my, True)), hp.get((my, False))),
             1 - my: side_info(b['opponent'][0], names, cat, tt, hp.get((1 - my, True)), hp.get((1 - my, False)))}
    sides[my]['role'], sides[1 - my]['role'] = 'us', 'opp'
    flags = [f'{s}:{f}' for s in sides for f in sides[s].pop('flags')]
    if any(len(sides[s]['deck']) != 8 for s in sides):
        return None, 'deck_size'
    if None not in crowns and crowns != api:
        flags.append(f'crowns_mismatch:live{crowns}_api{api}')
    # Plays the log began after (the reader starts at ~tick 150): a tick-0 frame holding only the towers makes the
    # first frame's bodies new, so deployments keeps them with the gap [0, first frame - 1] (flag pre_log).
    m['frames'] = [(0, [bd for bd in t0 if bd['tower']])] + m['frames']
    m['births'] = fights.phase3_births(path) if m['ext'] else {}
    first = {}
    for t, bodies in m['frames']:
        for bd in bodies:
            if not bd['tower']:
                first.setdefault(bd['id'], (bd['side'], bd['card_id'], bd['max_hp']))
    top = collections.Counter()                # own_unit shim: the largest max hp a body of the card is first seen with
    for s, cid, mx in first.values():
        c = cat.get(cid)
        if c and fights.form_of(cid, c) != 1:
            top[c['display_name']] = max(top[c['display_name']], mx)
    # ponytail: own_unit = "within the card's largest body size" (the SIM's per-level hp table is not on the laptop). It
    # gates H-NEARPARENT second plays (kept) and the Hero-Goblins exemption (lost: their goblins read as children of the
    # 3720-hp ability object; 4 opponent Hero Goblins decks in the battle log). Exact via crforge unit hp if it matters.
    # A looser "any first-seen hp" shim made the Hero IW's ice cube a play (10-26 validation: 1 extra own play).
    events, delay = fights.deployments(m, cat, life, own_unit=lambda n, h: h >= .45 * top.get(n, 0) > 0, stats=stats)
    plays, unplaced = [], []
    idx = {s: {d: k for k, d in enumerate(sides[s]['display'])} for s in sides}
    for e in events:
        k = idx[e['side']].get(e['name'])
        row = dict(side=e['side'], kind=e['kind'], card=None if k is None else sides[e['side']]['deck'][k], deck_index=k,
                   name=e['name'], form=e.get('form', 0), run_ticks=[e.get('lo', e['tick']), e.get('hi', e['tick'])],
                   tick=e['tick'], source=e['source'])
        if e['kind'] != 'ability':
            row.update(x=e['x'], y=e['y'], tile=[int(e['x']) // 1000, int(e['y']) // 1000], n=e.get('n'))
        if row['run_ticks'][0] == 0:
            row['pre_log'] = True
        if e.get('inferred'):
            row['inferred'] = True
        (plays if k is not None else unplaced).append(row)
    build = next((json.loads(r).get('phase2', {}).get('build') for r in open(path, 'rb') if b'"phase2"' in r), None)
    drawers = sorted(DRAWERS & (set(sides[0]['deck']) | set(sides[1]['deck'])))
    order = own_order(path)
    seq = {s: [p['deck_index'] for p in sorted(plays, key=lambda p: p['tick']) if p['side'] == s and p['kind'] == 'play']
           for s in (0, 1)}
    own_fail = cycle_fail(order, seq[my]) if order else 'no_deal'
    if own_fail is not None:
        flags.append(f'{my}:own_cycle_fail:{own_fail}')
    n_opp, opp_fit = deals_fitting(seq[1 - my])
    if not n_opp:
        flags.append(f'{1 - my}:opp_no_fitting_deal:0')
    return dict(own_cycle_fail=own_fail, opp_fitting_deals=n_opp, opp_deal_fit=opp_fit,match=path.stem, battle_time=b['battleTime'], gap_s=gap, my_side=my, game_build=build,
                era='post_1019' if path.stem[10:23] >= fights.TABLE_1019_FROM else 'pre_1019', tables=TABLES.name,
                ext=m['ext'], phase3_births=bool(m['births']), first_frame_tick=m['frames'][1][0], own_delay=delay,
                sides={str(s): sides[s] for s in (0, 1)},
                deal={str(my): order, str(1 - my): None}, opp_deal='unknown_live' , rng_free=not drawers,
                drawers=drawers, crowns_api=api, plays=plays, unplaced=unplaced, flags=flags,
                own_taps=[dict(tick=p['tick'], name=p['name'], x=p['x'], y=p['y']) for p in m['plays']]), None


def validate(live, rec):
    """Extracted plays vs the replay recording's hand-change plays (replay_rec/convert.hand_plays)."""
    sys.path.insert(0, str(ROOT / 'scratchpad/gauntlet/L74/replay_rec'))
    import convert
    r, why = match(live)
    if r is None:
        raise SystemExit(why)
    _, frames = convert.battle_frames(Path(rec))
    truth = convert.hand_plays(frames)
    cyc = convert.cycle_check(frames, truth)
    p0 = {int(p['side']): p for p in frames[0]['players']}
    out = dict(match=r['match'], truth_plays=len(truth), truth_cycle_bad_frames=cyc, extracted=len(r['plays']),
               unplaced=len(r['unplaced']), first_frame_tick=r['first_frame_tick'])
    # inputs vs the recording's tick-0 state
    out['deck_ok'] = {s: r['sides'][str(s)]['api_ids'] == p0[s]['deck_card_ids'] for s in (0, 1)}
    out['slot_flags_ok'] = {s: r['sides'][str(s)]['slot_flags'] == p0[s]['deck_form_flags'] for s in (0, 1)}
    my = r['my_side']
    out['own_deal_ok'] = r['deal'][str(my)] == p0[my]['hand_deck_indices'] + p0[my]['cycle_deck_indices']
    opp = 1 - my
    seq = [p['deck_index'] for p in sorted(r['plays'], key=lambda p: p['tick']) if p['side'] == opp and p['kind'] == 'play']
    out['opp_true_deal_fits'] = cycle_fail(p0[opp]['hand_deck_indices'] + p0[opp]['cycle_deck_indices'], seq) is None
    out['opp_fitting_deals'] = r['opp_fitting_deals']
    # per-card levels vs the recording's body levels (every non-tower body; card matched by display name)
    cat = load_catalog()[0]
    lv, bad = collections.Counter(), collections.Counter()
    for f in frames:
        for e in f['entities']:
            c = cat.get(e.get('card_id', -1))
            disp = r['sides'][str(e['side'])]['display']
            if c is None or c['display_name'] not in disp or not e.get('level'):
                continue
            ok = r['sides'][str(e['side'])]['levels'][disp.index(c['display_name'])] == e['level']
            (lv if ok else bad)[e['side'], c['display_name']] += 1
    out['levels_ok_cards'] = len(set(lv) - set(bad)); out['levels_bad_cards'] = sorted(map(str, bad))
    # plays: pair each truth play with an unused extracted play of the same side and deck index, nearest tick (<= 60)
    ext = [p for p in r['plays'] if p['kind'] == 'play']
    used, rows = set(), []
    for t in truth:
        c = [(abs(p['tick'] - t['tick']), i) for i, p in enumerate(ext)
             if i not in used and p['side'] == t['side'] and p['deck_index'] == t['deck_index'] and abs(p['tick'] - t['tick']) <= 60]
        if not c:
            rows.append(dict(side=t['side'], card=t['card'], tick=t['tick'], match=None)); continue
        i = min(c)[1]; used.add(i); p = ext[i]
        d = dict(side=t['side'], card=t['card'], tick=t['tick'], match=i, src=p['source'], lo=p['run_ticks'][0],
                 hi=p['run_ticks'][1], dlo=p['run_ticks'][0] - t['tick'], dhi=p['run_ticks'][1] - t['tick'],
                 pre_log=p.get('pre_log', False),
                 # the replay shows the hand change on the play's first-object tick (run + 1, as phase-3 stamped plays
                 # show), so with the change first sampled on frame H after frame Hprev the true run tick is in
                 # [Hprev, H - 1] (2 ticks on a 2-tick sample)
                 window_ok=max(p['run_ticks'][0], int(frames[t['frame'] - 1]['game_tick'])) <= min(p['run_ticks'][1], t['tick'] - 1))
        if t['side'] == my:          # our own command point: the confirmed tap (exact intent; the game may snap it)
            tap = [q for q in r['own_taps'] if q['name'] == p['name'] and 0 <= p['tick'] - q['tick'] <= 100]
            if tap:
                d['tap_dxy'] = [round(p['x'] - tap[-1]['x']), round(p['y'] - tap[-1]['y'])]
        if t['x'] is not None:
            d.update(dxy=[round(p['x'] - t['x']), round(p['y'] - t['y'])],
                     tile_ok=p['tile'] == [int(t['x']) // 1000, int(t['y']) // 1000])
        rows.append(d)
    extra = [dict(side=p['side'], card=p['card'], tick=p['tick'], src=p['source']) for i, p in enumerate(ext) if i not in used]
    out['rows'], out['extra'] = rows, extra
    for s in (0, 1):
        R = [x for x in rows if x['side'] == s]
        hit = [x for x in R if x['match'] is not None]
        role = 'us' if s == my else 'opp'
        out[role] = dict(truth=len(R), matched=len(hit), extra=sum(e['side'] == s for e in extra),
                         d_run_lo=dict(collections.Counter(x['dlo'] for x in hit)),
                         d_run_hi=dict(collections.Counter(x['dhi'] for x in hit)),
                         tile_ok=sum(bool(x.get('tile_ok')) for x in hit), located=sum('dxy' in x for x in hit),
                         max_dxy=max((max(map(abs, x['dxy'])) for x in hit if 'dxy' in x), default=None),
                         window_ok=sum(x['window_ok'] for x in hit), exact_tick=sum(x['lo'] == x['hi'] for x in hit),
                         tap_checked=sum('tap_dxy' in x for x in hit),
                         tap_exact=sum(x.get('tap_dxy') == [0, 0] for x in hit),
                         tap_max=max((max(map(abs, x['tap_dxy'])) for x in hit if 'tap_dxy' in x), default=None))
    out['abilities_extracted'] = [(p['side'], p['name'], p['run_ticks']) for p in r['plays'] if p['kind'] == 'ability']
    return out


def batch(out, since):
    bl = battles()
    names, cat, shims, tt = id_names(TABLES), load_catalog()[0], table_shims(TABLES), tower_table()
    """Per Ranked battle at or after `since` (EDT stamp): the live log that played it (battle_for, the gen_jobs rule),
    extracted. Writes every extracted match; counts skips by reason."""
    stats, rows, skips = collections.Counter(), [], []
    logs = [p for p in LIVE.glob('live_play_2026*.jsonl') if re.match(r'live_play_\d{8}_\d{6}\.jsonl$', p.name)]
    cut = dt.datetime.strptime(since, '%Y%m%d_%H%M') + dt.timedelta(hours=4)        # EDT -> UTC
    for b in bl:
        end = dt.datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S')
        if end < cut:
            continue
        stats['ranked_battles'] += 1
        c = [((end - log_start(p)).total_seconds(), p) for p in logs]
        c = [x for x in c if 60 <= x[0] <= 600]
        if not c:
            stats['no_live_log'] += 1; skips.append((b['battleTime'], 'no_live_log')); continue
        p = min(c, key=lambda x: x[0])[1]
        try:
            r, why = match(p, [b], names, cat, shims, tt)
        except Exception as e:      # one bad log must not stop the batch; counted and named
            r, why = None, f'error:{type(e).__name__}:{e}'[:160]
        if r is None:
            stats[why.split(':')[0]] += 1; skips.append((b['battleTime'], p.name, why)); continue
        rows.append(r)
    with open(out, 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    free = [r for r in rows if r['rng_free']]
    stats = dict(stats)
    stats.update(main_matches=len(rows), rng_free=len(free),
                 rng_free_no_flags=sum(not r['flags'] for r in free),
                 rng_free_own_deal=sum(bool(r['deal'][str(r['my_side'])]) for r in free),
                 builds=dict(collections.Counter(r['game_build'] for r in rows)),
                 flags=dict(collections.Counter(f.split(':')[0] + ':' + f.split(':')[1] for r in rows for f in r['flags'])))
    stats['skips'] = skips
    return dict(stats)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('match', 'validate', 'batch'))
    ap.add_argument('--live'); ap.add_argument('--rec'); ap.add_argument('--out'); ap.add_argument('--since', default='20261019_0600')
    a = ap.parse_args()
    if a.cmd == 'match':
        r, why = match(a.live)
        print(json.dumps(r if r else dict(skip=why)))
    elif a.cmd == 'validate':
        print(json.dumps(validate(a.live, a.rec), default=str))
    else:
        print(json.dumps(batch(a.out, a.since)))


if __name__ == '__main__':
    main()
