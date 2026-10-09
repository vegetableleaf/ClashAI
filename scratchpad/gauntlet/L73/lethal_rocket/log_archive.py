"""lethal_log on the live archive: the wired live rule (GenPilot.lethal_rocket, --lethal-rocket ot_behind --lethal-log on)
on every logged decision snapshot (no model). Per match with a LOG fire: first fire (tick, phase, target), what the bot
actually played in the next 3 s, whether that enemy tower fell later and how many ticks after, and the outcome (L74
loss_review matches.jsonl).  python log_archive.py "<glob>" """
import glob, json, os, sys
from types import SimpleNamespace
from collections import Counter
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline.decision_options import DecisionOptions, phase_index
from pipeline.e1_eval import allowed_slots
from pipeline.live_gen_v2 import GenPilot

pilot = object.__new__(GenPilot)
pilot.decision_options, pilot.grid = DecisionOptions(lethal_rocket='ot_behind', lethal_log='on'), 'lattice'
rows = {r['file']: r for r in map(json.loads, open('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/loss_review/matches.jsonl'))}
tot, out = Counter(), []
for f in sorted(glob.glob(sys.argv[1])):
    ev = []
    for line in open(f):
        try:
            ev.append(json.loads(line))
        except ValueError:
            pass
    dec = [d for d in ev if d.get('event') == 'decision' and 'public' in d]
    if not dec:
        continue
    tot['matches'] += 1
    names = [None] * 8
    for d in dec:
        for h in d['public']['own_hand']:
            if h['deck_index'] >= 0:
                names[h['deck_index']] = h['name']
    first = None
    for d in dec:
        p = d['public']
        side, hdi = p['observer_side'], [h['deck_index'] for h in p['own_hand']]
        me = dict(side=side, elixir_raw=int(p['own_elixir_raw'] * 1e4), next_deck_index=-1, hand_deck_indices=hdi)
        frame = dict(game_tick=p['raw_tick'], entities=p['raw_bodies'],
                     players=[me, dict(side=1 - side, elixir_raw=0, next_deck_index=-1, hand_deck_indices=[-1] * 4)])
        t = p['model_tick'] * 0.05
        allowed = allowed_slots(np.array([h['card'] > 0 for h in p['own_hand']]), [h['cost'] for h in p['own_hand']],
                                int(p['model_own_elixir']))
        hit = pilot.lethal_rocket(frame, dict(names=names, hand_deck_indices=hdi, bs=SimpleNamespace(t_sec=t)), allowed)
        if hit is not None and hit[2].get('card') == 'Log':
            tot['log_fire_decisions'] += 1
            if first is None:
                first = (d, t, hit[2], side)
    if first is None:
        continue
    d, t, target, side = first
    tick = d['tick']
    plays = [e['name'] for e in ev if e.get('event') == 'play' and tick <= e['tick'] <= tick + 60]
    # did an enemy princess at the target HP fall later? (its raw row disappears / hp 0)
    hp0 = target['hp']

    def enemy_princess_hps(dd):
        return sorted(b['hp'] for b in dd['public']['raw_bodies'] if b.get('card_id') == -1 and b['side'] != side
                      and b.get('kind') in (12, 13) and b['max_hp'] < 6000 and abs(b['x'] - 9000) > 1500)
    fell = next((dd['tick'] for dd in dec if dd['tick'] > tick and hp0 not in enemy_princess_hps(dd)
                 and len(enemy_princess_hps(dd)) < len(enemy_princess_hps(d))), None)
    r = rows.get(os.path.basename(f))
    res = (f"{'win' if r['crowns_me'] > r['crowns_opp'] else 'loss' if r['crowns_me'] < r['crowns_opp'] else 'draw'} "
           f"{r['crowns_me']}-{r['crowns_opp']} dur {r['dur_s']:.0f}s") if r else '?'
    ph = 'OT' if phase_index([t])[0] == 2 else 'reg_behind'
    tot[ph] += 1
    out.append(f"{os.path.basename(f)} | {ph} tick {tick} t {t:.1f} {target['lane']} hp {hp0} (dmg {target['damage']}) | "
               f"bot next 3 s: {plays} | tower fell {('+' + str(fell - tick) + ' ticks') if fell else 'no'} | {res}")
print(dict(tot))
print('\n'.join(out))
