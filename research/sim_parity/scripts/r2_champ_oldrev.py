import json,sys,re,urllib.request,urllib.parse,os
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
rev=sys.argv[1]; name=sys.argv[2]
req=urllib.request.Request(BASE+"?"+urllib.parse.urlencode(
    {'action':'parse','oldid':rev,'prop':'wikitext|revid','format':'json'}),headers=UA)
p=json.load(urllib.request.urlopen(req,timeout=25))['parse']
wt=p['wikitext']['*']
open(os.path.join(CACHE,'%s.rev%s.wikitext'%(name,rev)),'w',encoding='utf-8').write(wt)
print('title',p['title'],'revid',p['revid'],'bytes',len(wt))
for k,v in re.findall(r'\{\{#vardefine:\s*([A-Za-z0-9_]+)\s*\|\s*([^}]*?)\s*\}\}', wt):
    print('   %-20s = %s'%(k,v))
