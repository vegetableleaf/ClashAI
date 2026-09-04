"""L52: compare patched sim batches against the L51 baseline and the real/engine outcomes."""
import json, sys
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet")
def load(d):
    return {json.loads(l)['tag']: json.loads(l) for l in (ROOT / d / "summary.jsonl").read_text().splitlines() if l.strip()}
A = load('L51/simbatch')
eng = {}
for p in (ROOT / "ext/batch").glob("replay_*.json"):
    e = json.loads(p.read_text()); eng[p.stem.replace("replay_", "")] = e.get("final", {}).get("crowns")
runs = [('base', 'L51/simbatch'), ('spell_edge', 'L52/simbatch_spelledge'), ('corner', 'L52/simbatch_corner_buildings'),
        ('edge+corner', 'L52/simbatch_spell_edgepatchcorner_buildings'), ('hidden_pull', 'L52/simbatch_hidden'), ('all3', 'L52/simbatch_all3')]
for nm, d in runs:
    try: S = load(d)
    except Exception as e: print(nm, 'ERR', e); continue
    n = len(S); cm = sum(1 for r in S.values() if r['crowns_match']); wm = sum(1 for r in S.values() if r['winner_match'])
    w1 = sum(1 for r in S.values() if r['crowns'] and r['crowns'][1] > r['crowns'][0]); w0 = sum(1 for r in S.values() if r['crowns'] and r['crowns'][0] > r['crowns'][1])
    c0 = sum(r['crowns'][0] for r in S.values()); c1 = sum(r['crowns'][1] for r in S.values())
    ch = sum(1 for t in A if A[t]['crowns'] != S[t]['crowns'])
    se = sum(1 for t in S if eng.get(t) is not None and S[t]['crowns'] == eng[t])
    print(f"{nm:12s} n={n} crowns_match {cm} {100*cm/n:.1f}%  winner {wm} {100*wm/n:.1f}%  wins s0/s1 {w0}/{w1}  crowns/side {c0/n:.2f}/{c1/n:.2f}  ==engine {se}  changed vs base {ch}")
