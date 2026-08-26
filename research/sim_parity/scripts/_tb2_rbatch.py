import json,re,sys,time,urllib.request,urllib.parse,html,os
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
CACHE='C:/Users/benpe/ClashBot/research/sim_parity/webcache/'
def api(params):
    req=urllib.request.Request(BASE+'?'+urllib.parse.urlencode(params),headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)
def tables(h):
    out=[]
    for m in re.finditer(r'<table[^>]*>(.*?)</table>', h, re.S):
        rows=[]
        for rm in re.finditer(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.S):
            cells=[re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','',c))).strip()
                   for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', rm.group(1), re.S)]
            if cells: rows.append(cells)
        out.append(rows)
    return out
PAGES=json.load(open(sys.argv[1],encoding='utf-8'))
meta={}
for title in PAGES:
    try:
        d=api({'action':'parse','page':title,'prop':'text|revid','format':'json'})
        rev=d['parse']['revid']; h=d['parse']['text']['*']
    except Exception as e:
        meta[title]={'error':str(e)[:150]}; print(title,'ERR',e); time.sleep(0.25); continue
    grabbed=[]
    for tb in tables(h):
        if not tb: continue
        hdr=tb[0]
        if not any(c.strip()=='Level' for c in hdr): continue
        row11=[r for r in tb[1:] if r and r[0].strip()=='11']
        grabbed.append({'hdr':hdr,'l11':row11[0] if row11 else None,
                        'l1':tb[1] if tb[1:] else None})
    meta[title]={'revid':rev,'fetched':'2026-08-26','level_tables':grabbed}
    print('##',title,'revid',rev)
    for g in grabbed:
        print('   HDR:',' | '.join(g['hdr']))
        print('   L11:',' | '.join(g['l11']) if g['l11'] else None)
    time.sleep(0.3)
json.dump(meta,open(sys.argv[2],'w',encoding='utf-8'),indent=1)
