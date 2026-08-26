import json, sys, time, urllib.request, urllib.parse
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
def revs(title, n=30):
    q=urllib.parse.urlencode({'action':'query','prop':'revisions','titles':title,
        'rvlimit':n,'rvprop':'ids|timestamp|comment|user','format':'json'})
    req=urllib.request.Request(BASE+'?'+q,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r: data=json.load(r)
    pages=data['query']['pages']
    for pid,p in pages.items():
        print('##',p.get('title'))
        for rv in p.get('revisions',[]):
            print(rv['revid'], rv['timestamp'], (rv.get('comment','') or '')[:90])
for t in sys.argv[1:]:
    revs(t); time.sleep(0.3)
