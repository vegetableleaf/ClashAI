"""First-divergence dossier for failing captured fights (laptop, single process, K=0).
usage: python div.py OUT.json MATCH:T0[,T0...] [MATCH:T0...]
Per fight: the card views, every anchor body's hp timeline (live vs SIM) with the attacker that targeted it, and the first
divergence (hp / position / target / presence) of every paired body, live target from the phase-3 rows, SIM target from
target_uid. Derived numbers only (no addresses, no raw capture rows)."""
import json, math, os, sys, tempfile
sys.path.insert(0, os.environ.get('CB', '/workspace/w_r7d/cb'))
from scratchpad.gauntlet.L74.parity import fights as F
from scratchpad.gauntlet.L74.parity.core import load_catalog, ps

catalog, by_name = load_catalog()
CAP, MS, PJ = [], [], {}
_measure, _cut, _read, _bodies = F.measure, F.cut, F.read_match, F.Engine.bodies


def bodies(self, by):
    st, out = _bodies(self, by)
    uid = {}
    rows = [dict(zip(self.F, r)) for r in st['entities']]
    for e, o in zip(rows, out):
        uid[e['uid']] = o['id']
    for e, o in zip(rows, out):
        o['tgt'] = uid.get(e['target_uid']); o['ph'] = e['attack_phase']; o['stun'] = e['stun_ticks']
        o['kb'] = e['knockback_ticks']; o['buffs'] = e['buffs']; o['charge'] = e['charge']
    QF = getattr(self.sim, 'PROJECTILE_FIELDS', None) or ['team', 'x', 'y', 'aim_x', 'aim_y', 'target_uid', 'splash', 'firer_card_id']
    pj = [dict(zip(QF, q)) if isinstance(q, list) else q for q in st.get('projectiles', [])]
    PJ[st['tick']] = [(q['team'], self.cat[q['firer_card_id']]['name'] if isinstance(q.get('firer_card_id'), int) and 0 <= q['firer_card_id'] < len(self.cat) else q.get('firer_card_id'),
                       uid.get(q['target_uid']), round(q['x']/18), round(q['y']/18)) for q in pj]
    return st, out


def measure(rows, setup, flags, cat, stamp):
    CAP.append((rows, setup, dict(flags))); return _measure(rows, setup, flags, cat, stamp)


def read(path):
    m, why = _read(path); MS.append(m); return m, why


F.Engine.bodies, F.measure, F.read_match = bodies, measure, read
nm = lambda bd: bd.get('name') or catalog.get(bd.get('card_id'), {}).get('display_name') or bd['id']


def live_targets(m, rows):
    """tick -> {live id: live target id} from the phase-3 attack rows (joined on tick + generation id in-frame)."""
    out = {}
    for t, live, _ in rows:
        A = m['attacks'].get(t) or m['attacks'].get(t - 1) or m['attacks'].get(t + 1) or {}
        g2id = {bd.get('gen'): bd['id'] for bd in live if bd.get('gen') is not None}
        out[t] = {bd['id']: g2id.get(A[bd['gen']][0]) for bd in live if bd.get('gen') in A}
    return out


def dossier(m, r, rows, setup, flags):
    a = r['anchor']
    pairs = F.initial_pairs(rows, setup, catalog)
    inv = {s: l for l, s in pairs.items() if s}
    LT = live_targets(m, rows)
    at0 = {bd['id'] for bd in rows[0][1]}
    t_end = rows[-1][0]
    mine = []
    for t, live, _ in rows:
        for bd in live:
            if not bd['tower'] and bd['side'] == a['side'] and nm(bd) == a['name'] and bd['id'] not in at0 and bd['id'] not in mine:
                mine.append(bd['id'])
    sim_mine = []
    for t, _, simb in rows:
        for bd in simb:
            if not bd['tower'] and bd['side'] == a['side'] and bd['name'] == a['name'] and bd['id'] not in inv and bd['id'] not in sim_mine \
                    and t > rows[0][0]:
                sim_mine.append(bd['id'])
    out = dict(k=f"{r['match'][10:]}@{r['t0']}", anchor=a, card=dict(live=r['card']['live'], sim=r['card']['sim'][0]),
               events=[(e['tick'], 'own' if e['side'] == r['obs'] else 'opp', e['name'], e['form'], e['source']) for e in r['events']],
               flags={k: v for k, v in flags.items() if not k.startswith(('setup_form_swapped',))}, sim_only=r['sim_only'])
    # per-body first divergence
    first = {}
    last_seen = {}

    def note(lid, kind, t, info):
        if (lid, kind) not in first:
            first[lid, kind] = (t, info)
    streak = {}
    for t, live, simb in rows:
        L = {bd['id']: bd for bd in live}; S = {bd['id']: bd for bd in simb}
        for lid, bd in L.items():
            last_seen[lid] = t
            sid = pairs.get(lid) if not bd['tower'] else lid
            s = S.get(sid) if sid else None
            if bd['tower']:
                if s and abs(s['hp'] - bd['hp']) > 0:
                    note(lid, 'hp', t, (bd['hp'], s['hp']))
                continue
            if sid is None:
                continue
            if s is None:
                note(lid, 'gone_sim', t, (bd['hp'],))
                continue
            for kind, bad, info in (('hp', abs(s['hp'] - bd['hp']) > 0, (bd['hp'], s['hp'])),
                                    ('pos', math.hypot(s['x'] - bd['x'], s['y'] - bd['y']) > 500,
                                     ((round(bd['x']), round(bd['y'])), (round(s['x']), round(s['y'])))),
                                    ('tgt', LT.get(t, {}).get(lid, '?') != '?' and pairs.get(LT[t][lid], LT[t][lid]) != s.get('tgt'),
                                     (nm(L[LT[t][lid]]) + ':' + str(LT[t][lid])[:6] if LT.get(t, {}).get(lid) in L else LT.get(t, {}).get(lid),
                                      (nm(S[s['tgt']]) + ':' + str(inv.get(s['tgt'], s['tgt']))[:6]) if s.get('tgt') in S else s.get('tgt')))):
                c = streak.get((lid, kind), 0) + 1 if bad else 0
                streak[lid, kind] = c
                if c == 2:
                    note(lid, kind, t, info)
        for sid, s in S.items():
            lid = inv.get(sid)
            if lid and lid not in L and not s['tower'] and last_seen.get(lid) is not None:
                note(lid, 'gone_live', t, (s['hp'],))
    div = []
    for (lid, kind), (t, info) in first.items():
        bd = next((b for _, l, _ in rows for b in l if b['id'] == lid), None)
        div.append((t, kind, nm(bd) if bd else lid, bd['side'] if bd else None, str(lid)[:6], info, lid in mine))
    div.sort(key=lambda d: d[0])
    out['div'] = div[:40]
    # anchor bodies: hp timelines with who targets them
    tl = []
    for k in mine + sim_mine:
        sid = pairs.get(k) if not k.startswith('s') else k
        lk = k if not k.startswith('s') else None
        ch, last = [], None
        for t, live, simb in rows:
            Lb = next((b for b in live if b['id'] == lk), None) if lk else None
            Sb = next((b for b in simb if b['id'] == sid), None) if sid else None
            if Lb is None and Sb is None:
                continue
            la = sorted(nm(o) for o in live if LT.get(t, {}).get(o['id']) == lk) if lk else []
            sa = sorted(nm(o) for o in simb if o.get('tgt') == sid) if sid else []
            cur = (Lb and Lb['hp'], Sb and Sb['hp'], tuple(la), tuple(sa))
            if cur != last:
                ch.append((t,) + cur); last = cur
        tl.append(dict(id=str(k)[:8], sim=sid, max_hp=next((b['max_hp'] for _, l, s in rows for b in (l + s) if b['id'] in (k, sid)), None), tl=ch))
    out['anchor_bodies'] = tl
    return out


def main():
    dest = sys.argv[1]
    res = json.load(open(dest)) if os.path.exists(dest) else {}
    for arg in sys.argv[2:]:
        match, ts = arg.split(':')
        T0 = {int(x) for x in ts.split(',')}
        CAP.clear(); MS.clear(); PJ.clear()
        F.cut = lambda m, e, w: [f for f in _cut(m, e, w) if f['t0'] in T0]
        out = tempfile.mkdtemp(); os.makedirs(out + '/matches')
        F.run_match(os.environ.get('LIVE_DIR', str(ps.LIVE)) + f'/live_play_{match}.jsonl', 240, out, 0)
        d = json.load(open(out + f'/matches/live_play_{match}.json'))
        m = MS[0]
        for r, (rows, setup, flags) in zip(d['fights'], CAP):
            if 'card' not in r:
                print('ERR', r.get('t0'), r.get('error'), flush=True)
                continue
            r['match'] = d['summary']['match']
            x = dossier(m, r, rows, setup, flags)
            if True:
                pairs = F.initial_pairs(rows, setup, catalog); inv = {s: l for l, s in pairs.items() if s}
                LT = live_targets(m, rows)
                x['rows'] = [(t, [(bd['id'][:8], nm(bd), bd['side'], bd['hp'], round(bd['x']), round(bd['y']), (LT.get(t, {}).get(bd['id']) or '')[:8], bd.get('state')) for bd in live],
                              [(str(inv.get(s['id'], s['id']))[:8], s['name'] if not s['tower'] else s['id'], s['side'], s['hp'], round(s['x']), round(s['y']),
                                str(inv.get(s.get('tgt'), s.get('tgt')) or '')[:8], s.get('ph'), s.get('stun'), s.get('kb'), s.get('charge')) for s in simb]) for t, live, simb in rows]
                cn = lambda cid: (catalog.get(cid) or {}).get('display_name', cid)
                x['proj'] = {t: dict(live=[(q[0], cn(q[3]), (q[7] or '')[:8], (q[8] or '')[:8], round(q[1]), round(q[2])) for q in m['proj'].get(t, ())],
                                     sim=[(q[0], q[1], str(inv.get(q[2], q[2]) or '')[:8], q[3], q[4]) for q in PJ.get(t, ())]) for t, _, _ in rows}
            res[x['k'] + ':' + r['anchor']['name']] = x
            print(x['k'], r['anchor']['name'], 'L', x['card']['live'], 'S', x['card']['sim'], flush=True)
    json.dump(res, open(dest, 'w'), default=str)


main()
