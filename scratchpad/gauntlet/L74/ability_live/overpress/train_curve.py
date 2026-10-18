import json,sys
p=sys.argv[1]
print("upd matches winrate | ab_dec press_rate p_mean l_ab ent_ep0 acc/match | card_mix_IW")
for l in open(p):
    try: d=json.loads(l)
    except: continue
    if d.get('type')!='update': continue
    a=d.get('ability',{})
    cm=d.get('card_mix',{})
    iw={k:v for k,v in cm.items() if 'ice' in k.lower()} if isinstance(cm,dict) else cm
    print(d['update'],d['matches'],round(d['winrate'],3),'|',a.get('decisions'),round(a.get('press_rate',0),4),round(a.get('p_mean',0),4),round(a.get('l_ab',0),4),round(a.get('ent_ability_ep0',0),4),a.get('accepted_per_match'),'|',iw, round(d.get('plays_per_match',0),2))
