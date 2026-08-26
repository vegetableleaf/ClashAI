import json, time, urllib.request, urllib.parse, os, re
BASE="https://clashroyale.fandom.com/api.php"; UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
HDR=re.compile(r'^<!--\s*revid:(\d+)')
out={}
for t in ["Fire Spirit","Goblins","Mortar","Spear Goblins","Skeletons","Barbarians"]:
    fn=t.replace(' ','_')+'.wikitext'; path=os.path.join(CACHE,fn)
    ct=open(path,encoding='utf-8').read() if os.path.exists(path) else None
    m=HDR.match(ct) if ct else None; cr=int(m.group(1)) if m else None
    url=BASE+"?"+urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25))
    live=r['parse']['revid']; wt=r['parse']['wikitext']['*']
    body=ct.split('\n',1)[1] if m else ct
    lp=os.path.join(CACHE,fn.replace('.wikitext','.live20260826.wikitext'))
    open(lp,'w',encoding='utf-8').write("<!-- revid:%d fetched:2026-08-26 title:%s LIVE -->\n"%(live,t)+wt)
    out[t]={'revid_live':live,'revid_cached':cr,'content_identical':(body==wt) if body else None,
            'edit_war':('pass' if (cr is None or cr==live) else 'CHANGED'),
            'vardefines':re.findall(r'\{\{#vardefine:\s*([a-z0-9_]+)\s*\|\s*([0-9.]+)\s*\}\}',wt)}
    print(t,'live',live,'cached',cr,'same',(body==wt) if body else None, out[t]['vardefines'][:8])
    time.sleep(0.25)
json.dump(out,open(r'C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_spawn_anchor_fetchlog_extra.json','w'),indent=1)
