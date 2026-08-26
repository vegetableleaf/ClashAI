import json, time, os, sys, urllib.request, urllib.parse
BASE="https://clashroyale.fandom.com/api.php"
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=os.path.join(os.path.dirname(__file__),'..','webcache')
LOG=os.path.join(os.path.dirname(__file__),'..','ledger','r2_troops_b_fetchlog.json')
titles=["Giant Skeleton","Goblin Cage","Goblin Demolisher","Goblin Gang","Goblin Giant",
"Goblin Machine","Goblins","Golem","Guards","Heal Spirit","Hog Rider","Hunter","Ice Golem",
"Ice Spirit","Ice Wizard","Inferno Dragon","Knight","Lava Hound","Lumberjack",
"Lumberjack/Evolution","Magic Archer","Mega Knight","Mega Minion","Miner","Mini P.E.K.K.A.",
"Minion Horde","Minions","Mother Witch","Musketeer","Knight/Evolution"]
log={}
if os.path.exists(LOG):
    log=json.load(open(LOG,encoding='utf-8'))
for t in titles:
    if t in log and log[t].get('revid'):
        print("already fetched:",t); continue
    q=urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    url=BASE+'?'+q
    try:
        req=urllib.request.Request(url,headers=HDR)
        with urllib.request.urlopen(req,timeout=25) as r:
            data=json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print("ERROR",t,repr(e)); log[t]={'error':repr(e)}; time.sleep(0.25); continue
    if 'error' in data:
        print("APIERR",t,data['error'].get('code')); log[t]={'apierror':data['error'].get('code')}
    else:
        p=data['parse']
        wt=p['wikitext']['*']; revid=p['revid']
        fn=t.replace('/','_').replace(' ','_')+'.wikitext'
        with open(os.path.join(CACHE,fn),'w',encoding='utf-8') as f: f.write(wt)
        log[t]={'revid':revid,'fetched':'2026-08-26','bytes':len(wt),'file':fn,
                'url':'https://clashroyale.fandom.com/api.php?action=parse&page='+urllib.parse.quote(t)+'&prop=wikitext|revid&format=json'}
        print("OK",t,revid,len(wt))
    time.sleep(0.25)
json.dump(log,open(LOG,'w',encoding='utf-8'),indent=1)
print("done")
