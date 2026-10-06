"""Bot bad-play audit on top of rows_bot.jsonl / spells_bot.jsonl (+ decision events). CPU only, read-only.
Run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/spawners/bad_plays.py   -> bad_plays.json"""
import json, os, collections, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
LR = os.path.join(ROOT, 'scratchpad/gauntlet/L68/live_reader')


def rd(n):
    return [json.loads(l) for l in open(os.path.join(HERE, n))]


rows_b, rows_p = rd('rows_bot.jsonl'), rd('rows_pros.jsonl')
sp_b, sp_p = rd('spells_bot.jsonl'), rd('spells_pros.jsonl')
rows_p = [r for r in rows_p if r.get('core', 0) >= 7]
TROOP = ('Witch', 'NightWitch', 'Furnace', 'MotherWitch')
out = {}


def m(v):
    return round(statistics.mean(v), 2) if v else None


def md(v):
    return round(statistics.median(v), 2) if v else None


def pc(a, b):
    return round(100 * a / b) if b else None


# 1. elixir at deploy and 8 s later, troop spawners
for nm, R in (('bot', rows_b), ('pros', rows_p)):
    T = [r for r in R if r['fam'] in TROOP]
    out['elixir_' + nm] = dict(n=len(T), at_deploy_med=md([r['my_elixir'] for r in T]), at_deploy_mean=m([r['my_elixir'] for r in T]),
                               after8_med=md([r['my_elixir_8s'] for r in T]),
                               lt4_at_deploy_pct=pc(sum(r['my_elixir'] < 4 for r in T), len(T)),
                               ge6_at_deploy_pct=pc(sum(r['my_elixir'] >= 6 for r in T), len(T)),
                               lt1p5_after8_pct=pc(sum(r['my_elixir_8s'] < 1.5 for r in T), len(T)))
# 2. damage vs elixir at deploy
for nm, R in (('bot', rows_b), ('pros', rows_p)):
    T = [r for r in R if r['fam'] in TROOP and not r['dmg_trunc']]
    lo = [r['dmg_pct_princess'] for r in T if r['my_elixir'] < 4.5]
    hi = [r['dmg_pct_princess'] for r in T if r['my_elixir'] >= 4.5]
    out['dmg_by_elixir_' + nm] = dict(lt4p5=dict(n=len(lo), mean=m(lo)), ge4p5=dict(n=len(hi), mean=m(hi)))
# 3. first-response lane / king-back cycle plays / card
for nm, R in (('bot', rows_b), ('pros', rows_p)):
    T = [r for r in R if r['fam'] in TROOP and r['resp']]
    out['first_resp_' + nm] = dict(n=len(T), opp_lane_pct=pc(sum(r['resp'][0]['where'].startswith('opp') for r in T), len(T)),
                                   king_back_y29p5_pct=pc(sum(r['resp'][0]['y'] >= 29.5 for r in T), len(T)),
                                   on_or_near_pct=pc(sum(r['resp'][0]['where'] in ('ON', 'NEAR') for r in T), len(T)),
                                   xbow_first_pct=pc(sum(r['resp'][0]['card'] == 'Xbow' for r in T), len(T)),
                                   rocket_first_pct=pc(sum(r['resp'][0]['card'] == 'Rocket' for r in T), len(T)))
# 4. how the spawner died
for nm, R in (('bot', rows_b), ('pros', rows_p)):
    A = [r for r in R if r['fam'] in TROOP]
    T = [r for r in A if r['died']]
    out['death_' + nm] = dict(n=len(A), died=len(T), rocket_pct=pc(sum(r['cause'] == 'Rocket' for r in T), len(T)),
                              tower_in_range_pct=pc(sum('Tower' in r['attackers'] for r in T), len(T)),
                              xbow_in_range_pct=pc(sum('Xbow' in r['attackers'] for r in T), len(T)),
                              life_med=md([r['life_s'] for r in A]), gt20_pct=pc(sum(r['life_s'] > 20 for r in A), len(A)))


# 5. spells while a spawner is alive
def spc(S, ctx):
    c = collections.defaultdict(collections.Counter)
    for x in S:
        if x['ctx'] == ctx:
            c[x['card']][x['cls']] += 1
    return {k: dict(v, total=sum(v.values())) for k, v in c.items()}


out['spells_alive_bot'] = spc(sp_b, True)
out['spells_alive_pros'] = spc(sp_p, True)


def logbats(S):
    L = [x for x in S if x['card'] == 'Log']
    bats = [x for x in L if x['hit'] and set(x['hit']) <= {'Bats'}]
    kids = [x for x in L if x['hit'] and set(x['hit']) <= {'child'}]
    none = [x for x in L if not x['hit']]
    return dict(n_log=len(L), bats_only=len(bats), children_only=len(kids), nothing=len(none),
                bats_only_pct=pc(len(bats), len(L)), nothing_pct=pc(len(none), len(L))), bats, kids


out['log_bot'], bb, bk = logbats(sp_b)
out['log_pros'], _, _ = logbats(sp_p)

# 6. Rocket availability while a troop spawner is alive (decision events carry the hand and elixir)
dec_cache = {}


def decisions(src):
    if src not in dec_cache:
        D = []
        for l in open(os.path.join(LR, src)):
            if not l.startswith('{"event": "decision"'):
                continue
            r = json.loads(l)
            pub = r.get('public') or {}
            D.append((r['tick'], pub.get('own_elixir_raw'), [h['name'] for h in pub.get('own_hand', [])],
                      r['decision'].get('name'), r['decision'].get('p_play'), r['decision'].get('play')))
        dec_cache[src] = D
    return dec_cache[src]


avail = []
for r in rows_b:
    if r['fam'] not in TROOP:
        continue
    D = decisions(r['src'])
    W = [d for d in D if r['t0'] <= d[0] <= r['t0'] + 160]
    if not W:
        continue
    rk = [d for d in W if 'Rocket' in d[2] and (d[1] or 0) >= 6]
    avail.append(dict(src=r['src'], t0=r['t0'], fam=r['fam'], rocket_afford=bool(rk), rocket_in_hand=any('Rocket' in d[2] for d in W),
                      rocket_played=any(p['card'] == 'Rocket' for p in r['resp']),
                      max_p_rocket=max([d[4] or 0 for d in W if d[3] == 'Rocket'] or [0]), dmg=r['dmg_pct_princess'], life=r['life_s']))
out['rocket_availability'] = dict(
    n_deploys_with_decisions=len(avail), rocket_in_hand_pct=pc(sum(a['rocket_in_hand'] for a in avail), len(avail)),
    rocket_affordable_pct=pc(sum(a['rocket_afford'] for a in avail), len(avail)),
    rocket_played_pct=pc(sum(a['rocket_played'] for a in avail), len(avail)),
    affordable_not_played_pct=pc(sum(a['rocket_afford'] and not a['rocket_played'] for a in avail), len(avail)),
    median_max_p_play_when_affordable=md([a['max_p_rocket'] for a in avail if a['rocket_afford']]))


# 7. examples
def ex_row(r, extra=None):
    d = dict(file=r['src'], t0=r['t0'], fam=r['fam'], life_s=r['life_s'], my_elixir=r['my_elixir'], dmg=r['dmg_pct_princess'],
             resp=[(p['card'], p['delay'], p['where'], p['x'], p['y']) for p in r['resp']], cause=r['cause'])
    if extra:
        d.update(extra)
    return d


def top(cond, key, k=6):
    return sorted([r for r in rows_b if r['fam'] in TROOP and not r['dmg_trunc'] and cond(r)], key=key)[:k]


E = {}
E['no_same_lane_response_8s'] = [ex_row(r) for r in top(lambda r: r['first_same_lane'] is None, lambda r: -r['dmg_pct_princess'])]
E['xbow_first_at_low_elixir'] = [ex_row(r) for r in top(lambda r: r['resp'] and r['resp'][0]['card'] == 'Xbow' and r['my_elixir'] < 5, lambda r: -r['dmg_pct_princess'])]
E['overcommit_spent8_ge10'] = [ex_row(r, dict(spent8=r['spent8'], elixir_8s=r['my_elixir_8s'])) for r in top(lambda r: r['spent8'] >= 10, lambda r: -r['dmg_pct_princess'])]
E['opp_lane_first_response'] = [ex_row(r) for r in top(lambda r: r['resp'] and r['resp'][0]['where'].startswith('opp'), lambda r: -r['dmg_pct_princess'])]
E['log_on_bats_only'] = [dict(file=x['src'], tick=x['tick'], xy=(x['x'], x['y']), hit=x['hit']) for x in bb[:8]]
E['log_children_only_spawner_alive'] = [dict(file=x['src'], tick=x['tick'], xy=(x['x'], x['y']), hit=x['hit'], fams=x['fams']) for x in bk if x['ctx']][:8]
E['rocket_tornado_children_or_nothing_spawner_alive'] = [
    dict(card=x['card'], file=x['src'], tick=x['tick'], xy=(x['x'], x['y']), cls=x['cls'], hit=x['hit'], fams=x['fams'], d_parent=x['d_nearest_parent'])
    for x in sp_b if x['ctx'] and x['card'] in ('Rocket', 'Tornado') and x['cls'] in ('children only', 'hits nothing')][:10]
E['rocket_affordable_not_played_worst'] = sorted([a for a in avail if a['rocket_afford'] and not a['rocket_played']], key=lambda a: -a['dmg'])[:6]
out['examples'] = E
json.dump(out, open(os.path.join(HERE, 'bad_plays.json'), 'w'), indent=1, default=str)
print(json.dumps({k: v for k, v in out.items() if k != 'examples'}, indent=1))

# merge into results.json so one file carries everything
rp = os.path.join(HERE, 'results.json')
res = json.load(open(rp))
res['bad_plays'] = out
if os.path.exists(os.path.join(HERE, 'rocket_hold.json')):
    res['rocket_hold'] = json.load(open(os.path.join(HERE, 'rocket_hold.json')))
json.dump(res, open(rp, 'w'), indent=1, default=str)
# results.json is shared with the identity-audit agent (its keys: note, live_*, native_*, sim_* ...); keep a private copy of mine
mine = {k: res[k] for k in ('pros', 'bot', 'excess_tower_damage', 'bad_plays', 'rocket_hold') if k in res}
json.dump(mine, open(os.path.join(HERE, 'behaviour_results.json'), 'w'), indent=1, default=str)
