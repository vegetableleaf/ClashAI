import json, time, sys, re, urllib.request, urllib.parse
BASE="https://clashroyale.fandom.com/api.php"
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
def get(params):
    url=BASE+'?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))
def vars_at(title, cutoff_iso):
    # last revision strictly BEFORE cutoff
    q=get({'action':'query','prop':'revisions','titles':title,'rvlimit':'1',
           'rvprop':'ids|timestamp|comment','rvstart':cutoff_iso,'rvdir':'older','format':'json'})
    pages=q['query']['pages']; page=list(pages.values())[0]
    rev=page['revisions'][0]
    time.sleep(0.25)
    p=get({'action':'parse','oldid':str(rev['revid']),'prop':'wikitext','format':'json'})
    wt=p['parse']['wikitext']['*']
    vd=re.findall(r'\{\{#vardefine:\s*([\w ]+?)\s*\|\s*([^}|]*?)\s*\}\}',wt)
    return rev, vd
if __name__=='__main__':
    title=sys.argv[1]; cutoff=sys.argv[2]
    rev,vd=vars_at(title,cutoff)
    print(f"== {title} @ last rev before {cutoff}: revid {rev['revid']} ts {rev['timestamp']} comment {rev.get('comment','')!r}")
    for k,v in vd: print(f"   {k} = {v}")
