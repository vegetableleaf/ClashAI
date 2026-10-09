"""L74 runover, pass 2: cache.pkl -> tower-fall episodes, run-overs, identity census (Q1, Q2 live side).

  cd C:/Users/benpe/ClashBot && icebow/.venv/Scripts/python.exe <worktree>/scratchpad/gauntlet/L74/runover/analyze.py
Writes episodes.jsonl + matches.jsonl next to this file and prints the tables.
Definitions (own frame: my king (9,3), my half y < 16):
  fall      = first state where my tower's HP <= 0, or (princess) it is missing while my king is still alive.
  push      = enemy body value (card elixir x max_hp / largest max_hp of that card in the match) >= 2 on my half in the
              falling tower's lane (king: anywhere); t0 = earliest state of the chain ending at the fall, gaps <= 3 s.
  run-over  = fall - t0 <= RUN_S (20 s; also reported at 10/15/30).
  under fire = my tower HP lower than at the previous state. 'gate hold' = under fire, a defensive card (not X-Bow,
              not Rocket) affordable at raw elixir, and the decision did not play.
"""
import os, sys, json, pickle, collections, statistics, datetime, bisect
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
sys.path.insert(0, '.')
from pipeline import vocab
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, 'scratchpad/gauntlet/L74/loss_review')
import review as V   # ladder_results / nav_outcomes (read-only)

TPS = 20.0
RUN_S = 20.0
DEF = {'Log', 'Tornado', 'IceWizard', 'Tesla', 'Knight', 'Skeletons'}
TPOS = {'mK': (9.0, 3.0), 'mL': (3.5, 6.5), 'mR': (14.5, 6.5)}
CAT = json.load(open(V.CATALOG))['cards']
COST = {c['display_name']: c['elixir'] for c in CAT}


def lane_of_x(x): return 'L' if x < 7.5 else ('R' if x > 10.5 else 'C')


def family(ck):
    if 'towerref_w2' in ck: return 'towerref_w2'
    if 'barrel2k_cellref' in ck: return 'stack2k_cellref'
    if 'r1e31' in ck: return 'R1e'
    return ck.replace('.pt', '')


def era(st):
    o = st.get('opts') or {}
    return 'bundle2' if o.get('lethal_rocket') == 'ot_behind' and o.get('xbow_dead_lane') == 'block' else 'pre'


def falls(S, pre='m'):
    """{slot: fall state index} for my ('m') or enemy ('e') towers."""
    out = {}
    k = pre + 'K'
    seen = set()
    for i, s in enumerate(S):
        tw = s[4] if pre == 'm' else s[5]
        for sl, hp in tw.items():
            if hp > 0: seen.add(sl)
            if hp <= 0 and sl not in out: out[sl] = i
        kalive = tw.get(k, 0) > 0
        for sl in (pre + 'L', pre + 'R'):
            if sl in seen and sl not in out and sl not in tw and kalive:
                # missing while the king stands: confirm it stays missing for the next 2 states
                if all(sl not in (S[j][4] if pre == 'm' else S[j][5]) for j in range(i, min(i + 3, len(S)))):
                    out[sl] = i
    if k in out:      # king down = all three
        for sl in (pre + 'L', pre + 'R'):
            out.setdefault(sl, out[k])
    return out


def run():
    cache = pickle.load(open(os.path.join(HERE, 'cache.pkl'), 'rb'))
    lad = V.ladder_results(); nav = V.nav_outcomes(); nt = [o[0] for o in nav]
    M, E = [], []
    for b, r in sorted(cache.items()):
        st = r.get('start')
        if 'error' in r or not st or st.get('dry') or len(r['S']) < 30: continue
        S = r['S']
        mf, ef = falls(S, 'm'), falls(S, 'e')
        cc = 3 if 'mK' in mf else sum(k in mf for k in ('mL', 'mR'))
        ct = 3 if 'eK' in ef else sum(k in ef for k in ('eL', 'eR'))
        res = (lad.get(b) or [None])[0]
        src = 'ladder' if res else None
        if not res:
            try:
                t = datetime.datetime.strptime(b[10:25], '%Y%m%d_%H%M%S').timestamp() + S[-1][0] / TPS
                k = bisect.bisect_left(nt, t - 20)
                if k < len(nt) and nt[k] < t + 300 and nav[k][1] is not None: res, src = ('WIN' if nav[k][1] else 'LOSS'), 'nav'
            except ValueError: pass
        if not res:
            if ct != cc: res = 'WIN' if ct > cc else 'LOSS'
            else:
                mm = min([v for v in S[-1][4].values()] or [0]); em = min([v for v in S[-1][5].values()] or [0])
                res = 'DRAW' if mm == em else ('WIN' if mm > em else 'LOSS')
            src = 'derived'
        top = collections.Counter()
        for s in S:
            for e in s[6]: top[e[2]] = max(top[e[2]], e[4])
        def val(e): return COST.get(e[2], 1) * (min(1.0, e[4] / top[e[2]]) if e[4] > 0 and top[e[2]] else 1.0)
        opp = sorted({e[2] for s in S for e in s[6] if e[8] is not False and e[2] != '-1'})
        # identity census per match
        unres = collections.Counter(); resl = collections.Counter()
        for s in S:
            for e in s[6]:
                if e[8] is False:
                    key = vocab.engine_key(e[2])
                    (unres if e[6] == key else resl)[(e[2], e[3], int(e[4]), e[6], e[7])] += 1
        mbmax = collections.Counter()
        for s in S:
            c = collections.Counter(s[7])
            for k_, v in c.items(): mbmax[k_] = max(mbmax[k_], v)
        m = dict(file=b, fam=family(st['ckpt']), era=era(st), result=res, src=src, cc=cc, ct=ct, opp=opp, end_tick=S[-1][0],
                 unres={'|'.join(map(str, k)): v for k, v in unres.items()}, resolved={'|'.join(map(str, k)): v for k, v in resl.items()},
                 mb_max={k: v for k, v in mbmax.items() if v >= 3})
        M.append(m)
        T = [s[0] for s in S]
        plays = [(t, n, xy) for (t, n, xy, el, p, fo) in r['plays'] if t is not None]
        seen_slot_fall = set()
        for sl, i_f in sorted(mf.items(), key=lambda x: x[1]):
            if sl != 'mK' and 'mK' in mf and mf['mK'] == i_f: continue      # princess counted by the king fall
            lane = sl[1]
            def reg(e): return e[1] < 16 and (lane == 'K' or (e[0] < 9) == (lane == 'L'))
            def threat(s): return sum(val(e) for e in s[6] if reg(e))
            i0, j, last = i_f, i_f, i_f
            while j >= 0:
                if threat(S[j]) >= 2.0: i0, last = j, j
                elif (S[last][0] - S[j][0]) > 3 * TPS: break
                j -= 1
            tf, t0 = S[i_f][0], S[i0][0]
            dur = (tf - t0) / TPS
            win = S[i0:i_f + 1]
            el0 = S[i0][1]
            gate_s = broke_s = play_s = fire_s = 0.0
            gate_p, gate_tau, held = [], [], collections.Counter()
            for k_ in range(1, len(win)):
                s, sp = win[k_], win[k_ - 1]
                tw = s[4]; twp = sp[4]
                hp = tw.get(sl, 0); hpp = twp.get(sl, 0)
                under = hp < hpp or (lane != 'K' and tw.get('mK', 1e9) < twp.get('mK', 1e9))
                dt = min(s[0] - sp[0], TPS) / TPS
                if not under: continue
                fire_s += dt
                el = s[1] or 0
                aff = [h[0] for h in s[2] if h[0] in DEF and (h[1] or 99) <= el + 0.05]
                play, p, tau = s[3][0], s[3][1], s[3][2]
                if play: play_s += dt
                elif aff:
                    gate_s += dt; gate_p.append(p); gate_tau.append(tau); held.update(set(aff))
                else: broke_s += dt
            pl = [(t, n, lane_of_x(xy[0] * 18.0) if xy else '?') for t, n, xy in plays if t0 - 2 * TPS <= t <= tf]
            pre = [n for t, n, xy in plays if t0 - 12 * TPS <= t < t0 - 2 * TPS]
            in_lane = sum(1 for _, n, l in pl if n != 'Xbow' and (lane == 'K' or l == lane))
            # attackers near the tower in the last 3 s
            tx, ty = TPOS[sl]
            att = collections.Counter(); att_child_un = att_child_res = att_n = 0
            for s in S[max(0, i_f - 6):i_f + 1]:
                for e in s[6]:
                    if (e[0] - tx) ** 2 + (e[1] - ty) ** 2 <= 49:
                        att_n += 1; att[e[2]] += 1
                        if e[8] is False:
                            if e[6] == vocab.engine_key(e[2]): att_child_un += 1
                            else: att_child_res += 1
            E.append(dict(file=b, fam=m['fam'], era=m['era'], result=res, cc=cc, slot=sl, tick=tf, t0=t0, dur=round(dur, 1),
                          el0=el0, el_min=min((s[1] or 0) for s in win), fire_s=round(fire_s, 1), gate_s=round(gate_s, 1),
                          broke_s=round(broke_s, 1), play_s=round(play_s, 1),
                          gate_p_med=statistics.median([x for x in gate_p if x is not None] or [-1]),
                          gate_tau_med=statistics.median([x for x in gate_tau if x is not None] or [-1]),
                          held=dict(held), plays=[(n, l) for _, n, l in pl], plays_in_lane=in_lane, pre=pre, pre_cost=sum(COST.get(n, 0) for n in pre),
                          att=dict(att.most_common(6)), att_n=att_n, att_child_unres=att_child_un, att_child_res=att_child_res,
                          opp=opp))
    with open(os.path.join(HERE, 'matches.jsonl'), 'w') as fh:
        for m in M: fh.write(json.dumps(m) + '\n')
    with open(os.path.join(HERE, 'episodes.jsonl'), 'w') as fh:
        for e in E: fh.write(json.dumps(e) + '\n')
    print(f'matches {len(M)} episodes {len(E)} -> matches.jsonl / episodes.jsonl')


if __name__ == '__main__':
    run()
