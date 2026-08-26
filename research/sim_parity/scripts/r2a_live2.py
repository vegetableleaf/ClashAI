import json, time, urllib.request, urllib.parse, os, re, sys
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE='C:/Users/benpe/ClashBot/research/sim_parity/webcache'
OUT=os.environ.get('R2A_OUT','C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_evos_a_fetchlog_v3.json')
TITLES=json.loads(sys.argv[1])   # {key: title}
if os.path.exists(OUT):
    log=json.load(open(OUT,encoding='utf-8'))
else:
    log={'fetched':'2026-08-26','session':'r2_evos_a independent live re-verify','pages':{}}
for key,title in TITLES.items():
    q=urllib.parse.urlencode({'action':'parse','page':title,'prop':'wikitext|revid','format':'json'})
    url=BASE+'?'+q
    try:
        req=urllib.request.Request(url,headers=HDR)
        with urllib.request.urlopen(req,timeout=25) as r:
            data=json.load(r)
    except Exception as e:
        log['pages'][key]={'title':title,'error':repr(e),'url':url}
        print('ERR',key,e); time.sleep(0.25); continue
    if 'error' in data:
        log['pages'][key]={'title':title,'api_error':data['error'].get('code'),'url':url}
        print('APIERR',key,data['error'].get('code')); time.sleep(0.25); continue
    p=data['parse']; revid=p['revid']; text=p['wikitext']['*']
    cf=title.replace('/','_').replace(' ','_')+'.wikitext'
    path=os.path.join(CACHE,cf)
    cached_revid=None
    if os.path.exists(path):
        old=open(path,encoding='utf-8').read()
        m=re.match(r'<!-- revid:(\d+)',old)
        if m: cached_revid=int(m.group(1))
    stamped='<!-- revid:%d fetched:2026-08-26T2 title:%s -->\n'%(revid,title)+text
    changed = cached_revid is not None and cached_revid!=revid
    if changed:
        os.replace(path, os.path.join(CACHE, cf.replace('.wikitext','.rev%d.wikitext'%cached_revid)))
    if changed or cached_revid is None:
        open(path,'w',encoding='utf-8').write(stamped)
    log['pages'][key]={'title':title,'live_revid':revid,'prev_cached_revid':cached_revid,
        'changed':bool(changed),'bytes':len(text),'cache_file':cf,'url':url,'fetched':'2026-08-26'}
    print('%-26s live=%-7s cached=%-7s changed=%s bytes=%d'%(key,revid,cached_revid,changed,len(text)))
    time.sleep(0.25)
json.dump(log,open(OUT,'w',encoding='utf-8'),indent=1)
print('wrote',OUT,len(log['pages']))
