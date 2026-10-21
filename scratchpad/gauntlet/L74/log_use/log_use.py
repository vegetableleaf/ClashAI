"""Log use vs log bait on the live icebow logs (owner 10-21: "every model is trigger happy with the Log ... half the time the
opponent then punishes with Goblin Barrel / Skeleton Barrel / Dart Goblin").

Read-only, light CPU (~1-2 s per match). Uses only OUR public log fields and the opponent's PUBLIC plays / board bodies
(pipeline.public_observation.PublicObserver = the model's own opp_cycle source); never the opponent's hand, deck or
elixir (the frame's opp_elixir_est and the decision's opponent_elixir_estimate are never read).

  python log_use.py [--since 20261013_000000] [--out per_match.jsonl]

Per own confirmed Log: the enemy ground bodies its roll crosses (box 1.95 t half-width + 0.5 body pad, 10.1 t reach,
177 mt/tick = LOG_HIT_TICKS 57), which of them vanish within KILL_TICKS of the hit (= killed; may include tower/troop
kills), their elixir value (card elixir / bodies; a role-child body = CHILD_VALUE), and the seconds until the Log is back
in our hand. Per enemy LOG-BAIT play: was our Log in hand (last decision at or before the play), and the own-tower damage
it did = every own-tower HP drop between two frames x the share of that card's bodies among enemy bodies within NEAR of
that tower, summed for PUNISH_TICKS after the play.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import defaultdict
import json
import math
from pathlib import Path
import random
import sys

REPO = Path(__file__).resolve().parents[4]
try:                                    # shared laptop: idle priority
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:                       # noqa: BLE001
    pass
sys.path[:0] = [str(REPO), str(REPO / 'scratchpad/gauntlet/L74/monitor')]
from pipeline import vocab                                     # noqa: E402
from pipeline.obs_contract import catalog_card_form            # noqa: E402
from pipeline.public_observation import PublicObserver         # noqa: E402

LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
SIMCARDS = REPO / 'research/ext/Royale/RoyaleSim/data/derived/cards-160402017-20261006.json'
MAIN_PRINCESS = {4424, 4858}        # main account: 4424 until 10-19 ~14:00, 4858 (level-16 towers) after
HALF, PAD, REACH, SPEED = 1950, 500, 10100, 177    # Log rolling box (card table) and roll speed (LOG_HIT_TICKS 57)
KILL_TICKS = 40                     # a crossed body gone this soon after the crossing = killed
GAP = 15                            # a body unseen longer than this has ended
CHILD_VALUE = 1 / 3                 # elixir credited to a role-child body (max_hp < 45% of its card's biggest): a Skeleton
PUNISH_TICKS = 300                  # 15 s after a bait play
NEAR = 9500                         # mt: a body this close to a tower can be the one hitting it (Princess range 9 t)
# Log-bait = cheap ground swarm / glass cards the Log answers. CORE = the owner's three + the two other classic bait
# win-condition cards; EXT adds the rest of the Log-answerable ground cheap cards.
CORE = ('goblin_barrel', 'skeleton_barrel', 'dart_goblin', 'princess', 'goblin_gang')
EXT = CORE + ('skeleton_army', 'goblins', 'spear_goblins', 'wall_breakers', 'rascals', 'guards', 'firecracker',
              'goblin_giant', 'goblin_hut')
BODY_COUNT = {'goblin_barrel': 3, 'skeleton_barrel': 8, 'goblin_gang': 6, 'skeleton_army': 15, 'goblins': 4,
              'spear_goblins': 3, 'wall_breakers': 2, 'rascals': 3, 'guards': 3, 'skeletons': 3, 'barbarians': 5,
              'minion_horde': 6, 'royal_recruits': 6, 'royal_hogs': 4, 'elite_barbarians': 2, 'bats': 5, 'minions': 3}


def sim_traits():
    cards = json.loads(SIMCARDS.read_text(encoding='utf-8'))['cards']
    out = {}
    for c in cards:
        out[vocab.engine_key(c['name'])] = dict(elixir=c.get('elixir') or 0, kind=c.get('kind'),
                                                 air=(c.get('flying_height') or 0) > 0)
    return out


TRAITS = sim_traits()


def key_of(cid):
    name, form = catalog_card_form(cid)
    return (vocab.engine_key(name) if name else None), form


def tower_slot(e):
    if e[3] != -1:
        return None
    for tx, ty, k in ((9000, 3000, 'K0'), (3500, 6500, 'L0'), (14500, 6500, 'R0'),
                      (9000, 29000, 'K1'), (3500, 25500, 'L1'), (14500, 25500, 'R1')):
        if abs(e[1] - tx) < 600 and abs(e[2] - ty) < 600:
            return k
    return None


ENT = ('side', 'x', 'y', 'card_id', 'hp', 'max_hp', 'kind', 'address')
ST = ('behavior_state_raw', 'evo', 'level', 'category')
PROJ = ('side', 'x', 'y', 'card_id', 'target_x', 'target_y', 'address', 'generation_key', 'source', 'target')
FX = ('side', 'x', 'y', 'card_id', 'remaining_ms', 'level_raw', 'address', 'generation_key')


def reader_frame(e):
    """logframes.frames() shape, tolerant of logs without ents_state (older --log-frames off logs)."""
    st = e.get('ents_state') or [[None] * 4] * len(e['ents'])
    return dict(game_tick=int(e['tick']), my_side=e['my_side'],
                entities=[dict(zip(ENT, a), **dict(zip(ST, b))) for a, b in zip(e['ents'], st)],
                projectiles=[dict(zip(PROJ, p)) for p in e.get('proj') or ()],
                effects=[dict(zip(FX, p)) for p in e.get('fx') or ()])


def parse(path):
    """-> match dict or None (not main-account icebow / no frames)."""
    ck = None; frames = []; decs = []; plays = []; outs = []; end = None; side = None; po = None
    for raw in open(path, 'rb'):
        head = raw[:40]
        if b'"frame"' in head:
            j = json.loads(raw)
            if j.get('ents') is None:
                continue
            side = j['my_side']
            if po is None:
                po = PublicObserver(side)
            po.update(reader_frame(j), source='reader')
            frames.append((j['tick'], j['ents']))
        elif b'"decision"' in head:
            j = json.loads(raw)
            decs.append((j['tick'], [h.get('name') for h in (j.get('public') or {}).get('own_hand', [])]))
        elif b'"play"' in head:
            j = json.loads(raw)
            plays.append(dict(tick=j['tick'], name=j['name'], xy=j['xy'], forced=bool(j.get('forced')),
                              rule=next((k for k in ('lethal_rocket', 'hazard_play') if j.get(k)), None)))
        elif b'"confirmed"' in head or b'"unconfirmed"' in head:
            j = json.loads(raw)
            outs.append((j['event'], j['name'], j.get('intended'), j['tick']))
        elif b'"start"' in head and ck is None:
            ck = json.loads(raw).get('ckpt')
        elif b'"end"' in head:
            end = json.loads(raw)
    if not frames or ck is None:
        return None
    first = frames[0][1]
    pr = {e[5] for e in first if e[0] == side and (tower_slot(e) or 'K')[0] in 'LR'}
    deck = {n for _, h in decs for n in h}
    if not pr or not pr <= MAIN_PRINCESS or not {'Xbow', 'Log'} <= deck:
        return None
    own = [dict(p, xy=o[2] or p['xy'], land=o[3]) for p, o in zip(plays, outs) if o[0] == 'confirmed' and o[1] == p['name']]
    return dict(ck=ck, side=side, frames=frames, decs=decs, own=own, opp=po.plays, end=end)


def raw_xy(side, xy):
    """own-frame screen xy (0..1, own edge y=1) -> raw millitiles (fights.read_match's conversion)."""
    x, y = 18 - xy[0] * 18, xy[1] * 32
    return (x * 1000, y * 1000) if side == 1 else ((18 - x) * 1000, (32 - y) * 1000)


class Board:
    """Body presence per (address, card_id): sorted ticks; role-child test by the card's biggest max_hp."""
    def __init__(self, m):
        self.m = m
        self.ticks = [t for t, _ in m['frames']]
        self.seen = defaultdict(list)
        self.top = defaultdict(int)
        for t, ents in m['frames']:
            for e in ents:
                if e[3] != -1:
                    self.seen[e[7], e[3]].append(t)
                    self.top[e[0], e[3]] = max(self.top[e[0], e[3]], e[5])

    def end_of(self, k, t):
        """last tick of body k's continuous presence through t."""
        ts = self.seen[k]
        i = bisect_right(ts, t) - 1
        while i + 1 < len(ts) and ts[i + 1] - ts[i] <= GAP:
            i += 1
        return ts[i] if i >= 0 else t

    def value(self, e):
        k, _ = key_of(e[3])
        tr = TRAITS.get(k, {})
        if e[5] > 0 and e[5] < .45 * self.top[e[0], e[3]]:
            return CHILD_VALUE
        n = BODY_COUNT.get(k, 1)
        return (tr.get('elixir') or CHILD_VALUE * n) / n

    def frame_at(self, t):
        i = max(0, bisect_right(self.ticks, t) - 1)
        return self.m['frames'][i]


def log_hits(m, B, p):
    """Enemy ground bodies the Log's roll crosses: the front moves SPEED mt/tick from the cast point (confirmation tick)."""
    side, (lx, ly) = m['side'], raw_xy(m['side'], p['xy'])
    fwd = 1 if side == 0 else -1
    t0 = p['land']
    hits = {}
    for t, ents in m['frames'][bisect_right(B.ticks, t0 - 1):]:
        if t > t0 + REACH // SPEED + 2:
            break
        front = min(REACH, (t - t0) * SPEED)
        for e in ents:
            if e[0] == side or e[3] == -1 or (e[7], e[3]) in hits:
                continue
            k, _ = key_of(e[3])
            tr = TRAITS.get(k)
            if tr is None or tr['air']:
                continue
            ahead = (e[2] - ly) * fwd
            if abs(e[1] - lx) <= HALF + PAD and -600 - PAD <= ahead <= front + PAD:
                hits[e[7], e[3]] = dict(t=t, key=k, hp=e[4], max_hp=e[5], value=B.value(e),
                                        building=tr['kind'] == 'building')
    last = B.ticks[-1]
    for k, h in hits.items():
        h['killed'] = B.end_of(k, h['t']) <= h['t'] + KILL_TICKS and last > h['t'] + KILL_TICKS + 20
        after = next((e[4] for t, ents in m['frames'][bisect_right(B.ticks, h['t'] + 3):bisect_right(B.ticks, h['t'] + 12)]
                      for e in ents if (e[7], e[3]) == k), None)
        h['hp_after'] = after
    # crosses an enemy tower?
    tower = any(e[0] != side and tower_slot(e) and abs(e[1] - lx) <= HALF + 1000 and 0 <= (e[2] - ly) * fwd <= REACH + 1000
                for e in B.frame_at(t0)[1])
    return hits, tower


def hand_at(m, t):
    i = bisect_right([d[0] for d in m['decs']], t) - 1
    return m['decs'][i][1] if i >= 0 else []


def back_in_hand(m, t):
    for dt, h in m['decs']:
        if dt > t + 2 and 'Log' in h:
            return (dt - t) / 20
    return None


def tower_damage(m, B):
    """{(card key, play index)}: bait-attributed own-tower damage per enemy play (all keys, filter later)."""
    side = m['side']
    plays = m['opp']
    by_key = defaultdict(list)
    for i, p in enumerate(plays):
        by_key[p['card']].append((p['tick'], i))
    dmg = defaultdict(float)
    prev = None
    for t, ents in m['frames']:
        towers = {tower_slot(e): (e[1], e[2], e[4]) for e in ents if e[0] == side and tower_slot(e)}
        if prev:
            for s, (x, y, hp) in towers.items():
                if s in prev and 0 < prev[s] - hp < 3000:
                    near = [e for e in ents if e[0] != side and e[3] != -1 and math.hypot(e[1] - x, e[2] - y) <= NEAR]
                    if not near:
                        continue
                    for e in near:
                        k, _ = key_of(e[3])
                        cand = [(pt, i) for pt, i in by_key.get(k, []) if 0 <= t - pt <= PUNISH_TICKS]
                        if cand:
                            dmg[cand[-1][1]] += (prev[s] - hp) / len(near)
        prev = {s: v[2] for s, v in towers.items()}
    return dmg


def analyse(path, results):
    m = parse(path)
    if m is None:
        return None
    import card_use as CU
    B = Board(m)
    res = results.get(path.name)
    won = res[0] == 'WIN' if res else (((m['end'] or {}).get('towers') or {}).get('won'))
    reveal = {}
    for p in m['opp']:
        if p['card'] in EXT:
            reveal.setdefault(p['card'], p['tick'])
    core_t = min([reveal[k] for k in CORE if k in reveal], default=None)
    ext_t = min(reveal.values(), default=None)
    logs = []
    for p in m['own']:
        if p['name'] != 'Log':
            continue
        hits, tower = log_hits(m, B, p)
        hv = list(hits.values())
        killed = sum(h['value'] for h in hv if h['killed'])
        logs.append(dict(tick=p['land'], forced=p['forced'], rule=p['rule'], n_hit=len(hv),
                         n_killed=sum(h['killed'] for h in hv), killed_value=round(killed, 2),
                         hit_value=round(sum(h['value'] for h in hv), 2), tower=tower,
                         keys=sorted({h['key'] for h in hv}), bait_hit=any(h['key'] in EXT for h in hv),
                         hits=[[h['key'], h['hp'], h['max_hp'], h['hp_after'], h['killed'], round(h['value'], 2),
                                h['building']] for h in hv],
                         back_s=back_in_hand(m, p['land']),
                         core_revealed=core_t is not None and core_t < p['land'],
                         ext_revealed=ext_t is not None and ext_t < p['land'],
                         own_half=(raw_xy(m['side'], p['xy'])[1] < 16000) == (m['side'] == 0)))
    dmg = tower_damage(m, B)
    bait = []
    own_logs = [lg['tick'] for lg in logs]
    for i, p in enumerate(m['opp']):
        if p['card'] not in EXT:
            continue
        h = hand_at(m, p['tick'])
        since = [p['tick'] - t for t in own_logs if t <= p['tick']]
        bait.append(dict(tick=p['tick'], card=p['card'], log_in_hand='Log' in h, hand_known=bool(h),
                         since_log_s=round(min(since) / 20, 1) if since else None, dmg=round(dmg.get(i, 0.0)),
                         first=reveal[p['card']] == p['tick']))
    # enemy ground troop plays and whether our next Log (<= 12 s) crossed that card
    ground = []
    for p in m['opp']:
        tr = TRAITS.get(p['card'])
        if not tr or tr['kind'] != 'troop' or tr['air']:
            continue
        nxt = next((lg for lg in logs if 0 <= lg['tick'] - p['tick'] <= 240 and p['card'] in lg['keys']), None)
        ground.append(dict(tick=p['tick'], card=p['card'], log_in_hand='Log' in hand_at(m, p['tick']),
                           logged=nxt is not None, cost=tr['elixir']))
    last = m['frames'][-1][0]
    known = [h for t, h in m['decs'] if len(h) == 4]
    out_share = sum('Log' not in h for h in known) / len(known) if known else None
    return dict(match=path.stem, mark=CU.mark_of(m['ck']), won=won, ticks=last, logs=logs, bait=bait, ground=ground,
                log_out_share=out_share,
                core_revealed=core_t, ext_revealed=ext_t, opp_cards=sorted({p['card'] for p in m['opp']}),
                own_plays=[[p['land'], vocab.engine_key(p['name'])] for p in m['own']],
                opp_plays=[[p['tick'], p['card']] for p in m['opp']])


# ---------------------------------------------------------------- summary
def boot(xs, f, B=1000, seed=0):
    rng = random.Random(seed); v = sorted(f([rng.choice(xs) for _ in xs]) for _ in range(B))
    return round(v[int(.025 * B)], 3), round(v[int(.975 * B) - 1], 3)


def share(xs, pred):
    xs = list(xs)
    return (sum(map(pred, xs)) / len(xs)) if xs else float('nan')


LOG_DMG = 429                       # measured: the modal hp drop of a Log-crossed body on the level-16 logs (85 of 124)
LOW = 1.0                           # a "low-value" Log kills < 1 elixir of enemy bodies outright (half its cost)


def kill_value(lg):
    """elixir of enemy bodies the Log kills by itself (hp at the crossing <= LOG_DMG)."""
    return sum(v for k, hp, mx, after, killed, v, b in lg['hits'] if 0 < hp <= LOG_DMG)


def kind(lg):
    if lg['n_hit'] == 0:
        return 'chip' if lg['tower'] else 'empty'
    return 'low' if kill_value(lg) < LOW else 'fair' if kill_value(lg) < 2 else 'good'


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float('nan')


def summary(rows, label):
    L = [lg for r in rows for lg in r['logs']]
    Lm = [lg for lg in L if not lg['forced']]
    out = [f'## {label}: {len(rows)} matches, {len(L)} confirmed Logs ({sum(lg["forced"] for lg in L)} forced by a rule)']
    if not rows:
        return out
    mins = sum(r['ticks'] for r in rows) / 20 / 60
    lpm = [len(r['logs']) for r in rows]
    ci = boot(lpm, mean)
    osh = mean(r['log_out_share'] for r in rows if r.get('log_out_share') is not None)
    out.append(f'- Logs / match {mean(lpm):.2f} [{ci[0]:.2f}, {ci[1]:.2f}], / minute {len(L)/mins:.2f}; '
               f'win rate {share(rows, lambda r: bool(r["won"])):.3f}; Log out of hand on {osh:.3f} of decisions')
    if Lm:
        k = [kind(lg) for lg in Lm]
        out.append(f'- Log kinds (n {len(Lm)}): ' + ', '.join(f'{c} {k.count(c)/len(k):.3f}' for c in ('good', 'fair', 'low', 'chip', 'empty'))
                   + f'; median kill value {sorted(map(kill_value, Lm))[len(Lm)//2]:.2f}; hit a bait card {share(Lm, lambda lg: lg["bait_hit"]):.3f}')
        bk = sorted(lg['back_s'] for lg in L if lg['back_s'] is not None)
        if bk:
            out.append(f'- Log back in hand after: median {bk[len(bk)//2]:.1f} s, p25 {bk[len(bk)//4]:.1f}, p75 {bk[3*len(bk)//4]:.1f}')
        top = defaultdict(int)
        for lg in Lm:
            if kind(lg) == 'low':
                for key in lg['keys']:
                    top[key] += 1
        out.append('  - low-value Logs most often crossed: ' + ', '.join(f'{a} {b}' for a, b in sorted(top.items(), key=lambda kv: -kv[1])[:8]))
        for tag, f in (('CORE bait revealed before the Log', lambda lg: lg['core_revealed']),
                       ('no CORE bait revealed', lambda lg: not lg['core_revealed'])):
            s_ = [lg for lg in Lm if f(lg)]
            if s_:
                out.append(f'  - {tag}: n {len(s_)}, low-value {share(s_, lambda lg: kind(lg) == "low"):.3f}, chip {share(s_, lambda lg: kind(lg) == "chip"):.3f}, '
                           f'good {share(s_, lambda lg: kind(lg) == "good"):.3f}, hit a bait card {share(s_, lambda lg: lg["bait_hit"]):.3f}')
    for tag, keys in (('CORE', CORE), ('EXT', EXT)):
        bt = [b for r in rows for b in r['bait'] if b['card'] in keys and b['hand_known']]
        if not bt:
            continue
        inn = [b for b in bt if b['log_in_hand']]
        outh = [b for b in bt if not b['log_in_hand']]

        def dm(xs):
            return mean(b['dmg'] for b in xs)
        lo, hi = (boot(outh, dm) if outh else (0, 0)), (boot(inn, dm) if inn else (0, 0))
        out.append(f'- {tag} bait plays {len(bt)} ({len(bt)/len(rows):.2f}/match): Log OUT of hand {len(outh)} '
                   f'({len(outh)/len(bt):.3f}), mean own-tower dmg {dm(outh):.0f} [{lo[0]:.0f}, {lo[1]:.0f}]; Log IN hand {len(inn)}, '
                   f'{dm(inn):.0f} [{hi[0]:.0f}, {hi[1]:.0f}]; within 5 s after one of our Logs '
                   f'{share(bt, lambda b: b["since_log_s"] is not None and b["since_log_s"] <= 5):.3f}')
        per = defaultdict(list)
        for b in bt:
            per[b['card']].append(b)
        out.append('  - per card (plays, out-of-hand share, dmg out / in): ' + '; '.join(
            f'{c} {len(v)} {share(v, lambda b: not b["log_in_hand"]):.2f} '
            f'{dm([b for b in v if not b["log_in_hand"]]):.0f}/{dm([b for b in v if b["log_in_hand"]]):.0f}'
            for c, v in sorted(per.items(), key=lambda kv: -len(kv[1]))))
        pm = [sum(b['dmg'] for b in r['bait'] if b['card'] in keys and b['hand_known'] and not b['log_in_hand']) for r in rows]
        ci = boot(pm, mean)
        out.append(f'  - {tag} punish damage per match while Log out of hand: mean {mean(pm):.0f} [{ci[0]:.0f}, {ci[1]:.0f}]')
    rev = [r for r in rows if r['core_revealed'] is not None]
    out.append(f'- matches where the opponent revealed a CORE bait card: {len(rev)} ({len(rev)/len(rows):.3f}), '
               f'win {share(rev, lambda r: bool(r["won"])):.3f} vs '
               f'{share([r for r in rows if r["core_revealed"] is None], lambda r: bool(r["won"])):.3f} without')
    G = [g for r in rows for g in r['ground'] if g['log_in_hand']]
    if G:
        out.append(f'- enemy ground-troop plays while our Log was in hand: {len(G)}; Logged within 12 s {share(G, lambda g: g["logged"]):.3f} '
                   f'(cost <= 3: {share([g for g in G if g["cost"] <= 3], lambda g: g["logged"]):.3f}, '
                   f'>= 4: {share([g for g in G if g["cost"] >= 4], lambda g: g["logged"]):.3f})')
    return out


def by_win(rows):
    """Within-matchup relation (CORE-revealed matches): Log-out punish damage and low-value share vs win."""
    rev = [r for r in rows if r['core_revealed'] is not None]
    if not rev:
        return []
    out = []
    for won in (True, False):
        s = [r for r in rev if bool(r['won']) == won]
        if not s:
            continue
        dm = [sum(b['dmg'] for b in r['bait'] if b['card'] in CORE and not b['log_in_hand']) for r in s]
        lg = [lg for r in s for lg in r['logs'] if not lg['forced']]
        out.append(f'  - CORE-revealed {"WINS" if won else "LOSSES"} n {len(s)}: Log-out CORE punish dmg/match {sum(dm)/len(s):.0f}, '
                   f'Logs/match {sum(len(r["logs"]) for r in s)/len(s):.2f}, low-value {share(lg, lambda x: kind(x) == "low"):.3f}')
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--since', default='20261013_000000')
    ap.add_argument('--out', default=str(Path(__file__).with_name('per_match.jsonl')))
    ap.add_argument('--from-out', action='store_true', help='summarise an existing --out file (no log parsing)')
    a = ap.parse_args(argv)
    if a.from_out:
        rows = [json.loads(x) for x in open(a.out, encoding='utf-8')]
    else:
        import card_use as CU
        results = CU.results()
        rows = []
        with open(a.out, 'w', encoding='utf-8') as fo:
            for p in sorted(LOGS.glob('live_play_2026*.jsonl')):
                if p.stem < 'live_play_' + a.since:
                    continue
                try:
                    r = analyse(p, results)
                except Exception as e:                       # noqa: BLE001 -- a broken log is skipped, counted
                    print('skip', p.name, type(e).__name__, e, file=sys.stderr)
                    continue
                if r:
                    rows.append(r); fo.write(json.dumps(r) + '\n')
    marks = defaultdict(list)
    for r in rows:
        marks[r['mark']].append(r)
    for mk, rs in sorted(marks.items(), key=lambda kv: min(r['match'] for r in kv[1])):
        if len(rs) < 20:
            continue
        print('\n'.join(summary(rs, mk) + by_win(rs)))
        print()
    print('\n'.join(summary(rows, 'ALL icebow main-account') + by_win(rows)))


if __name__ == '__main__':
    main(sys.argv[1:])
