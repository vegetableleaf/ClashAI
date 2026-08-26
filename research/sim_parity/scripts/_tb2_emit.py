import json,sys,os
OUT='C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_b_new.jsonl'
def rec(key,field,cur,p1,p2,p3,vote,verdict,notes,sources,edit_war='pass'):
    return {"key":key,"field":field,"current_db":cur,"p1_vardefine":p1,"p2_table":p2,
            "p3_history":p3,"sources":sources,"vote":vote,
            "cross_checks":{"edit_war":edit_war},"verdict":verdict,"notes":notes}
def src(page,revid,raw,fetched='2026-08-26'):
    import urllib.parse
    return {"url":"https://clashroyale.fandom.com/api.php?action=parse&page=%s&prop=wikitext|revid&format=json"%urllib.parse.quote(page),
            "revid":revid,"fetched":fetched,"raw":raw}
def append(records):
    with open(OUT,'a',encoding='utf-8') as f:
        for r in records: f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print('appended',len(records),'->',OUT)
