import re,os,json,sys
sys.path.insert(0,'C:/Users/benpe/ClashBot/research/sim_parity/scripts')
from _tb2_digest import clean
CACHE='C:/Users/benpe/ClashBot/research/sim_parity/webcache/'
DB=json.load(open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/current_db_snapshot.json',encoding='utf-8'))['cards']
# page -> [(subheader-match, dbkey)]
MAP=[('Giant_Skeleton.wikitext','Giant Skeleton','giant_skeleton'),
 ('Goblin_Cage.wikitext','Goblin Brawler','goblin_brawler'),
 ('Goblin_Demolisher.wikitext','Goblin Demolisher','goblin_demolisher'),
 ('Goblin_Gang.wikitext','Goblin','goblin_gang'),
 ('Goblin_Giant.wikitext','Goblin Giant','goblin_giant'),
 ('Goblin_Machine.wikitext','Goblin Machine','goblin_machine'),
 ('Goblins.wikitext','Goblin','goblins'),
 ('Golem.wikitext','Golem Attributes','golem'),
 ('Golem.wikitext','Golemite','golemite'),
 ('Guards.wikitext','Guard','guards'),
 ('Heal_Spirit.wikitext','Heal Spirit','heal_spirit'),
 ('Hog_Rider.wikitext','','hog_rider'),
 ('Hunter.wikitext','','hunter'),
 ('Ice_Golem.wikitext','','ice_golem'),
 ('Ice_Spirit.wikitext','','ice_spirit'),
 ('Ice_Wizard.wikitext','','ice_wizard'),
 ('Inferno_Dragon.wikitext','','inferno_dragon'),
 ('Knight.wikitext','','knight'),
 ('Lava_Hound.wikitext','Lava Hound','lava_hound'),
 ('Lava_Hound.wikitext','Lava Pup','lava_pups'),
 ('Lumberjack.wikitext','','lumberjack'),
 ('Lumberjack_Evolution.wikitext','Ghost','lumberjack_ghost'),
 ('Magic_Archer.wikitext','','magic_archer'),
 ('Mega_Knight.wikitext','','mega_knight'),
 ('Mega_Minion.wikitext','','mega_minion'),
 ('Miner.wikitext','','miner'),
 ('Mini_P.E.K.K.A..wikitext','','mini_pekka'),
 ('Minion_Horde.wikitext','','minion_horde'),
 ('Minions.wikitext','','minions'),
 ('Mother_Witch.wikitext','Mother Witch','mother_witch'),
 ('Mother_Witch.wikitext','Hog','mother_witch_hog'),
 ('Musketeer.wikitext','','musketeer')]
def blocks(t):
    """yield (subheader_label, table_text) for every StatisticsSubheader-led wikitable"""
    for m in re.finditer(r'\{\{StatisticsSubheader\|([^}]*)\}\}\s*(\{\|.*?\n\|\})', t, re.S):
        yield m.group(1).strip(), m.group(2)
def cells(tbl):
    heads=[clean(x) for x in re.findall(r'^!\s*scope="col"\s*\|(.*)$', tbl, re.M)]
    rows=[]
    for line in tbl.split('\n'):
        ls=line.strip()
        if ls.startswith('|') and '||' in ls and not ls.startswith('|-') and not ls.startswith('|}'):
            rows.append([clean(c) for c in ls[1:].split('||')])
    return heads, rows
def num(s):
    if s is None: return None
    m=re.search(r'-?\d+(?:\.\d+)?',str(s).replace(',',''))
    return float(m.group(0)) if m else None
print('%-18s %-26s %-7s %-7s %-8s %-8s %s'%('key','section','wikiHS','wikiFHS','db_hit','db_load','identity'))
for fn,label,key in MAP:
    if not os.path.exists(CACHE+fn): print('%-18s MISSING PAGE %s'%(key,fn)); continue
    t=open(CACHE+fn,encoding='utf-8').read()
    got=None
    for lab,tbl in blocks(t):
        if 'unit-statistics-table' in tbl: continue
        if label and label.lower() not in lab.lower(): continue
        h,r=cells(tbl)
        if 'Hit Speed' in h and r:
            i=h.index('Hit Speed'); j=h.index('First Hit Speed') if 'First Hit Speed' in h else None
            got=(lab, num(r[0][i]) if i<len(r[0]) else None, num(r[0][j]) if (j is not None and j<len(r[0])) else None)
            break
    d=DB.get(key,{})
    hs,lt=d.get('hit_speed'),d.get('load_time_s')
    if got is None:
        print('%-18s %-26s %-7s %-7s %-8s %-8s %s'%(key,'(no Hit Speed table)','-','-',hs,lt,''))
        continue
    lab,whs,wfhs=got
    calc=round(whs-wfhs,3) if (whs is not None and wfhs is not None) else None
    ok=''
    if lt is None: ok='(db has no load_time_s)'
    elif calc is None: ok='(no FHS col)'
    elif abs(calc-lt)<1e-6: ok='OK'
    else: ok='** MISMATCH -> %s'%calc
    hsflag='' if (hs is None or whs is None or abs(hs-whs)<1e-6) else '  <<HIT_SPEED %s vs wiki %s>>'%(hs,whs)
    print('%-18s %-26s %-7s %-7s %-8s %-8s %s%s'%(key,lab[:26],whs,wfhs,hs,lt,ok,hsflag))
