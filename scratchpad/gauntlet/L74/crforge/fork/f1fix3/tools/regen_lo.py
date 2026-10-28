import json, sys
from pathlib import Path
sys.path.insert(0, r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crforge\pilot\sme')
sys.path.insert(0, r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\crforge\pilot\extract')
import regen_inputs, extract
extract.TABLES = Path(r'C:\Users\benpe\crforge_eval\cache\tables\16.402.22')
names = [l.split('\t')[0].strip() for l in open(sys.argv[1]) if l.strip()]
out = open(sys.argv[2], 'w')
for n in names:
    p = extract.LIVE / (n + '.jsonl')
    ctx = dict(names=extract.id_names(extract.TABLES), cat=extract.load_catalog()[0], by_name=extract.load_catalog()[1], shims=extract.table_shims(extract.TABLES), tt=extract.tower_table(), uhp=extract.unit_hp_table())
    r, why = extract.match(p, api=False, **ctx)
    if r is None:
        print('SKIP', n, why); continue
    out.write(json.dumps(r) + '\n'); print('ok', n, r['sides']['0']['deck'], r['sides']['1']['deck'], r['rng_free'], r['flags'])
