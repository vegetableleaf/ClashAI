"""Pros-vs-bot response to opponent spawners. CPU only, read-only on inputs.

Run from repo root:
  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/spawners/spawner_behaviour.py [--pros] [--bot]
Writes results.json, rows_pros.jsonl, rows_bot.jsonl, tables.md next to this file.

Both sides are reduced to the same shape: a timeline of (tick, my_elixir, bodies) with bodies
(side, x_milli, y_milli, name, hp, maxhp, uid), my plays (tick, card, x_tile, y_tile in the
CANONICAL frame: my home at y>16, forward = decreasing y), and then ONE analyzer runs on both.
"""
import glob, json, os, sys, bisect, statistics, collections, math
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, ROOT)

FAM = {'Witch': 'Witch', 'DarkWitch': 'NightWitch', 'FirespiritHut': 'Furnace', 'WitchMother': 'MotherWitch',
       'Tombstone': 'Tombstone', 'GoblinHut': 'GoblinHut', 'BarbarianHut': 'BarbarianHut', 'Graveyard': 'Graveyard'}
# what each spawner emits (for "spell on children, not on the spawner")
CHILD = {'Witch': {'Skeletons'}, 'NightWitch': {'Bats'}, 'Furnace': {'FireSpirits'}, 'MotherWitch': {'RoyalHogs', 'Hog'},
         'Tombstone': {'Skeletons'}, 'GoblinHut': {'SpearGoblins'}, 'BarbarianHut': {'Barbarians'}, 'Graveyard': {'Skeletons'}}
FAMS = list(dict.fromkeys(FAM.values()))
TPS = 20
WIN = 160          # 8 s response window
DMG = 300          # 15 s tower damage window
CORE = {'Xbow', 'Tesla', 'Tornado', 'IceWizard', 'Rocket', 'Skeletons', 'Knight', 'Log'}
BOT_LAG = 20   # decision tick -> body on the board is ~26 ticks for my own plays; pros bodies show within ~5 ticks
BUILDINGS = {'Tombstone', 'GoblinHut', 'BarbarianHut'}   # the Furnace WALKS in this build (drifted 18 tiles), so hp-only
PARENT_MIN = {'Witch': 400, 'NightWitch': 400, 'Furnace': 400, 'MotherWitch': 250, 'Tombstone': 250, 'GoblinHut': 500, 'BarbarianHut': 400}
RANGE = {'Xbow': 11.5, 'Tesla': 5.5, 'IceWizard': 5.5, 'Knight': 1.8, 'Skeletons': 1.5}
COST = {'Xbow': 6, 'Log': 2, 'Tesla': 4, 'Knight': 3, 'Skeletons': 1, 'Tornado': 3, 'IceWizard': 3, 'Rocket': 6}
OUR = {'x-bow': 'Xbow', 'the-log': 'Log', 'tesla': 'Tesla', 'knight': 'Knight', 'skeletons': 'Skeletons',
       'tornado': 'Tornado', 'ice-wizard': 'IceWizard', 'rocket': 'Rocket'}


def canon(x, y, my_side):
    """raw milli-tiles -> canonical tiles (my home at y>16)."""
    return (x / 1000.0, y / 1000.0) if my_side == 1 else (18 - x / 1000.0, 32 - y / 1000.0)


def place_cat(px, py, sx, sy):
    d = math.hypot(px - sx, py - sy)
    if d <= 3.0:
        return 'ON'
    same = (px < 9) == (sx < 9)
    depth = 'enemy-half' if py < 14.5 else ('bridge' if py <= 19 else 'own-back')
    if same and d <= 6.0:
        return 'NEAR'
    return ('same-lane ' if same else 'opp-lane ') + depth


def analyze(timeline, my_side, plays, meta, enemy_plays_ticks=None):
    """timeline: list of (tick, my_elixir, bodies); plays: list of dict(tick,card,x,y) mine. Returns rows."""
    if not timeline:
        return [], {}
    opp = 1 - my_side
    end_tick = timeline[-1][0]
    ticks = [t[0] for t in timeline]
    tracks = {}      # key -> dict
    open_key = {}
    towers_hp = []   # per frame: (tick, [(hp,mhp,x) of my towers])
    simul = collections.defaultdict(int)   # family -> max simultaneous bodies on one frame
    for tick, elx, bodies in timeline:
        cnt = collections.Counter()
        mt = []
        for (side, x, y, name, hp, mhp, uid) in bodies:
            if name == 'TOWER':
                if side == my_side:
                    mt.append((hp, mhp, x))
                continue
            if side == opp and name in FAM:
                fam = FAM[name]
                cnt[fam] += 1
                k = (uid, name)
                tr = tracks.get(open_key.get(k))
                if tr is None or tick - tr['last'] > 60:
                    tr = dict(uid=uid, fam=fam, name=name, first=tick, first_pos=(x, y), first_hp=hp, mhp=mhp, last=tick,
                              last_pos=(x, y), last_hp=hp, hist=[])
                    tracks[(k, tick)] = tr
                    open_key[k] = (k, tick)
                tr['last'] = tick; tr['last_pos'] = (x, y); tr['last_hp'] = hp; tr['mhp'] = max(tr['mhp'], mhp)
        for f, c in cnt.items():
            simul[f] = max(simul[f], c)
        towers_hp.append((tick, mt))
    th_ticks = [t for t, _ in towers_hp]
    tw = {}   # tower x -> (ticks, running-min hp, maxhp); absent for >100 ticks before the end = destroyed
    for tk, mt in towers_hp:
        for hp, m, x in mt:
            T = tw.setdefault(round(x), ([], [], m))
            T[0].append(tk); T[1].append(min(hp, T[1][-1]) if T[1] else hp)

    def hp_at(x, T):
        tk, hs, m = tw[x]
        i = bisect.bisect_right(tk, T) - 1
        if i < 0:
            return m
        if T > tk[-1] + 100 and tk[-1] < end_tick - 100:
            return 0
        return hs[i]

    def tower_sum(tick, after=True):
        i = bisect.bisect_left(th_ticks, tick) if after else max(0, bisect.bisect_right(th_ticks, tick) - 1)
        i = min(i, len(towers_hp) - 1)
        return towers_hp[i]

    # Spawn children carry the PARENT card id/name (a Witch's skeletons are listed as 'Witch', maxhp ~81).
    # Parent = body with maxhp >= PARENT_HP; Graveyard has no parent body, so its children are merged into one deploy.
    allt = sorted(tracks.values(), key=lambda r: r['first'])
    Hmax = {}
    for t in allt:
        Hmax[t['name']] = max(Hmax.get(t['name'], 0), t['mhp'])

    def is_parent(t):
        if t['fam'] in BUILDINGS and math.hypot(t['last_pos'][0] - t['first_pos'][0], t['last_pos'][1] - t['first_pos'][1]) > 800:
            return False
        if t['fam'] in BUILDINGS and (t['last'] - t['first'] < 40 or (t['mhp'] > 0 and t['mhp'] < 0.8 * Hmax[t['name']])):
            return False           # a hut's children (Barbarians/Spear Goblins...) walk away; the hut never moves
        if t['mhp'] <= 0:          # hp unreadable (-1): buildings; children always report real hp
            return True
        return t['mhp'] >= PARENT_MIN[t['fam']] and t['mhp'] >= 0.6 * Hmax[t['name']]
    n_child_tracks = collections.Counter(t['fam'] for t in allt if t['fam'] != 'Graveyard' and not is_parent(t))
    parents = [t for t in allt if t['fam'] != 'Graveyard' and is_parent(t)]
    gy = [t for t in allt if t['fam'] == 'Graveyard']
    cl = []
    for t in gy:
        if cl and t['first'] - cl[-1]['first'] <= 240:
            c = cl[-1]
            c['last'] = max(c['last'], t['last']); c['last_hp'] = t['last_hp'] if t['last'] >= c['last'] else c['last_hp']
            c['last_pos'] = t['last_pos'] if t['last'] >= c['last'] else c['last_pos']
            c['n_kids'] += 1
        else:
            t = dict(t); t['n_kids'] = 1; cl.append(t)
    for c in cl:
        c['last_hp'] = 0  # a graveyard 'dies' when its last skeleton does; hp fraction not meaningful
    tracks_use = parents + cl
    pcount = {}
    for f in FAMS:
        ev = sorted([(t['first'], 1) for t in tracks_use if t['fam'] == f] + [(t['last'] + 1, -1) for t in tracks_use if t['fam'] == f])
        cur = mx = 0
        for _, dv in ev:
            cur += dv; mx = max(mx, cur)
        pcount[f] = mx
    simul_parent = pcount
    rows = []
    # frames by tick for attacker lookup
    bt = {t[0]: t[2] for t in timeline}
    by_tick_sorted = ticks
    plays = sorted(plays, key=lambda p: p['tick'])
    p_ticks = [p['tick'] for p in plays]
    for tr in sorted(tracks_use, key=lambda r: r['first']):
        t0 = tr['t0'] = tr.get('t0', tr['first'] - (meta.get('appear_lag', 25)))
        if enemy_plays_ticks:
            # snap to the logged play tick when it exists (pros)
            cands = [e for e in enemy_plays_ticks if e[1] == tr['fam'] and tr['first'] - 70 <= e[0] <= tr['first']]
            if cands:
                t0 = max(cands)[0]
        sx, sy = canon(*tr['first_pos'], my_side)
        died = tr['last'] < end_tick - 30
        life = (tr['last'] - t0) / TPS
        hpf = tr['last_hp'] / tr['mhp'] if tr['mhp'] > 0 else None
        # my responses within the window
        i = bisect.bisect_right(p_ticks, t0)
        resp = [p for p in plays[i:] if p['tick'] <= t0 + WIN][:3]
        allw = [p for p in plays[i:] if p['tick'] <= t0 + WIN]
        rs = []
        for p in resp:
            rs.append(dict(card=p['card'], delay=round((p['tick'] - t0) / TPS, 1),
                           where=place_cat(p['x'], p['y'], sx, sy), x=round(p['x'], 1), y=round(p['y'], 1),
                           dist=round(math.hypot(p['x'] - sx, p['y'] - sy), 1), tick=p['tick']))
        # cause of death
        cause, attackers = None, []
        if died:
            lx, ly = canon(*tr['last_pos'], my_side)
            j = bisect.bisect_left(p_ticks, tr['last'] - 140)
            rk = [p for p in plays[j:] if p['tick'] <= tr['last'] + 20 and p['card'] == 'Rocket'
                  and math.hypot(p['x'] - lx, p['y'] - ly) <= 3.5]
            tk = [p for p in plays[j:] if p['tick'] <= tr['last'] + 20 and p['card'] == 'Log'
                  and math.hypot(p['x'] - lx, p['y'] - ly) <= 12]
            # attackers alive within range on the frame where the spawner was last seen
            for (side, x, y, name, hp, mhp, uid) in bt.get(tr['last'], []):
                if side != my_side:
                    continue
                cx, cy = canon(x, y, my_side)
                d = math.hypot(cx - lx, cy - ly)
                if name == 'TOWER' and d <= 7.5:
                    attackers.append('Tower')
                elif name in RANGE and d <= RANGE[name]:
                    attackers.append(name)
            attackers = sorted(set(attackers))
            if rk:
                cause = 'Rocket'
            elif hpf is not None and hpf > 0.45 and not attackers:
                cause = 'expiry/unknown(hp>45%)'
            elif attackers:
                cause = 'in-range:' + '+'.join(attackers)
            else:
                cause = 'no-attacker-in-range(hp<=45%)'
        # my tower damage over the next 15 s
        trunc = t0 + DMG > end_tick + 5
        dmg = 0.0; dmg_same = 0.0
        for x in tw:
            dd = max(0.0, hp_at(x, t0) - hp_at(x, t0 + DMG))
            dmg += dd
            if (x < 9000) == (tr['first_pos'][0] < 9000) and abs(x - 9000) > 1000:
                dmg_same += dd
        prm = min([v[2] for v in tw.values()] or [1])
        # elixir of mine at the deploy
        k = max(0, bisect.bisect_right(ticks, t0) - 1)
        k8 = min(len(ticks) - 1, max(0, bisect.bisect_right(ticks, t0 + WIN) - 1))
        rows.append(dict(fam=tr['fam'], name=tr['name'], t0=t0, first=tr['first'], sx=round(sx, 1), sy=round(sy, 1),
                         depth=round(16 - sy, 1), lane='L' if sx < 9 else 'R', my_elixir=round(timeline[k][1] or 0, 1), my_elixir_8s=round(timeline[k8][1] or 0, 1),
                         died=died, life_s=round(life, 1), last_hp_frac=(round(hpf, 2) if hpf is not None else None), cause=cause, attackers=attackers,
                         resp=rs, n_resp=len(rs), n8=len(allw), spent8=sum(COST.get(p['card'], 0) for p in allw),
                         first_same_lane=next((round((p['tick'] - t0) / TPS, 1) for p in allw if (p['x'] < 9) == (sx < 9)), None),
                         first_on_near=next((round((p['tick'] - t0) / TPS, 1) for p in allw if math.hypot(p['x'] - sx, p['y'] - sy) <= 6), None), ignored=len(rs) == 0, dmg=round(dmg), dmg_same=round(dmg_same),
                         dmg_pct_princess=round(100 * dmg / prm, 1), dmg_trunc=trunc, game_end=end_tick,
                         **{k2: v for k2, v in meta.items() if k2 != 'appear_lag'}))
    # spell audit: every Rocket / Log / Tornado I play while an enemy spawner PARENT is alive anywhere
    par = {(t['uid'], t['name']): t for t in parents}
    spells = []
    for pl in plays:
        if pl['card'] not in ('Rocket', 'Log', 'Tornado'):
            continue
        ft = bisect.bisect_left(ticks, pl['tick'] + (36 if pl['card'] == 'Rocket' else 24))
        ft = min(ft, len(ticks) - 1)
        alive = [t for t in parents if t['first'] <= ticks[ft] <= t['last']]
        hit = collections.Counter(); par_hit = None
        for (side, x, y, name, hp, mhp, uid) in timeline[ft][2]:
            if side != opp or name == 'TOWER':
                continue
            cx, cy = canon(x, y, my_side)
            if pl['card'] == 'Rocket':
                inside = math.hypot(cx - pl['x'], cy - pl['y']) <= 2.5
            elif pl['card'] == 'Log':
                inside = abs(cx - pl['x']) <= 2.5 and pl['y'] - 11.5 <= cy <= pl['y'] + 1
            else:
                inside = math.hypot(cx - pl['x'], cy - pl['y']) <= 3.0
            if not inside:
                continue
            isp = (uid, name) in par
            kind = ('BUILDING' if (pl['card'] == 'Log' and FAM.get(name) in BUILDINGS) else 'SPAWNER') if isp else ('child' if name in FAM else name)
            hit[kind] += 1
        d_par = min([math.hypot(canon(*t['last_pos'], my_side)[0] - pl['x'], canon(*t['last_pos'], my_side)[1] - pl['y']) for t in alive] or [99])
        if hit['SPAWNER']:
            cls = 'hits spawner'
        elif hit['BUILDING'] and len(hit) == 1:
            cls = 'log on building (no effect)'
        elif not hit:
            cls = 'hits nothing'
        elif set(hit) <= {'child'}:
            cls = 'children only'
        elif 'child' in hit and len(hit) > 1:
            cls = 'children + other'
        else:
            cls = 'other troops only'
        spells.append(dict(ctx=bool(alive), card=pl['card'], tick=pl['tick'], x=round(pl['x'], 1), y=round(pl['y'], 1), cls=cls, hit=dict(hit),
                           fams=sorted(set(t['fam'] for t in alive)), d_nearest_parent=round(d_par, 1), **{k2: v for k2, v in meta.items() if k2 in ('src', 'job')}))
    # baseline: all 15 s windows, my tower loss (percent of one princess tower)
    base = []
    prm = min([v[2] for v in tw.values()] or [1])
    for tk in range(200, max(200, end_tick - DMG), 20):
        base.append(100 * sum(max(0.0, hp_at(x, tk) - hp_at(x, tk + DMG)) for x in tw) / prm)
    return rows, dict(card_counts=dict(collections.Counter(p['card'] for p in plays)), spells=spells, simul=dict(simul), simul_parent=simul_parent, child_tracks=dict(n_child_tracks), base_mean=(statistics.mean(base) if base else None), base_n=len(base))


# ------------------------------- pros -------------------------------------------------
def pros_one(f):
    try:
        d = json.load(open(f))
    except Exception:
        return None
    fd = d['final_decks']
    sides = [s for s in '01' if 'Xbow' in fd[s]]
    if len(sides) != 1:
        return None
    ms = int(sides[0])
    deck = set(c.split('@')[0] for c in fd[sides[0]])
    core = len(deck & CORE)
    tl = []
    for fr in d['frames']:
        b = []
        for e in fr['entities']:
            nm = e[3]
            if nm == '-1' and e[8] < 5000100:
                nm = 'TOWER'
            elif nm == '-1':
                continue
            b.append((e[0], e[1], e[2], nm, e[4], e[5], e[8]))
        tl.append((fr['tick'], fr['elixir'][ms], b))
    plays, eplays = [], []
    for p in d['log']:
        if not p.get('accepted') or p.get('x') is None:
            continue
        cx, cy = canon(p['x'], p['y'], ms)
        if p['side'] == ms:
            plays.append(dict(tick=p['tick'], card=OUR.get(p['card'], p['card']), x=cx, y=cy))
        else:
            n = p['card'].replace('-', '').lower()
            for nm, fam in (('witch', 'Witch'), ('nightwitch', 'NightWitch'), ('furnace', 'Furnace'), ('motherwitch', 'MotherWitch'),
                            ('tombstone', 'Tombstone'), ('goblinhut', 'GoblinHut'), ('barbarianhut', 'BarbarianHut'), ('graveyard', 'Graveyard')):
                if n == nm:
                    eplays.append((p['tick'], fam))
    won = d['final'].get('winner') == ms
    rows, extra = analyze(tl, ms, plays, dict(src=os.path.basename(f), job=os.path.basename(os.path.dirname(f)),
                                              won=won, core=core, appear_lag=0), eplays)
    # log-only cross-check count of deployments
    extra['n_log_deploys'] = collections.Counter(fam for _, fam in eplays)
    extra['n_plays_mine'] = len(plays)
    extra['core'] = core; extra['won'] = won
    return rows, extra


def run_pros(pool_n=3):
    files = sorted(glob.glob(os.path.join(ROOT, 'scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json')))
    rows, extras = [], []
    with Pool(pool_n) as p:
        for r in p.imap_unordered(pros_one, files, chunksize=8):
            if r:
                rows += r[0]; extras.append(r[1])
    return rows, extras, len(files)


# ------------------------------- bot --------------------------------------------------
def bot_one(f):
    from pipeline.obs_contract import _catalog_names
    N = _catalog_names()
    tl_f, tl_d, plays = [], [], []
    my_side = None
    meta_end = None
    for l in open(f):
        try:
            r = json.loads(l)
        except Exception:
            continue
        ev = r.get('event')
        if ev == 'frame':
            my_side = r.get('my_side', my_side)
            b = []
            for e in r['ents']:
                nm = 'TOWER' if (e[3] == -1 and e[6] in (12, 13)) else N.get(e[3], 'id%s' % e[3])
                if e[3] == -1 and e[6] not in (12, 13):
                    continue
                b.append((e[0], e[1], e[2], nm, e[4], e[5], e[7]))
            tl_f.append((r['tick'], r.get('elixir'), b))
        elif ev == 'decision':
            pub = r.get('public') or {}
            my_side = pub.get('observer_side', my_side)
            b = []
            for e in pub.get('raw_bodies', []):
                if e['card_id'] == -1 and e['kind'] in (12, 13):
                    nm = 'TOWER'
                elif e['card_id'] == -1:
                    continue
                else:
                    nm = N.get(e['card_id'], 'id%s' % e['card_id'])
                b.append((e['side'], e['x'], e['y'], nm, e['hp'], e['max_hp'], e['address']))
            tl_d.append((r['tick'], pub.get('own_elixir_raw'), b))
        elif ev == 'play':
            plays.append(r)
        elif ev == 'end':
            meta_end = r
    tl = tl_f if len(tl_f) > 50 else tl_d
    if not tl or my_side is None:
        return dict(file=os.path.basename(f), usable=False, n_plays=len(plays))
    # dedupe ticks (frames can repeat a tick)
    seen = set(); t2 = []
    for t in tl:
        if t[0] in seen:
            continue
        seen.add(t[0]); t2.append(t)
    t2.sort(key=lambda t: t[0])
    pl = [dict(tick=p['tick'] + BOT_LAG, card=p['name'], x=18 * (1 - p['xy'][0]), y=32 * p['xy'][1]) for p in plays if p.get('xy')]
    if my_side == 0:
        pass  # play xy are in the bot's own frame; canonical already (own home at y>16)
    rows, extra = analyze(t2, my_side, pl, dict(src=os.path.basename(f), appear_lag=5))
    extra.update(file=os.path.basename(f), usable=True, my_side=my_side, src_kind='frame' if tl is tl_f else 'decision',
                 n_plays=len(pl), n_ticks=len(t2), end_tick=t2[-1][0], mtime=os.path.getmtime(f))
    return rows, extra


def run_bot(pool_n=3):
    files = sorted(glob.glob(os.path.join(ROOT, 'scratchpad/gauntlet/L68/live_reader/live_play_2026100[456]_*.jsonl')))
    rows, extras = [], []
    with Pool(pool_n) as p:
        for r in p.imap(bot_one, files, chunksize=2):
            if isinstance(r, dict):
                extras.append(r)
            else:
                rows += r[0]; extras.append(r[1])
    # match results
    outs = []
    for nf in sorted(glob.glob(os.path.join(ROOT, 'scratchpad/gauntlet/L68/live_reader/ladder_nav_2026100[456]*.jsonl'))):
        for l in open(nf):
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get('event') == 'outcome':
                outs.append((r['t'], r['won']))
    outs.sort()
    ts = [o[0] for o in outs]
    for e in extras:
        if 'mtime' not in e:
            e['mtime'] = os.path.getmtime(os.path.join(ROOT, 'scratchpad/gauntlet/L68/live_reader', e['file']))
        i = bisect.bisect_left(ts, e['mtime'] - 5)
        e['won'] = outs[i][1] if i < len(ts) and ts[i] - e['mtime'] < 60 else None
    wmap = {e['file']: e['won'] for e in extras}
    for r in rows:
        r['won'] = wmap.get(r['src'])
    return rows, extras, len(files)


# ------------------------------- summaries --------------------------------------------
def med(v):
    v = [x for x in v if x is not None]
    return round(statistics.median(v), 1) if v else None


def mean(v):
    v = [x for x in v if x is not None]
    return round(statistics.mean(v), 1) if v else None


def pct(a, b):
    return round(100.0 * a / b) if b else None


def summarize(rows, extras, label):
    out = {}
    for fam in FAMS:
        R = [r for r in rows if r['fam'] == fam]
        if not R:
            continue
        n = len(R)
        first = collections.Counter(r['resp'][0]['card'] for r in R if r['resp'])
        where = collections.Counter(r['resp'][0]['where'] for r in R if r['resp'])
        allc = collections.Counter(p['card'] for r in R for p in r['resp'])
        att = collections.Counter(a for r in R for a in r['attackers'])
        D = [r for r in R if not r['dmg_trunc']]
        out[fam] = dict(
            n=n, n_games=len(set(r['src'] for r in R)), ignored_pct=pct(sum(r['ignored'] for r in R), n),
            plays8_mean=mean([r['n8'] for r in R]), elixir8_mean=mean([r['spent8'] for r in R]),
            no_same_lane_resp_8s_pct=pct(sum(1 for r in R if r['first_same_lane'] is None), n),
            no_on_near_resp_8s_pct=pct(sum(1 for r in R if r['first_on_near'] is None), n),
            first_on_near_med_s=med([r['first_on_near'] for r in R]),
            life_gt20_pct=pct(sum(1 for r in R if r['life_s'] > 20), n),
            n_resp_mean=mean([r['n_resp'] for r in R]),
            first_delay_med_s=med([r['resp'][0]['delay'] for r in R if r['resp']]),
            first_card=dict(first.most_common(6)), first_card_pct={k: pct(v, sum(first.values())) for k, v in first.most_common(6)},
            all3_card_pct={k: pct(v, sum(allc.values())) for k, v in allc.most_common(8)},
            first_where_pct={k: pct(v, sum(where.values())) for k, v in where.most_common(8)},
            on_or_near_any_pct=pct(sum(1 for r in R if any(p['where'] in ('ON', 'NEAR') for p in r['resp'])), n),
            died_pct=pct(sum(r['died'] for r in R), n),
            life_med_s=med([r['life_s'] for r in R if r['died']]),
            life_p25_p75=[round(statistics.quantiles([r['life_s'] for r in R if r['died']], n=4)[i], 1) for i in (0, 2)] if sum(r['died'] for r in R) >= 4 else None,
            cause=dict(collections.Counter(r['cause'] for r in R if r['died']).most_common(6)),
            attacker_in_range_pct=({k: pct(v, sum(r['died'] for r in R)) for k, v in att.most_common(6)}),
            spawn_depth_med_tiles=med([r['depth'] for r in R]),
            my_elixir_med=med([r['my_elixir'] for r in R]), my_elixir_8s_med=med([r['my_elixir_8s'] for r in R]),
            king_back_first_pct=pct(sum(1 for r in R if r['resp'] and r['resp'][0]['y'] >= 29.5), n),
            dmg15_mean_pct_princess=mean([r['dmg_pct_princess'] for r in D]),
            dmg15_median_pct_princess=med([r['dmg_pct_princess'] for r in D]),
            dmg15_ignored=mean([r['dmg_pct_princess'] for r in D if r['ignored']]),
            dmg15_responded=mean([r['dmg_pct_princess'] for r in D if not r['ignored']]),
            win_rate_pct=pct(sum(1 for r in R if r.get('won') is True), sum(1 for r in R if r.get('won') is not None)),
        )
    allD = [r for r in rows if not r['dmg_trunc']]
    sp = [x for e in extras for x in (e.get('spells') or [])]
    spc = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    names = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for x in sp:
        spc[x['ctx']][x['card']][x['cls']] += 1
        for k2, v in x['hit'].items():
            names[x['ctx']][x['card']][k2] += v
    out['_spells'] = {('spawner_alive' if c else 'no_spawner'): {k: dict(v, total=sum(v.values())) for k, v in d.items()} for c, d in spc.items()}
    out['_spell_hit_names'] = {('spawner_alive' if c else 'no_spawner'): {k: dict(v.most_common(8)) for k, v in d.items()} for c, d in names.items()}
    ng = max(1, len(extras))
    cc = collections.Counter()
    for e in extras:
        cc.update(e.get('card_counts') or {})
    out['_plays_per_game'] = {k: round(v / ng, 2) for k, v in cc.most_common()}
    out['_games'] = len(extras)
    ge = {}
    for fam in FAMS:
        ex = [e for e in extras if (e.get('simul_parent') or {}).get(fam, 0) > 0]
        dec = [e for e in ex if e.get('won') is not None]
        ge[fam] = dict(games=len(ex), decided=len(dec), wins=sum(1 for e in dec if e['won']))
    dec = [e for e in extras if e.get('won') is not None]
    ge['_all'] = dict(games=len(extras), decided=len(dec), wins=sum(1 for e in dec if e['won']))
    anyf = [e for e in dec if any((e.get('simul_parent') or {}).get(f, 0) > 0 for f in FAMS)]
    ge['_any_spawner'] = dict(decided=len(anyf), wins=sum(1 for e in anyf if e['won']))
    nof = [e for e in dec if e not in anyf]
    ge['_no_spawner'] = dict(decided=len(nof), wins=sum(1 for e in nof if e['won']))
    out['_game_exposure'] = ge
    # Xbow responses: how many of the first-3 Xbow responses are within Xbow range of the spawner
    xr = [p for r in rows for p in r['resp'] if p['card'] == 'Xbow']
    out['_xbow_resp'] = dict(n=len(xr), in_range_11p5_pct=pct(sum(1 for p in xr if p['dist'] <= 11.5), len(xr)), med_dist=med([p['dist'] for p in xr]))
    out['_all'] = dict(n=len(rows), dmg15_mean_pct_princess=mean([r['dmg_pct_princess'] for r in allD]),
                       base_mean=mean([e.get('base_mean') for e in extras if e.get('base_mean') is not None]))
    for key in ('simul', 'simul_parent'):
        sm = collections.defaultdict(collections.Counter)
        for e in extras:
            for f, c in (e.get(key) or {}).items():
                sm[f][c] += 1
        out['_max_simultaneous_by_game_' + key] = {f: dict(sorted(c.items())) for f, c in sm.items()}
    out['_child_tracks_total'] = dict(sum((collections.Counter(e.get('child_tracks') or {}) for e in extras), collections.Counter()))
    return out


def table_md(S, label):
    L = ['### %s' % label, '| family | n | ignored | 1st resp delay | 1st-resp card (%) | 1st placement (%) | died | life med s | tower dmg 15s (%princ) |', '|---|---|---|---|---|---|---|---|---|']
    for fam in FAMS:
        s = S.get(fam)
        if not s:
            continue
        fc = ', '.join('%s %s' % (k, v) for k, v in list(s['first_card_pct'].items())[:4])
        fw = ', '.join('%s %s' % (k, v) for k, v in list(s['first_where_pct'].items())[:3])
        L.append('| %s | %d | %s%% | %ss | %s | %s | %s%% | %s | %s |' % (fam, s['n'], s['ignored_pct'], s['first_delay_med_s'], fc, fw, s['died_pct'], s['life_med_s'], s['dmg15_mean_pct_princess']))
    return '\n'.join(L)


if __name__ == '__main__':
    args = sys.argv[1:] or ['--pros', '--bot']
    res = {}
    if '--pros' in args:
        rows, ex, nf = run_pros()
        with open(os.path.join(HERE, 'spells_pros.jsonl'), 'w') as fh:
            for e in ex:
                for x in e.get('spells') or []:
                    fh.write(json.dumps(x) + chr(10))
        with open(os.path.join(HERE, 'rows_pros.jsonl'), 'w') as fh:
            for r in rows:
                fh.write(json.dumps(r) + '\n')
        full = [r for r in rows if r.get('core', 0) >= 7]
        exf = [e for e in ex if e.get('core', 0) >= 7]
        res['pros'] = dict(files=nf, used=len(ex), core7=len(exf), deploys_all=len(rows), deploys_core7=len(full),
                           log_deploy_counts=dict(sum((e['n_log_deploys'] for e in ex), collections.Counter())),
                           win_rate_icebow=pct(sum(e['won'] for e in ex), len(ex)),
                           summary=summarize(full, exf, 'pros'), summary_all_decks=summarize(rows, ex, 'pros_all'))
    if '--bot' in args:
        rows, ex, nf = run_bot()
        with open(os.path.join(HERE, 'spells_bot.jsonl'), 'w') as fh:
            for e in ex:
                for x in e.get('spells') or []:
                    fh.write(json.dumps(x) + chr(10))
        with open(os.path.join(HERE, 'rows_bot.jsonl'), 'w') as fh:
            for r in rows:
                fh.write(json.dumps(r) + '\n')
        usable = [e for e in ex if e.get('usable')]
        res['bot'] = dict(files=nf, usable=len(usable), unusable_play_only=len(ex) - len(usable),
                          decided=sum(1 for e in usable if e.get('won') is not None),
                          wins=sum(1 for e in usable if e.get('won') is True),
                          deploys=len(rows), summary=summarize(rows, usable, 'bot'))
    old = {}
    p = os.path.join(HERE, 'results.json')
    if os.path.exists(p):
        old = json.load(open(p))
    old.update(res)
    # excess tower damage the bot takes after spawner deploys vs pros, per bot match
    if 'pros' in old and 'bot' in old:
        ex = {}
        nm = max(1, old['bot']['usable'])
        for fam, b in old['bot']['summary'].items():
            pr = old['pros']['summary'].get(fam)
            if fam.startswith('_') or not pr or b.get('dmg15_mean_pct_princess') is None:
                continue
            ex[fam] = dict(bot_n=b['n'], bot_dmg=b['dmg15_mean_pct_princess'], pros_dmg=pr['dmg15_mean_pct_princess'],
                           excess_pct_princess_per_bot_match=round(b['n'] * (b['dmg15_mean_pct_princess'] - pr['dmg15_mean_pct_princess']) / nm, 2))
        old['excess_tower_damage'] = ex
    json.dump(old, open(p, 'w'), indent=1, default=str)
    md = []
    if 'pros' in old:
        md.append(table_md(old['pros']['summary'], 'PROS (core-deck icebow, n deploys)'))
    if 'bot' in old:
        md.append(table_md(old['bot']['summary'], 'BOT'))
    open(os.path.join(HERE, 'tables.md'), 'w').write('\n\n'.join(md))
    print('\n\n'.join(md))
