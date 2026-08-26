import json,re,sys,time,urllib.request,urllib.parse,html
BASE='https://clashroyale.fandom.com/api.php'
HDR={'User-Agent':'icebow-monitor/1.0 (+local)'}
def rendered(title):
    q=urllib.parse.urlencode({'action':'parse','page':title,'prop':'text|revid','format':'json'})
    req=urllib.request.Request(BASE+'?'+q,headers=HDR)
    with urllib.request.urlopen(req,timeout=25) as r: d=json.load(r)
    return d['parse']['revid'], d['parse']['text']['*']
def tables(h):
    # crude: split rendered html into tables, strip tags
    out=[]
    for m in re.finditer(r'<table[^>]*>(.*?)</table>', h, re.S):
        body=m.group(1)
        rows=[]
        for rm in re.finditer(r'<tr[^>]*>(.*?)</tr>', body, re.S):
            cells=[html.unescape(re.sub(r'<[^>]+>','',c)).strip() for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', rm.group(1), re.S)]
            cells=[re.sub(r'\s+',' ',c) for c in cells]
            if cells: rows.append(cells)
        out.append(rows)
    return out
if __name__=='__main__':
    title=sys.argv[1]
    lvl=sys.argv[2] if len(sys.argv)>2 else '11'
    rev,h=rendered(title)
    print('REVID',rev)
    for i,tb in enumerate(tables(h)):
        if not tb: continue
        hdr=tb[0]
        if not any('Level' in c for c in hdr): continue
        print('TABLE',i,'HDR:',' | '.join(hdr))
        for row in tb[1:]:
            if row and row[0].strip()==lvl:
                print('  L%s: %s'%(lvl,' | '.join(row)))
