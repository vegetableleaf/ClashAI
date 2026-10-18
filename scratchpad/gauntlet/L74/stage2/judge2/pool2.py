import json,os,time
for f in ("decks_live_train.json","decks_live_eval.json"):
    p="C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/mix/"+f
    d=json.load(open(p)); print(f, time.ctime(os.path.getmtime(p)), json.dumps(d.get("source"))[:400])
