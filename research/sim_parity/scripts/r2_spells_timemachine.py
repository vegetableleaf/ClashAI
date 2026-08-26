import json, time, urllib.request, urllib.parse, re, sys, os
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
def api(params):
    url=BASE+"?"+urllib.parse.urlencode(params)
    return json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25))
def revs(title, start, end):
    r=api({'action':'query','prop':'revisions','titles':title,'rvlimit':'50',
           'rvprop':'ids|timestamp|comment','rvstart':start,'rvend':end,'rvdir':'newer','format':'json'})
    pg=list(r['query']['pages'].values())[0]
    return pg.get('revisions',[])
def wt(revid):
    r=api({'action':'parse','oldid':revid,'prop':'wikitext','format':'json'})
    return r['parse']['wikitext']['*']
def vardefs(t):
    return dict((m.group(1).strip(),m.group(2).strip())
                for m in re.finditer(r"\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}", t))
for title in sys.argv[1:]:
    print("="*20, title)
    rs=revs(title,'2026-07-01T00:00:00Z','2026-08-26T23:59:59Z')
    print(" revisions Jul1->Aug26 2026:", len(rs))
    for r in rs:
        print("   ", r['revid'], r['timestamp'], (r.get('comment') or '')[:70])
    time.sleep(0.3)
    # last revision BEFORE 4/8/2026
    pre=api({'action':'query','prop':'revisions','titles':title,'rvlimit':'1','rvprop':'ids|timestamp',
             'rvstart':'2026-08-03T23:59:59Z','rvdir':'older','format':'json'})
    pgv=list(pre['query']['pages'].values())[0]['revisions'][0]
    print(" PRE-4/8/2026 revid", pgv['revid'], pgv['timestamp'])
    time.sleep(0.3)
    a=vardefs(wt(pgv['revid'])); time.sleep(0.3)
    b=vardefs(wt(api({'action':'parse','page':title,'prop':'revid','format':'json'})['parse']['revid']))
    keys=sorted(set(a)|set(b))
    for k in keys:
        av,bv=a.get(k),b.get(k)
        print(f"   {'DIFF' if av!=bv else 'same'}  {k}: pre={av}  now={bv}")
    time.sleep(0.3)
