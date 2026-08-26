import json,sys
d=json.load(open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/current_db_snapshot.json',encoding='utf-8'))['cards']
for k in sys.argv[1:]:
    r=d.get(k)
    if r is None: print('=====',k,'<<MISSING>>'); continue
    print('=====',k)
    for f in sorted(r):
        v=r[f]
        print('   %-24s %s' % (f, json.dumps(v)))
