import json, time, urllib.request, urllib.parse, os, re
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
titles=["Goblin Cage","Goblin Cage/Evolution","Party Hut","Furnace","Furnace/Evolution",
        "Goblin Hut","Tombstone","Barbarian Hut","Goblin Drill","Goblin Drill/Evolution",
        "Elixir Collector","Mortar/Evolution","Phoenix","Mighty Miner","Little Prince"]
HDR=re.compile(r'^<!--\s*revid:(\d+)')
out={}
for t in titles:
    fn=t.replace('/','_').replace(' ','_')+'.wikitext'
    path=os.path.join(CACHE,fn)
    cached_rev=None; cached_txt=None
    if os.path.exists(path):
        cached_txt=open(path,encoding='utf-8').read()
        m=HDR.match(cached_txt)
        if m: cached_rev=int(m.group(1))
    url=BASE+"?"+urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    try:
        r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25))
        p=r['parse']; live=p['revid']; wt=p['wikitext']['*']
        body_cached = cached_txt.split('\n',1)[1] if (cached_txt and HDR.match(cached_txt)) else cached_txt
        same = (body_cached==wt) if body_cached is not None else None
        lp=os.path.join(CACHE,fn.replace('.wikitext','.live20260826.wikitext'))
        open(lp,'w',encoding='utf-8').write("<!-- revid:%d fetched:2026-08-26 title:%s LIVE -->\n"%(live,t)+wt)
        out[t]={'revid_live':live,'revid_cached':cached_rev,'cached_file':fn if cached_txt else None,
                'live_file':os.path.basename(lp),'content_identical':same,
                'edit_war':('pass' if (cached_rev is None or cached_rev==live) else 'CHANGED'),
                'bytes':len(wt),'fetched':'2026-08-26'}
        print(t,'live',live,'cached',cached_rev,'same',same)
    except Exception as e:
        out[t]={'error':repr(e)}; print(t,'ERROR',repr(e))
    time.sleep(0.25)
json.dump(out,open(r'C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_spawn_anchor_fetchlog.json','w'),indent=1)
print('done')
