import json, time, urllib.request, urllib.parse, sys
BASE="https://clashroyale.fandom.com/api.php"
HDRS={'User-Agent':'icebow-monitor/1.0 (+local)'}
pages=["Goblin Cage","Goblin Giant","Goblin Machine","Goblins","Golem","Guards","Heal Spirit",
"Hog Rider","Hunter","Ice Golem","Ice Spirit","Ice Wizard","Inferno Dragon","Knight","Lava Hound",
"Lumberjack","Lumberjack/Evolution","Magic Archer","Mega Knight","Mega Minion","Miner",
"Mini P.E.K.K.A.","Minion Horde","Minions","Mother Witch","Musketeer"]
cached=json.load(open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_b_fetchlog.json',encoding='utf-8'))
out={}
for p in pages:
    url=BASE+"?action=parse&page="+urllib.parse.quote(p)+"&prop=revid&format=json"
    req=urllib.request.Request(url,headers=HDRS)
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            d=json.loads(r.read().decode('utf-8'))
        live=d.get('parse',{}).get('revid')
        if live is None: live='ERR:'+json.dumps(d.get('error',{}))[:120]
    except Exception as e:
        live='EXC:'+str(e)[:120]
    c=cached.get(p,{})
    crev=c.get('revid') if isinstance(c,dict) else None
    status='SAME' if live==crev else 'CHANGED'
    out[p]={'cached_revid':crev,'live_revid':live,'status':status}
    print(p,'|',crev,'->',live,'|',status,flush=True)
    time.sleep(0.25)
json.dump(out,open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_b_revidcheck.json','w',encoding='utf-8'),indent=1)
