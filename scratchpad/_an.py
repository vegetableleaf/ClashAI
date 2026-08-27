import json, math, glob, os, sys
def load(tag):
    d=json.load(open(f'rs_{tag}.json'))
    return d, {r['seed']: r for r in d['records']}
def paired(bt, at, key):
    seeds=sorted(set(bt)&set(at))
    diffs=[at[s][key]-bt[s][key] for s in seeds]
    n=len(diffs); m=sum(diffs)/n
    var=sum((x-m)**2 for x in diffs)/(n-1) if n>1 else 0.0
    sem=math.sqrt(var/n) if n>1 else float('nan')
    return m, sem, (m/sem if sem else float('nan')), n
def wr(t): 
    v=[1.0 if r['outcome']=='win' else 0.0 for r in t.values()]
    return 100*sum(v)/len(v)
bd, bt = load('base')
arms=sys.argv[1:]
print(f"{'arm':10s} {'H':>6} {'N':>3} {'K':>3} {'cells':>5} {'win%':>6} {'tower':>7} | {'dTOWER':>7} {'sem':>5} {'sig':>6} | {'dCROWN':>7} {'sig':>6} | {'dWIN':>6} {'sig':>6} | {'s/m':>5}")
print(f"{'base':10s} {0:>6} {5:>3} {4:>3} {1:>5} {wr(bt):>6.1f} {sum(r['tower_delta'] for r in bt.values())/len(bt):>7.3f}")
for tag in arms:
    try: d,t = load(tag)
    except FileNotFoundError: print(f'{tag}: MISSING'); continue
    mt,st,zt,n = paired(bt,t,'tower_delta')
    mc,sc,zc,_ = paired(bt,t,'crown_delta')
    # paired winrate
    seeds=sorted(set(bt)&set(t))
    wd=[(1.0 if t[s]['outcome']=='win' else 0.0)-(1.0 if bt[s]['outcome']=='win' else 0.0) for s in seeds]
    mw=sum(wd)/len(wd); vw=sum((x-mw)**2 for x in wd)/(len(wd)-1); sw=math.sqrt(vw/len(wd))
    sm=sum(r['wall_s'] for r in t.values())/len(t)
    tw=sum(r['tower_delta'] for r in t.values())/len(t)
    print(f"{tag:10s} {d['horizon']:>6} {d['interval']:>3} {d['topk']:>3} {d.get('cells',1):>5} {wr(t):>6.1f} {tw:>7.3f} | {mt:>+7.3f} {st:>5.3f} {zt:>+6.2f} | {mc:>+7.3f} {zc:>+6.2f} | {100*mw:>+6.1f} {mw/sw:>+6.2f} | {sm:>5.2f}  n={n}")
