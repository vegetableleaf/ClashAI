import json, time, urllib.request, urllib.parse, os
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
META=os.path.join(CACHE,'_r2_spells_meta.json')
titles=["Arrows","Barbarian Barrel","Clone","Earthquake","Fireball","Freeze","Giant Snowball",
"Goblin Barrel","Goblin Barrel/Evolution","Goblin Curse","Graveyard","Lightning","Mirror","Poison",
"Rage","Rocket","Royal Delivery","The Log","Tornado","Vines","Void","Zap"]
old=json.load(open(META))
out={}
for t in titles:
    url=BASE+"?"+urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    req=urllib.request.Request(url,headers=UA)
    try:
        r=json.load(urllib.request.urlopen(req,timeout=25))
        p=r['parse']; revid=p['revid']; wt=p['wikitext']['*']
        fn=t.replace('/','_').replace(' ','_')+'.wikitext'
        oldrev=old.get(t,{}).get('revid')
        # read existing cache content
        path=os.path.join(CACHE,fn)
        same=None
        if os.path.exists(path):
            same=(open(path,encoding='utf-8').read()==wt)
        open(path,'w',encoding='utf-8').write(wt)
        out[t]={'revid_live':revid,'revid_cached_0051':oldrev,'edit_war':('pass' if revid==oldrev else 'CHANGED'),
                'content_same_as_cache':same,'bytes':len(wt),'fetched':'2026-08-26','file':fn}
        print(t,'live',revid,'cached',oldrev,'same_content',same)
    except Exception as e:
        out[t]={'error':repr(e)}
        print(t,'ERROR',repr(e))
    time.sleep(0.25)
json.dump(out,open(os.path.join(CACHE,'_r2_spells_meta_live.json'),'w'),indent=1)
print('done')
