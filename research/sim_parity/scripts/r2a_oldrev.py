import json, sys, time, re, urllib.request, urllib.parse
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
for oldid in sys.argv[1:]:
    q=urllib.parse.urlencode({'action':'parse','oldid':oldid,'prop':'wikitext|revid','format':'json'})
    req=urllib.request.Request(BASE+'?'+q,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r: data=json.load(r)
    t=data['parse']['wikitext']['*']
    print('## oldid',oldid,data['parse'].get('title'))
    for vm in re.finditer(r'\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]+?)\s*\}\}',t):
        print('  VARDEF:',vm.group(1),'=',vm.group(2))
    time.sleep(0.3)
