import json,sys,collections
R=[json.loads(l)['f'] for l in open(sys.argv[1]) if l.startswith('{"event": "frame"')]
R=[f for f in R if f.get('game_tick',-1)>=0]
P=[json.loads(l) for l in open(sys.argv[2])]
rt=set(f['game_tick'] for f in R); pt=set(f['game_tick'] for f in P)
print('rec',len(rt),'parity',collections.Counter(t%2 for t in rt),'p3',len(pt),'union',len(rt|pt),'span',min(pt),max(rt))
# compare towers on common ticks
Rm={f['game_tick']:f for f in R}; Pm={f['game_tick']:f for f in P}
com=sorted(rt&pt); eq=0; neq=[]
def key(f): return sorted((e['side'],e['x'],e['y'],e['hp'],e['card_id']) for e in f['entities'])
for t in com:
    if key(Rm[t])==key(Pm[t]): eq+=1
    else: neq.append(t)
print('common',len(com),'entity-equal',eq,'first neq',neq[:10])
print('p3 players',P[0]['players'][:1] if P[0]['players'] else None, sum(1 for f in P if f['players']))
