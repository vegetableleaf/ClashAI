"""Q4/Q5 from eval rows: presses per IW deployment, deploy->press delay, presses before any IW landed, repeat presses
inside one deployment, press tick by phase (1x <2400, 2x <4800, OT)."""
import json,glob,sys,statistics as st
from collections import Counter
R=sys.argv[1]
for arm in ("cue_ab","cxxxviii"):
    rows=[]
    for f in glob.glob(f"{R}/eval/{arm}_74*/D3/*/matches.jsonl"): rows+=[json.loads(l) for l in open(f)]
    delays=[];orphan=0;multi=0;tot=0;phase=Counter();over=0;elix=[]
    for r in rows:
        dep=[(p[1],p[4]) for p in r['own_plays'] if p[2]=='ice_wizard' and p[3]]   # landing tick, elixir at play
        pr=[t for t,c in r['own_presses'] if c=='IceWizard']
        np_=sum(r['ability_presses'].get(str(r['learner_side']),{}).values()); nd=r['ability_deployments'].get(str(r['learner_side']),{}).get('IceWizard',0)
        over+= np_>nd
        used=Counter()
        for t in pr:
            tot+=1; phase['1x' if t<2400 else '2x' if t<4800 else 'OT']+=1
            prev=[d for d,_ in dep if d<=t]
            if not prev: orphan+=1; continue
            d=max(prev); delays.append((t-d)/20); used[d]+=1
        multi+=sum(v-1 for v in used.values() if v>1)
    q=st.quantiles(delays,n=10)
    print(arm,"presses",tot,"orphan(no prior IW landing)",orphan,"repeat presses in one deployment",multi,"matches presses>deploys",over)
    print("   deploy->press s: median",round(st.median(delays),2),"deciles",[round(x,1) for x in q],"share<=1s",round(sum(d<=1 for d in delays)/len(delays),3))
    print("   by phase",{k:round(v/len(rows),3) for k,v in phase.items()},"per match")
