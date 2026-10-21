"""W13: the SAME crown-path / decisive-fall definitions on CLX's SIM eval rows (fin15, all16), to say whether the SIM reproduces
(and punishes) the live loss situations.  Sets (C:/Users/benpe/pod_backup_weekend/tonight1020/clx_fin15/):
  w12  = vs W7's calibrated opponent (R6 u20, T .1, decide 40), seeds 741200/742000/743000/744000, 1,920 games (W7OPP_EVAL.md)
  e4   = vs the E4 eval opponents (the promotion gate), same seeds, 1,920 games (tonight1020/RESULTS.md)
SIM rows have no positions: the window features are card / elixir only (X-Bow zone from habits.xbow_y in play order).
SIM tick = game clock (regulation 3600).  -> clx_ranked/sim_rows.json
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/clx_ranked/sim.py
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import anatomy as AN  # noqa: E402  (idle priority on import)

H = AN.H
BASE = Path('C:/Users/benpe/pod_backup_weekend/tonight1020/clx_fin15')
SETS = {'w12': 'w12_clx_fin15/w12_clx_fin15_7*/D3/*/matches.jsonl', 'e4': 'eval/clx_fin15_7*_fin15/D3/*/matches.jsonl'}
REG = 3600


def xzone(y):
    return 'xbow_' + AN.I.xtype(y * 32) if y is not None else 'xbow_unknown'


def row(j, s):
    win = {'win': 1.0, 'loss': 0.0}.get(j['outcome'], 0.5)
    seq = []
    for f in j['crown']['falls']:
        seq.append((f['tick'], 'opp' if f['who'] == 'foe' else 'own', 'P'))
    end = j['crown']['end']
    oc, tc = end['crowns']
    if end['king'] <= 0:
        seq.append((end['tick'], 'own', 'K'))
    if oc == 3:
        seq.append((end['tick'], 'opp', 'K'))
    our = their = 0
    led = trailed = False
    for t, who, sl in seq:
        if sl == 'K':
            continue
        our += who == 'opp'
        their += who == 'own'
        led |= our > their
        trailed |= their > our
    dec = AN._decisive(seq) if win == 0.0 else None
    ph = None if dec is None else AN.phase_of(dec[0])
    opp_deck = {H.norm(c) for c in j['opp_deck']}
    r = dict(set=s, key=f"{j['seed']}:{j['tag']}:{j['learner_side']}", win=win, end_s=round(j['end_tick'] * .05, 1),
             ot=j['end_tick'] > REG + 10, our_cr=oc, their_cr=tc, led=led, trailed=trailed, reached_11=AN._reached_11(seq),
             king_lost=any(w == 'own' and sl == 'K' for _, w, sl in seq),
             first=next((w for _, w, sl in seq if sl != 'K'), None),
             first_s=next((round(t * .05, 1) for t, w, sl in seq if sl != 'K'), None),
             path=AN.path_label(win, led, trailed, ph, win == 0.0 and dec is None),
             wincon=AN.wincon(opp_deck), arch=AN.A.classify([c.replace('_', '') for c in opp_deck]))
    o3 = j.get('o3_plays') or {}
    if o3:
        own_i = [dict(tick=p[1], card=H.norm(p[2])) for p in j['own_plays'] if p[3]]
        opp_i = [dict(tick=tt, card=H.norm(c)) for tt, c in o3.get('opp', [])]
        r['intensity'] = AN.intensity(own_i, opp_i, j['end_tick'])
    if dec is not None:
        t = dec[0]
        xy = iter(j['habits'].get('xbow_y') or [])
        plays = []
        for p in j['own_plays']:
            if not p[3]:
                continue
            c = H.norm(p[2])
            z = xzone(next(xy, None)) if c == 'x_bow' else 'rocket' if c == 'rocket' else 'other'
            plays.append((p[1], c, z, p[4]))
        w = [p for p in plays if t - AN.WIN_T <= p[0] <= t]
        pre = [p for p in plays if t - AN.WIN_T - AN.PRE_T <= p[0] < t - AN.WIN_T]
        off = lambda ps: sum(H.cost(c) for _, c, z, _ in ps if z in ('xbow_bridge', 'xbow_pocket') or c == 'rocket')  # noqa: E731
        opp = [(tt, H.norm(c)) for tt, c in (j.get('o3_plays') or {}).get('opp', []) if t - AN.WIN_T <= tt <= t]
        r['decisive'] = dict(t=t, clock_s=round(t * .05, 1), phase=ph, slot=dec[2], own_off_w=off(w), own_off_pre=off(pre),
                             own_spend_w=sum(H.cost(c) for _, c, _, _ in w), own_cards=[(tt - t, c, z) for tt, c, z, _ in w],
                             el_play_min=min((e for *_, e in w), default=None),
                             opp_cards=[(tt - t, c) for tt, c in opp],
                             opp_troop_el=sum(H.cost(c) for _, c in opp if H.kind(c) != 'spell') if opp else None)
    return r


def main():
    rows = []
    for s, pat in SETS.items():
        fs = sorted(glob.glob(str(BASE / pat)))
        n0 = len(rows)
        for f in fs:
            for line in open(f):
                rows.append(row(json.loads(line), s))
        print(s, len(fs), 'files', len(rows) - n0, 'games')
    json.dump(rows, open(HERE / 'sim_rows.json', 'w'), indent=0)


if __name__ == '__main__':
    main()
