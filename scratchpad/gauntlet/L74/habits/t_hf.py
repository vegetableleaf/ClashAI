import json, sys, polars as pl, glob, collections
f = sorted(glob.glob('scratchpad/gauntlet/L67/hf/replays/part-*.parquet'))[0]
df = pl.read_parquet(f, n_rows=200)
print(df.columns, df.shape)
p = json.loads(df['payload_json'][0])
def show(d, pre='', depth=0):
    for k, v in d.items():
        if isinstance(v, dict) and depth < 3: print(pre + k, '{'); show(v, pre + '  ', depth + 1)
        elif isinstance(v, list): print(pre + k, 'list', len(v), json.dumps(v[:2])[:400])
        else: print(pre + k, repr(v)[:120])
show(p)
c = collections.Counter(e.get('kind') for e in p['events']); print(c)
