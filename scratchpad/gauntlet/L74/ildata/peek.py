import sys, pyarrow.parquet as pq
for p in sys.argv[1:]:
    t = pq.read_table(p); print(p, t.num_rows); print(t.schema)
    r = t.slice(0, 2).to_pylist()
    for x in r: print({k: (str(v)[:300]) for k, v in x.items()})
