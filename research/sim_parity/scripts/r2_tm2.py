import json, time, sys, re, urllib.request, urllib.parse
BASE="https://clashroyale.fandom.com/api.php"
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
def get(params):
    url=BASE+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))
title,cutoff,pat=sys.argv[1],sys.argv[2],sys.argv[3]
q=get({'action':'query','prop':'revisions','titles':title,'rvlimit':'1',
       'rvprop':'ids|timestamp|comment','rvstart':cutoff,'rvdir':'older','format':'json'})
rev=list(q['query']['pages'].values())[0]['revisions'][0]
time.sleep(0.25)
p=get({'action':'parse','oldid':str(rev['revid']),'prop':'wikitext','format':'json'})
wt=p['parse']['wikitext']['*']
print(f"== {title} oldid {rev['revid']} ts {rev['timestamp']}")
for m in re.finditer(pat, wt):
    s=max(0,m.start()-120); print("   ...", wt[s:m.end()+240].replace("\n"," | ")[:500], "\n")
