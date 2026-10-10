"""Owner 10-10: under threat the bot Logs / Tornados to DELAY instead of building a defence (Tesla, Knight, IW).
Per live play decision: card, p_play vs the base gate tau, hazard/forced flags. A play with p_play < base tau only
happened because a threatened/hazard rule lowered the bar. Split: delay spells (Log, Tornado) vs defenders."""
import glob, json
from collections import Counter
D = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
DELAY, DEF = {'Log', 'Tornado'}, {'Tesla', 'Knight', 'IceWizard', 'Skeletons'}
c = Counter(); keys = set()
for f in sorted(glob.glob(D + 'live_play_20261009_*.jsonl') + glob.glob(D + 'live_play_20261010_*.jsonl')):
    for l in open(f, encoding='utf-8', errors='replace'):
        if not l.startswith('{"event": "decision"'): continue
        d = json.loads(l); dc = d.get('decision') or {}
        if not dc.get('play'): continue
        n = dc.get('name'); grp = 'delay' if n in DELAY else ('def' if n in DEF else None)
        if grp is None: continue
        keys |= set(dc)
        pp, tau = dc.get('p_play', d.get('p_play')), dc.get('gate_tau', d.get('gate_tau', 0.35))
        below = pp is not None and tau is not None and pp < 0.35
        rule = bool(dc.get('hazard_play') or dc.get('forced') or d.get('hazard_play') or d.get('forced'))
        c[grp, 'n'] += 1; c[grp, 'below_base_tau'] += below; c[grp, 'rule_flag'] += rule
        c[grp, 'why=' + str(dc.get('why'))] += 1
for g in ('delay', 'def'):
    n = c[g, 'n']
    print(f"{g}: plays {n} | p_play < 0.35 (only played because the bar was lowered) {c[g, 'below_base_tau'] / max(n, 1):.1%} | hazard/forced flag {c[g, 'rule_flag'] / max(n, 1):.1%}")
    print('   ', sorted(((k[1], v) for k, v in c.items() if k[0] == g and k[1].startswith('why=')), key=lambda x: -x[1])[:5])
print('decision keys:', sorted(keys)[:30])
