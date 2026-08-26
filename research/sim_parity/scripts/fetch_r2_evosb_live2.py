import json, time, urllib.request, urllib.parse, os, hashlib
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
LEDGER=r'C:/Users/benpe/ClashBot/research/sim_parity/ledger'
# revids recorded by the 00:52 evos_b fetchlog (the earlier timepoint)
prior=json.load(open(os.path.join(LEDGER,'r2_evosb_fetchlog.json'),encoding='utf-8'))
titles=["Musketeer/Evolution","Royal Recruits/Evolution","Skeleton Barrel/Evolution",
        "Skeletons/Evolution","Witch/Evolution","Wizard/Evolution","Zap/Evolution",
        "Musketeer","Royal Recruits","Skeleton Barrel","Skeletons","Witch","Wizard","Zap"]
out={}
for t in titles:
    fn=t.replace('/','_').replace(' ','_')+'.wikitext'
    path=os.path.join(CACHE,fn)
    old_sha=None
    if os.path.exists(path):
        old=open(path,encoding='utf-8').read()
        old_sha=hashlib.sha1(old.encode('utf-8')).hexdigest()[:10]
    url=BASE+"?"+urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    try:
        r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25))
        p=r['parse']; revid=p['revid']; wt=p['wikitext']['*']
        new_sha=hashlib.sha1(wt.encode('utf-8')).hexdigest()[:10]
        # archive this fetch under its revid, and refresh the plain cache name
        open(os.path.join(CACHE,fn.replace('.wikitext','.rev%d.wikitext'%revid)),'w',encoding='utf-8').write(wt)
        open(path,'w',encoding='utf-8').write(wt)
        pr=prior.get(t,{}).get('live_revid')
        out[t]={'live_revid':revid,'prior_revid_0052':pr,
                'edit_war':('pass' if (pr is None or pr==revid) else 'CHANGED'),
                'prior_recorded':pr is not None,
                'sha_before':old_sha,'sha_live':new_sha,'content_changed':(old_sha!=new_sha),
                'bytes':len(wt),'fetched':'2026-08-26','file':fn}
        print(t,'live',revid,'prior',pr,out[t]['edit_war'],'content_changed',old_sha!=new_sha)
    except Exception as e:
        out[t]={'error':repr(e)}
        print(t,'ERROR',repr(e))
    time.sleep(0.25)
json.dump(out,open(os.path.join(LEDGER,'r2_evos_b_livefetch2.json'),'w'),indent=1)
print('DONE')
