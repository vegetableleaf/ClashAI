"""Run invlib.extract over every live match (CXXXVIII, CLIII, CLIX, CLX) and every pro icebow8 native re-drive -> rows.pkl
    nice -n 19 python extract_all.py      (single process, ~10 min)"""
import pickle
import time
import invlib as I

out = dict(match=[], xbow=[], rocket=[], opp_samples=[], bridge=[], tornado=[])
t0 = time.time()
for src, it in (('live', I.live_matches()), ('pro', I.pro_matches())):
    n = 0
    for m in it:
        e = I.extract(m)
        for k in out:
            out[k] += e[k] if isinstance(e[k], list) else [e[k]]
        n += 1
        if n % 200 == 0:
            print(src, n, round(time.time() - t0), 's', flush=True)
    print(src, 'done', n, flush=True)
pickle.dump(out, open(I.HERE / 'rows.pkl', 'wb'))
print({k: len(v) for k, v in out.items()}, round(time.time() - t0), 's')
