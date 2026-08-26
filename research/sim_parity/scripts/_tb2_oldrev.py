import json,sys,time,re,urllib.request,urllib.parse
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
def wt(oldid):
    q=urllib.parse.urlencode({'action':'parse','oldid':str(oldid),'prop':'wikitext|revid','format':'json'})
    req=urllib.request.Request(BASE+'?'+q,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r: d=json.load(r)
    return d['parse']['wikitext']['*']
def revbefore(title,iso):
    q=urllib.parse.urlencode({'action':'query','prop':'revisions','titles':title,'rvlimit':'1',
        'rvprop':'ids|timestamp|comment','rvstart':iso,'rvdir':'older','format':'json'})
    req=urllib.request.Request(BASE+'?'+q,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r: d=json.load(r)
    p=list(d['query']['pages'].values())[0]
    return p['revisions'][0]
if __name__=='__main__':
    title=sys.argv[1]; iso=sys.argv[2]
    rev=revbefore(title,iso); time.sleep(0.3)
    print('== %s @ last rev before %s: revid %s ts %s'%(title,iso,rev['revid'],rev['timestamp']))
    t=wt(rev['revid'])
    print('   len',len(t))
    n=0
    for m in re.finditer(r'\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}',t):
        print('   VARDEF %-24s = %s'%(m.group(1),m.group(2))); n+=1
    if not n:
        print('   (no vardefines) -- looking for hardcoded L11 row / hp text')
        for m in re.finditer(r'^\|\s*11\s*\|\|.*$',t,re.M): print('   L11ROW:',m.group(0)[:200])
