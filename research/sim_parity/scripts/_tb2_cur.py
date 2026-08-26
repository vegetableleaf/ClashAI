import yaml,json,sys
y=yaml.safe_load(open('C:/Users/benpe/ClashBot/icebow/config/cards.yaml',encoding='utf-8'))['cards']
for k in sys.argv[1:]:
    r=y.get(k) or {}
    print('=====',k,' verified=',r.get('verified'))
    print('   ',json.dumps(r,sort_keys=True))
