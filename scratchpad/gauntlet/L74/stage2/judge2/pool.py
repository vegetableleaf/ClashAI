import json,sys
sys.path.insert(0,"C:/Users/benpe/ClashBot")
d=json.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/mvp/decks_hog_eval.json"))
print(type(d), (list(d.keys())[:5] if isinstance(d,dict) else len(d)))
e=d if isinstance(d,list) else d.get("decks",d)
print(len(e)); print(e[0] if isinstance(e,list) else list(e.items())[0])
