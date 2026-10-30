import json,sys
# idcmp.py NEW REF: compare one-match result records field by field (cls_ticks is new since the ref runs)
new={json.loads(l)['match']:json.loads(l) for l in open(sys.argv[1])}
ref={json.loads(l)['match']:json.loads(l) for l in open(sys.argv[2])}
for m,a in new.items():
    b=ref[m]; keys=sorted(set(a)|set(b))
    same=[k for k in keys if a.get(k)==b.get(k)]; diff=[k for k in keys if a.get(k)!=b.get(k)]
    print(m, 'same', len(same), 'differ', diff)
