import json, time, urllib.request, urllib.parse, os, re
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE='C:/Users/benpe/ClashBot/research/sim_parity/webcache'
OUT='C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_evos_a_fetchlog_v2.json'
KEYS={
 'archers_evo':'Archers/Evolution','baby_dragon_evo':'Baby Dragon/Evolution',
 'barbarians_evo':'Barbarians/Evolution','bats_evo':'Bats/Evolution',
 'battle_ram_evo':'Battle Ram/Evolution','bomber_evo':'Bomber/Evolution',
 'cannon_evo':'Cannon/Evolution','dart_goblin_evo':'Dart Goblin/Evolution',
 'electro_dragon_evo':'Electro Dragon/Evolution','elite_barbarians_evo':'Elite Barbarians/Evolution',
 'executioner_evo':'Executioner/Evolution','firecracker_evo':'Firecracker/Evolution',
 'furnace_evo':'Furnace/Evolution','giant_snowball_evo':'Giant Snowball/Evolution',
 'goblin_barrel_evo':'Goblin Barrel/Evolution','goblin_cage_evo':'Goblin Cage/Evolution',
 'goblin_drill_evo':'Goblin Drill/Evolution','goblin_giant_evo':'Goblin Giant/Evolution',
 'hunter_evo':'Hunter/Evolution','ice_spirit_evo':'Ice Spirit/Evolution',
 'inferno_dragon_evo':'Inferno Dragon/Evolution'}
log={'fetched':'2026-08-26','session':'r2_evos_a diff pass','pages':{}}
for key,title in KEYS.items():
    q=urllib.parse.urlencode({'action':'parse','page':title,'prop':'wikitext|revid','format':'json'})
    req=urllib.request.Request(BASE+'?'+q,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r:
        data=json.load(r)
    p=data['parse']; revid=p['revid']; text=p['wikitext']['*']
    cf=title.replace('/','_').replace(' ','_')+'.wikitext'
    path=os.path.join(CACHE,cf)
    cached_revid=None
    if os.path.exists(path):
        old=open(path,encoding='utf-8').read()
        m=re.match(r'<!-- revid:(\d+)',old)
        if m: cached_revid=int(m.group(1))
    stamped='<!-- revid:%d fetched:2026-08-26 title:%s -->\n'%(revid,title)+text
    changed = cached_revid is not None and cached_revid!=revid
    if changed or cached_revid is None:
        # archive: if changed, keep old under rev-name
        if changed:
            os.replace(path, os.path.join(CACHE, cf.replace('.wikitext','.rev%d.wikitext'%cached_revid)))
        open(path,'w',encoding='utf-8').write(stamped)
    log['pages'][key]={'title':title,'live_revid':revid,'cached_revid':cached_revid,
        'changed':bool(changed),'bytes':len(text),'cache_file':cf,
        'url':'https://clashroyale.fandom.com/api.php?action=parse&page=%s&prop=wikitext|revid&format=json'%urllib.parse.quote(title)}
    print(key,revid,'cached',cached_revid,'CHANGED' if changed else 'ok')
    time.sleep(0.25)
json.dump(log,open(OUT,'w'),indent=1)
print('done')
