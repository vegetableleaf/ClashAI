import json, time, urllib.request, urllib.parse
BASE="https://clashroyale.fandom.com/api.php"
HDRS={'User-Agent':'icebow-monitor/1.0 (+local)'}
def get(url):
    req=urllib.request.Request(url,headers=HDRS)
    with urllib.request.urlopen(req,timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))
# 1) revid recheck for pages not covered by r2_troops_b_revidcheck.json
cached=json.load(open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_b_fetchlog.json',encoding='utf-8'))
out={}
for p in ["Giant Skeleton","Goblin Demolisher","Goblin Gang","Knight/Evolution"]:
    try:
        d=get(BASE+"?action=parse&page="+urllib.parse.quote(p)+"&prop=revid&format=json")
        live=d.get('parse',{}).get('revid')
    except Exception as e:
        live='EXC:'+str(e)[:100]
    crev=(cached.get(p) or {}).get('revid')
    out[p]={'cached_revid':crev,'live_revid':live,'status':'SAME' if live==crev else 'CHANGED'}
    print(p,'|',crev,'->',live,'|',out[p]['status'],flush=True)
    time.sleep(0.25)
json.dump(out,open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_b_revidcheck2.json','w',encoding='utf-8'),indent=1)
# 2) search for Goblin Brawler
print('--- SEARCH ---')
d=get(BASE+"?action=query&list=search&srsearch="+urllib.parse.quote("Goblin Brawler")+"&srlimit=12&format=json")
for h in d.get('query',{}).get('search',[]):
    print(repr(h['title']), h.get('size'))
