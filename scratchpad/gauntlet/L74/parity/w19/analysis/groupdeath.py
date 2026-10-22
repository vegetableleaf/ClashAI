"""Unseen / mis-dated SPELL signature in failing troop fights: >= 2 anchor bodies die on the SAME live tick (a splash kill),
and the SIM does not kill them within DEATH_TOL of it (or kills them together at another tick). Split by whether an opponent
spell was replayed (spell_seen / inferred Zap) within 60 ticks of the live group death, and by era.
  python groupdeath.py RUN_DIR [RUN_DIR ...]"""
import glob, json, os, sys
from collections import Counter
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
FORM = ('', ' evo', ' hero')
cnt = Counter(); tot = Counter(); cards = Counter(); spells = Counter()
for run in sys.argv[1:]:
    for p in sorted(glob.glob(run + '/matches/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped') or not s.get('phase3b_births'):
            continue
        era = 'L16' if s['match'][10:23] >= '20261019_1402' else 'pre'
        for r in d['fights']:
            c = r.get('card')
            if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
                continue
            tot[era] += 1
            L, S = c['live'], c['sim'][0]
            if L['spell'] or F.card_agree(L, S)[0]:
                continue
            cnt[era, 'failing troop'] += 1
            dl = Counter(x for x in L['own'] if x is not None)
            grp = [t for t, n in dl.items() if n >= 2]
            if not grp:
                continue
            t = min(grp)
            sim_near = sum(1 for y in S['own'] if y is not None and abs(y - t) <= F.DEATH_TOL)
            if sim_near >= dl[t]:
                continue
            lab = ('own ' if r['own'] else 'opp ') + r['anchor']['name'] + FORM[r['anchor']['form']]
            opp_sp = [e for e in r['events'] if e['side'] != r['anchor']['side'] and e['source'] in ('spell_seen', 'zap_unseen', 'unseen_zap')
                      and abs(e['tick'] - t) <= 60]
            key = 'opp spell replayed within 60 ticks' if opp_sp else 'NO opp spell replayed'
            cnt[era, key] += 1; cards[era, lab] += 1
            for e in opp_sp:
                spells[era, e['name'], 'seen after the group death' if e['tick'] > t else 'seen before']+= 1
for k in sorted(cnt):
    print(k, cnt[k])
print('strict fights per era', dict(tot))
print('anchor cards:', cards.most_common(16))
print('replayed opp spells near the group death:', spells.most_common(20))
