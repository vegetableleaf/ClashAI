"""ot_behind on the live archive: per match with a REGULATION fire (parity_otb_reg.json from parity_log.py
--mode=ot_behind), the first fire tick / target and the match outcome (L74 loss_review matches.jsonl: crowns, dur_s,
tiebreak_min); plus the loss-review set 'regulation-end loss with the enemy's lowest tower <= 497' and how many of
those the rule would have fired in.  python otb_archive.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
reg = json.load(open(os.path.join(HERE, 'parity_otb_reg.json')))
rows = {r['file']: r for r in map(json.loads, open('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/loss_review/matches.jsonl'))}


def ending(r):
    if r['crowns_opp'] >= 3 or r['crowns_me'] >= 3:
        return '3-crown'
    if r['dur_s'] < 186:
        return 'regulation end'
    return 'OT'


def result(r):
    return 'win' if r['crowns_me'] > r['crowns_opp'] else 'loss' if r['crowns_me'] < r['crowns_opp'] else 'draw'


print('match | first reg fire tick (lane, hp) | fires | outcome (me-opp, ending)')
for f, fires in sorted(reg.items()):
    r = rows.get(f)
    o = f"{result(r)} {r['crowns_me']}-{r['crowns_opp']} {ending(r)} dur {r['dur_s']:.0f}s" if r else 'not in loss review'
    print(f'{f} | {fires[0][0]} ({fires[0][1]}, {fires[0][2]}) | {len(fires)} | {o}')
short = [r for r in rows.values() if r.get('valid_state') and result(r) == 'loss' and ending(r) == 'regulation end'
         and 0 < ((r.get('tiebreak_min') or {}).get('opp') or 0) <= 497]
print(f'\nloss-review regulation-end losses with the enemy lowest tower <= 497: {len(short)}; ot_behind fires in '
      f'{sum(r["file"] in reg for r in short)}: {[r["file"] for r in short if r["file"] in reg]}')
print('  without a fire:', [(r['file'], (r.get('tiebreak_min') or {}).get('opp')) for r in short if r['file'] not in reg])
