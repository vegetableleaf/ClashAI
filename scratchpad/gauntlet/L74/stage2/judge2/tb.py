import glob,json,sys
sys.path.insert(0,"C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate")
import gate_fit; classify=gate_fit.classify
R=json.load(open("gate/live_targets.json"))
for mk,f in (("CXXXVIII",lambda s:s>=13000),("CXXIV",lambda s:12000<=s<13000)):
    rows=[x for x in R if x["mark"]==mk and x["src"]=="ladder" and x["start"] is not None and f(x["start"]) and x["ot"]]
    for g in ("Hog","rest"):
        s=[x for x in rows if x["cls"].startswith("Hog")==(g=="Hog")]
        L=[x for x in s if x["res"]!="WIN"]; t=[x for x in L if x["dur_s"]>=295]
        print("live",mk,g,"OT losses",len(L),"ran to time(>=295s)",len(t))
for pat in ("C:/Users/benpe/pod_backup_weekend/rt35/RT35/cues130_gae_cue_u250_74*/D3/*/matches.jsonl",):
    for g in ("Hog","rest"):
        L=t=0
        for fn in glob.glob(pat):
            for line in open(fn):
                r=json.loads(line); e=r.get("end_tick") or 0
                if e<=3600 or r["outcome"]=="win": continue
                if classify([c.split("@")[0] for c in r["opp_deck"]]).startswith("Hog")!=(g=="Hog"): continue
                L+=1; t+= e>=5990
        print("SIM CXXXVIII",g,"OT non-wins",L,"to time",t)
