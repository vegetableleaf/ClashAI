"""Q1: live Hero IW press cost from live_play logs. Per 'ability' event: the largest single frame-to-frame elixir step
down between the press and its ability_confirmed, regen of that step added back; card plays inside the window excluded."""
import json,glob,statistics as st,sys
RATE=((0,1/56),(2400,1/28),(4800,1/18.6))
def rate(t): return [r for s,r in RATE if t>=s][-1]
steps=[];naive=[];n_play=0;n=0;capped=0
for f in sorted(glob.glob(sys.argv[1])):
    pend=None;frames=[];plays=[]
    for l in open(f):
        try: e=json.loads(l)
        except: continue
        ev=e.get('event')
        if ev=='start': pend=None;frames=[]
        if ev=='frame': frames.append((e['tick'],e['elixir'])); frames=frames[-200:]
        if ev=='play' and pend: pend['plays']+=1
        if ev=='ability': pend={'tick':e['tick'],'el':e['elixir'],'plays':0}
        if ev=='ability_confirmed' and pend:
            n+=1
            if pend['plays']: n_play+=1; pend=None; continue
            w=[fr for fr in frames if pend['tick']-2<=fr[0]<=e['tick']]
            ds=[(a[1]-b[1]+(b[0]-a[0])*rate(a[0]),a,b) for a,b in zip(w,w[1:]) if b[0]>a[0]]
            if ds:
                d=max(ds)[0]; steps.append(d)
                if pend['el']>=9.9: capped+=1
            lat=e['tick']-pend['tick']
            naive.append(e['elixir_drop']+lat*rate(pend['tick']))
            pend=None
q=lambda v:[round(x,3) for x in st.quantiles(v,n=20)[::4]] if len(v)>4 else v
print("confirmed presses",n,"with a card play in the window (excluded)",n_play)
print("largest frame step (+regen): n",len(steps),"median",round(st.median(steps),3),"mean",round(st.mean(steps),3),"5/25/45/65/85 pct",q(steps))
print("  share in [1.8,2.2]",round(sum(1.8<=s<=2.2 for s in steps)/len(steps),3))
print("event drop + latency regen: median",round(st.median(naive),3),"mean",round(st.mean(naive),3))
