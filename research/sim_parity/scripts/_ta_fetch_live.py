import json, time, urllib.request, urllib.parse, os, sys
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE='research/sim_parity/webcache'
fl=json.load(open('research/sim_parity/ledger/r2_troops_a_fetchlog.json'))
out={}
for title,meta in fl.items():
    q=urllib.parse.urlencode({'action':'parse','page':title,'prop':'wikitext|revid','format':'json'})
    req=urllib.request.Request(BASE+'?'+q, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            data=json.load(r)
    except Exception as e:
        out[title]={'error':str(e),'cached_revid':meta['live_revid']}
        print('ERR',title,e); time.sleep(0.25); continue
    p=data.get('parse',{})
    revid=p.get('revid'); wt=p.get('wikitext',{}).get('*','')
    cf=os.path.join(CACHE, meta['cache_file'])
    cached_revid=meta['live_revid']
    changed = (revid != cached_revid)
    if changed:
        # preserve the older cache under .rev<old>, then write the new live text
        old=open(cf,encoding='utf-8').read() if os.path.exists(cf) else None
        if old is not None:
            keep=cf.replace('.wikitext','.rev%d.wikitext'%cached_revid)
            if not os.path.exists(keep):
                open(keep,'w',encoding='utf-8').write(old)
        open(cf,'w',encoding='utf-8').write(wt)
    else:
        # ensure archive holds this text
        if not os.path.exists(cf) or open(cf,encoding='utf-8').read()!=wt:
            open(cf,'w',encoding='utf-8').write(wt)
    out[title]={'cached_revid':cached_revid,'live_revid':revid,'edit_war':'CHANGED' if changed else 'pass',
                'fetched':'2026-08-26','bytes':len(wt),'cache_file':meta['cache_file'],'keys':meta['keys']}
    print(('CHANGED ' if changed else 'pass    ')+title, cached_revid,'->',revid)
    time.sleep(0.25)
json.dump(out, open('research/sim_parity/ledger/r2_troops_a_fetchmeta2.json','w'), indent=1)
print('done', len(out))
