import sys
sys.path.insert(0,"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate")
import gate_fit
for name,pat in (("CXXXVIII","C:/Users/benpe/pod_backup_weekend/rt35/RT35/cues130_gae_cue_u250_74*/D3/*/matches.jsonl"),
                 ("u250ctl","C:/Users/benpe/pod_backup_weekend/rt35/RT35/cues130_gae_ctl_u250_74*/D3/*/matches.jsonl")):
    S=gate_fit.sim(pat); print(name,"n",len(S))
    for g in ("Hog","rest"):
        for ot in (False,True):
            s=[r for r in S if r[1].startswith("Hog")==(g=="Hog") and r[2]==ot]
            w=sum(r[0] for r in s); print(f"  {g:4s} {'OT ' if ot else 'reg'} {w}/{len(s)} {w/max(1,len(s)):.1%}")
