"""Pro icebow sides from corpus_v6/icebow_public_v1 re-drives: per-frame emptiness/elixir + both sides' play logs (own frame, own edge y=0)."""
import json, glob, pickle, os
BASE = {"Xbow", "Skeletons", "Log", "Knight", "Tesla", "Tornado", "IceWizard", "Rocket"}
out = []
fs = sorted(glob.glob('C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json'))
for i, f in enumerate(fs):
    try: d = json.load(open(f))
    except Exception: continue
    decks = {s: {c.split('@')[0] for c in d['final_decks'][s]} for s in '01'}
    for s in (0, 1):
        if decks[str(s)] != BASE: continue
        tf = (lambda x, y: (x / 1000, y / 1000)) if s == 0 else (lambda x, y: (18 - x / 1000, 32 - y / 1000))
        fr = []
        for F in d['frames']:
            en = [e for e in F['entities'] if str(e[3]) != '-1']
            mine = [(e[3],) + tf(e[1], e[2]) for e in en if e[0] == s]
            opp = [(e[3],) + tf(e[1], e[2]) for e in en if e[0] != s]
            fr.append((int(F['tick']), F['elixir'][s], mine, opp))
        plays = []
        for p in d['log']:
            if not p.get('accepted'): continue
            X, Y = tf(p['x'], p['y']) if p.get('x') is not None else (None, None)
            plays.append(dict(t=p['tick'], me=p['side'] == s, card=p['card'], X=X, Y=Y, cost=p.get('cost'), el=p.get('elixir_before'), ability='ability' in p))
        out.append(dict(id=os.path.basename(f)[7:19] + f'_s{s}', side=s, end=d['final']['tick'], frames=fr, plays=plays, opp_deck=sorted(decks[str(1 - s)])))
    if i % 200 == 0: print(i, len(fs), len(out), flush=True)
pickle.dump(out, open('pro_q.pkl', 'wb'))
print('pros', len(out))
