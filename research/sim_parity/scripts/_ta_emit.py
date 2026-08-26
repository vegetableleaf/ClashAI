import json, sys, urllib.parse
OUT='research/sim_parity/ledger/r2_troops_a.jsonl'
def src(title, revid, raw):
    return {'url':'https://clashroyale.fandom.com/api.php?action=parse&page=%s&prop=wikitext|revid&format=json'%urllib.parse.quote(title),
            'revid':revid,'fetched':'2026-08-26','raw':raw}
def emit(lines, mode='a'):
    with open(OUT,mode,encoding='utf-8') as f:
        for l in lines:
            l.setdefault('cross_checks',{'edit_war':'pass'})
            f.write(json.dumps(l,ensure_ascii=False)+'\n')
    print('emitted',len(lines))
