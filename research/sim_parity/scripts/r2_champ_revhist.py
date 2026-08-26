import json,sys,time,urllib.request,urllib.parse
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
def q(**kw):
    kw.setdefault('format','json')
    req=urllib.request.Request(BASE+"?"+urllib.parse.urlencode(kw),headers=UA)
    return json.load(urllib.request.urlopen(req,timeout=25))
title=sys.argv[1]; n=int(sys.argv[2]) if len(sys.argv)>2 else 25
r=q(action='query',prop='revisions',titles=title,rvlimit=n,rvprop='ids|timestamp|comment|user|size',rvslots='main')
pg=list(r['query']['pages'].values())[0]
print('PAGE:',pg.get('title'))
for rev in pg.get('revisions',[]):
    print('  %-9s %s  %6s b  %-16s %s'%(rev['revid'],rev['timestamp'][:10],rev.get('size'),rev.get('user','?')[:16],(rev.get('comment') or '')[:70]))
