import json, time, urllib.request, urllib.parse, os, hashlib
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
LED=r'C:/Users/benpe/ClashBot/research/sim_parity/ledger'
# cached revids recorded by the 05:37 pass (the 08-25/26 archive timepoint)
prior=json.load(open(os.path.join(LED,'r2_champions_fetchlog.json')))['pages']
titles=["Archer Queen","Boss Bandit","Goblinstein","Golden Knight","Little Prince",
        "Mighty Miner","Monk","Skeleton King"]
out={}
for t in titles:
    url=BASE+"?"+urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    req=urllib.request.Request(url,headers=UA)
    try:
        r=json.load(urllib.request.urlopen(req,timeout=25))
        p=r['parse']; revid=p['revid']; wt=p['wikitext']['*']; title=p['title']
        fn=t.replace('/','_').replace(' ','_')+'.wikitext'
        path=os.path.join(CACHE,fn)
        arch=open(path,encoding='utf-8').read() if os.path.exists(path) else None
        same = (arch is not None and arch.replace('\r\n','\n')==wt.replace('\r\n','\n'))
        cr=prior.get(t,{}).get('cached_revid')
        if not same:
            # preserve BOTH timepoints: archive the live one under its revid
            open(os.path.join(CACHE,t.replace('/','_').replace(' ','_')+'.rev%d.wikitext'%revid),'w',encoding='utf-8').write(wt)
        out[t]={'title_returned':title,'revid_live':revid,'revid_archive':cr,
                'edit_war':('pass' if revid==cr else 'CHANGED'),
                'content_identical_to_archive':same,'bytes':len(wt),
                'sha1':hashlib.sha1(wt.encode('utf-8')).hexdigest()[:12],'fetched':'2026-08-26','file':fn}
        print('%-16s live=%s archive=%s same=%s title=%r'%(t,revid,cr,same,title))
    except Exception as e:
        out[t]={'error':repr(e)}; print(t,'ERROR',repr(e))
    time.sleep(0.25)
json.dump(out,open(os.path.join(LED,'r2_champions_livefetch.json'),'w'),indent=1)
print('done')
