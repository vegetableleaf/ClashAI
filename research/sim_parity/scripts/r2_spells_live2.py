import json, time, urllib.request, urllib.parse, os
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
ROOT=r'C:/Users/benpe/ClashBot/research/sim_parity'
CACHE=os.path.join(ROOT,'webcache')
prev=json.load(open(os.path.join(CACHE,'_r2_spells_meta_live.json')))
titles=["Arrows","Barbarian Barrel","Clone","Earthquake","Fireball","Freeze","Giant Snowball",
"Goblin Barrel","Goblin Barrel/Evolution","Goblin Curse","Graveyard","Lightning","Mirror","Poison",
"Rage","Rocket","Royal Delivery","The Log","Tornado","Vines","Void","Zap"]
out={}
for t in titles:
    url=BASE+"?"+urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    req=urllib.request.Request(url,headers=UA)
    try:
        r=json.load(urllib.request.urlopen(req,timeout=25))
        p=r['parse']; revid=p['revid']; wt=p['wikitext']['*']
        fn=t.replace('/','_').replace(' ','_')+'.wikitext'
        path=os.path.join(CACHE,fn)
        cached_rev=prev.get(t,{}).get('revid_live')
        same=None
        if os.path.exists(path):
            same=(open(path,encoding='utf-8').read()==wt)
        open(path,'w',encoding='utf-8').write(wt)
        out[t]={'revid_live_0600':revid,'revid_prev_0537':cached_rev,
                'edit_war':('pass' if revid==cached_rev else 'CHANGED'),
                'content_identical':same,'bytes':len(wt),'fetched':'2026-08-26','file':fn}
        print(t,revid,cached_rev,out[t]['edit_war'],'content_same',same)
    except Exception as e:
        out[t]={'error':repr(e)}; print(t,'ERROR',repr(e))
    time.sleep(0.25)
json.dump(out,open(os.path.join(ROOT,'ledger','r2_spells_livefetch.json'),'w'),indent=1)
print('DONE'); print('CHANGED:',[k for k,v in out.items() if v.get('edit_war')=='CHANGED'])
