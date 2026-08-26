import json,sys,os
OUT='C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_evos_a.jsonl'
recs=json.load(open(sys.argv[1],encoding='utf-8'))
n=0
with open(OUT,'a',encoding='utf-8') as f:
    for r in recs:
        f.write(json.dumps(r,ensure_ascii=False)+'\n'); n+=1
print('appended',n,'->',OUT)
