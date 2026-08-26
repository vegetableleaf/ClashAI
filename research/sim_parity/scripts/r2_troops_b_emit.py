import sys, json, os
LED=os.path.join(os.path.dirname(__file__),'..','ledger','r2_troops_b.jsonl')
LOG=os.path.join(os.path.dirname(__file__),'..','ledger','r2_troops_b_fetchlog.json')
log=json.load(open(LOG,encoding='utf-8'))
def src(page, raw):
    e=log[page]
    return {"url": e["url"], "revid": e["revid"], "fetched": e["fetched"], "raw": raw}
entries=json.load(sys.stdin)
with open(LED,'a',encoding='utf-8') as f:
    for e in entries:
        pages=e.pop('_pages')   # list of [page, raw] pairs
        e['sources']=[src(p,r) for p,r in pages]
        e.setdefault('cross_checks',{'edit_war':'pass'})
        f.write(json.dumps(e,ensure_ascii=False)+"\n")
print("appended",len(entries),"->",LED)
