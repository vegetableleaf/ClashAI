"""Per-arm eval press stats from the promotion eval matches.jsonl rows."""
import json,glob,sys,statistics as st
from collections import Counter
R=sys.argv[1]
for arm in ("cue_ab","cxxxviii"):
    rows=[]
    for f in glob.glob(f"{R}/eval/{arm}_74*/D3/*/matches.jsonl"):
        rows+= [json.loads(l) for l in open(f)]
    n=len(rows); w=sum(r['outcome']=='win' for r in rows)
    pr=[sum(r.get('ability_presses',{}).get(str(r['learner_side']),{}).values()) for r in rows]
    dep=[r.get('ability_deployments',{}).get(str(r['learner_side']),{}).get('IceWizard',0) for r in rows]
    ah=[r['ability_head'] for r in rows if r.get('ability_head')]
    fb=Counter(); [fb.update(r.get('ability_fallback_generic',{})) for r in rows]
    endt=[r['end_tick'] for r in rows]
    print(arm,"n",n,"win",round(w/n,4),"press/m",round(sum(pr)/n,3),"IWdeploy/m",round(sum(dep)/n,3),"press/deploy",round(sum(pr)/max(1,sum(dep)),3),
          "end_tick mean",round(st.mean(endt),1),"fallback_generic",dict(fb))
    if ah:
        print("   head decisions/m",round(sum(a['decisions'] for a in ah)/len(ah),2),"head presses/m",round(sum(a['presses'] for a in ah)/len(ah),3),
              "p_mean",round(st.mean(a['p_mean'] for a in ah),4))
    # presses per minute of match
    print("   presses per 1000 ticks",round(1000*sum(pr)/sum(endt),3), "zero-press share", round(sum(p==0 for p in pr)/n,3))
    # press count vs head 'presses' consistency
    if ah: print("   engine-accepted vs head-decided presses", sum(pr), sum(a['presses'] for a in ah))
