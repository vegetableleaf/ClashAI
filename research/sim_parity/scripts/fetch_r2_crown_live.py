import json, time, urllib.request, urllib.parse, os, hashlib
BASE="https://clashroyale.fandom.com/api.php"
UA={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE=r'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
OUT=r'C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_crosscheck_crown_fetchlog.json'
# title -> archived revid known from prior logs (None = unknown, infer by content)
TARGETS={
 "Firecracker":437467, "Firecracker/Evolution":None,
 "Zap":437305, "Zap/Evolution":437306,
 "Cannon":437251, "Cannon/Evolution":None,
 "Earthquake":437302, "Goblin Curse":437353, "The Log":437310,
 "Giant Skeleton":436713, "Graveyard":437290, "Royal Delivery":437384,
 "Tornado":436504, "Vines":437543, "Goblin Drill":None, "Goblin Drill/Evolution":None,
 "Miner":None, "Giant Snowball":None, "Giant Snowball/Evolution":None,
}
def cachename(t): return t.replace('/','_').replace(' ','_')+'.wikitext'
out={}
for t,arch_rev in TARGETS.items():
    url=BASE+"?"+urllib.parse.urlencode({'action':'parse','page':t,'prop':'wikitext|revid','format':'json'})
    try:
        r=json.load(urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25))
        p=r['parse']; live=p['revid']; wt=p['wikitext']['*']; ret=p.get('title')
        fn=cachename(t); path=os.path.join(CACHE,fn)
        had=os.path.exists(path)
        prior=open(path,encoding='utf-8').read() if had else None
        ident=(prior==wt) if had else None
        sha=hashlib.sha1(wt.encode('utf-8')).hexdigest()[:12]
        if had and not ident:
            # PRESERVE the archived timepoint; park live under its own revid
            livepath=os.path.join(CACHE,t.replace('/','_').replace(' ','_')+'.rev%d.wikitext'%live)
            open(livepath,'w',encoding='utf-8').write(wt)
            wrote=os.path.basename(livepath)
        else:
            if not had: open(path,'w',encoding='utf-8').write(wt)
            wrote=fn
        eff_arch = arch_rev if arch_rev is not None else (live if ident else None)
        if eff_arch is None: war='UNKNOWN_ARCHIVE_REV'
        elif eff_arch==live: war='pass'
        else: war='CHANGED'
        if had and ident is False and war=='pass': war='CHANGED'
        out[t]={'title_returned':ret,'revid_live':live,'revid_archived':arch_rev,
                'archived_file_existed':had,'content_identical_to_archive':ident,
                'edit_war':war,'sha1':sha,'bytes':len(wt),'fetched':'2026-08-26',
                'file_written':wrote,'archive_file':fn,
                'url':'https://clashroyale.fandom.com/wiki/'+t.replace(' ','_')}
        print(t,'| live',live,'| arch',arch_rev,'| ident',ident,'|',war)
    except Exception as e:
        out[t]={'error':repr(e)}; print(t,'ERROR',repr(e))
    time.sleep(0.25)
json.dump(out,open(OUT,'w'),indent=1)
print('WROTE',OUT)
