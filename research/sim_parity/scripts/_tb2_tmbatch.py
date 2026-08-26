import json,sys,time,re,urllib.request,urllib.parse
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
def api(p):
    req=urllib.request.Request(BASE+'?'+urllib.parse.urlencode(p),headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)
JOBS=json.load(open(sys.argv[1],encoding='utf-8'))
out={}
for title,iso in JOBS:
    try:
        q=api({'action':'query','prop':'revisions','titles':title,'rvlimit':'1',
               'rvprop':'ids|timestamp','rvstart':iso,'rvdir':'older','format':'json'})
        rev=list(q['query']['pages'].values())[0]['revisions'][0]
        time.sleep(0.3)
        d=api({'action':'parse','oldid':str(rev['revid']),'prop':'wikitext','format':'json'})
        t=d['parse']['wikitext']['*']
    except Exception as e:
        print('##',title,'ERR',str(e)[:120]); out[title]={'error':str(e)[:150]}; time.sleep(0.3); continue
    vd={m.group(1):m.group(2) for m in re.finditer(r'\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}',t)}
    l11=[m.group(0)[:220] for m in re.finditer(r'^\|\s*11\s*\|\|.*$',t,re.M)]
    # attribute-table hit speed / relevant literal rows
    hs=re.findall(r'^\|[^\n]*?sec\|\|[^\n]*$',t,re.M)[:3]
    out[title]={'iso':iso,'revid':rev['revid'],'ts':rev['timestamp'],'vardefines':vd,'l11':l11,'rows':hs}
    print('##',title,'| before',iso,'| revid',rev['revid'],rev['timestamp'])
    for k,v in vd.items(): print('     VD %-22s = %s'%(k,v))
    for r in l11: print('     L11ROW:',r)
    for r in hs: print('     ROW:',r[:200])
    time.sleep(0.3)
json.dump(out,open(sys.argv[2],'w',encoding='utf-8'),indent=1)
